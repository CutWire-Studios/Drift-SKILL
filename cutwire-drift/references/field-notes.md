# Field notes: what a real Drift build actually costs

**Status, 2026-09-23:** every defect below has since been fixed in the development build after
0.6.0, and each fix carries a test. They are kept here because the *shape* of the trouble is
what is worth knowing — where effort leaks on a long build, and what to check when something
looks wrong. Where a section says "the fix", that is what shipped. If you are driving an older
Drift, the workarounds still apply.

Everything here comes from one production run — a 13-episode series that was
rejected after its pilot, then re-scoped into a single 69-second 16:9 showcase
that shipped in two versions. Numbers are counted from the transcripts, not
estimated. Read this before committing to a long build; it is mostly about where
effort disappears.

## The shape of the work

| Stage | Tool calls | Notes |
|---|---|---|
| Design direction | 49 | Mostly reading the editor's own catalogs and the repo source. Wrote two documents, touched no timeline. |
| Asset sourcing | 110 | Half of it ffprobe and contact sheets; 21 assets, every clip verified before use. |
| Voiceover | 21 | 14 lines, two of which had to be rewritten to fit. |
| Build (v1) | 247 calls / **2,279 ops** | 122 `apply` batches, 26 contact sheets, 13 stills. |
| Review (v1) | 126 | 100 of them `Read` on rendered stills and crops. |
| Fix + export (v2) | included above | 20 review items. |

The builder was by far the most expensive stage, and most of its cost was not
creative work.

## Cost sink #1: keyframes Drift wrote for you

**666 `remove_keyframe` ops against 287 `set_keyframe` ops.** Nearly a third of all
ops in the build were cleanup.

The mechanism: `set_transform` and the first `set_keyframe` on a clip write at the
playhead and snapshot the clip's other fields there. Key `x` while the playhead sits
outside the clip and you also get `y`, `width`, `height` keys at a time unrelated to
the animation — the clip then slides or resizes on screen for reasons nothing in your
spec explains. Pills, headlines and a reframe panel all drifted this way, twice: once
in v1 and again in v2 after the same mistake.

The mechanism turned out to be two things, and only one of them was the commonly assumed one.
Nothing copies sibling properties: **every visual clip is born with a key at t=0 on x/y/width/
height**, because the compositor needs an explicit size. A first `set_transform` then added a
*second* key and the existing ones became a visible animation. On top of that, the write was
clamped only at the low end, so a write made with the playhead outside the clip stored a key
outside it — which is what scattered keys at unrelated times.

**Both are fixed** on a current build (`docs/MCP.md`, Traps). Writes are clamped into the
clip's own span. `set_transform` moves the single birth key instead of adding another, so
the value holds. A key at the playhead is added only when that property already has two or
more keys, or when auto-key is on. Removing the birth keys, or seeking before every
constant `set_transform`, is the old workaround and now only adds work.

Still worth doing:

1. Seek before `set_transform` only when the property is already animated or auto-key is on — that write goes to the playhead. `set_property_keyframes_enabled(false)` forces a constant instead.
2. Generate real multi-key motion with `scripts/keyframes.py`. It seeks because `set_keyframe_interpolation` moves the playhead, not because a constant transform needs it.
3. Run `scripts/drift_cli.py audit --emit-fix keys.json` after each section. It reports keys that sit outside their clip. A single key is a hold, not a defect.

The audit found two surviving stray keys in the shipped v2 project.

## Cost sink #2: phantom transitions

Building with `set_overlap {enabled:true}` and then trimming left **13 crossfades
nobody added**. One spanned −4.9 s to 18.7 s and put the wrong footage on screen for
seconds. Removing two of them pushed their clips later and stretched a 35 s timeline
to 38.5 s.

**The fix** landed hours after this build hit it: overlap no longer mints crossfades, the window
is clamped to the clips, and removing one no longer shoves them. Transitions now also bind to the
clip at the cut rather than the earliest overlapping one, and a stored duration longer than the
clips is clamped on load.

Still worth doing:

- Audit transitions per track after a trim pass: they are only visible in `inspect({clips:true, detail:true})` under `tracks[].transitions`.
- `remove_transition` needs `{track, id}` — ids are unique within a track only. Getting this wrong cost two failed batches.

## Cost sink #3: measuring audio through a broken meter

`analyze_loudness` reported `true_peak_db: 0.0` for every range, including music-only
ranges that ffmpeg measured at −2.6 dBTP. Five mix iterations were spent chasing peaks
that the meter could not see. `normalize_volume` then read the mono voiceover WAVs about
3 dB quieter than ffmpeg does and raised them into clipping, and `utility.limiter` added
gain rather than limiting.

**The fix:** the meter now sums the channels as BS.1770 requires (it was 3.01 dB low on
everything), measures true peak with real 4× oversampling before the master clipper, the limiter
limits, and `duck_under` samples a rest level per dip and replaces its own previous pass.

The mix that shipped, before those fixes: voiceover at unity (the files were already −16 LUFS /
−2 dBTP), music at 0.86 with a hand-written envelope, final export −16.7 LUFS integrated,
−2.9 dBTP. It misses the −14 LUFS delivery target by 2.7 LU, and inside Drift there was
no way to close that without clipping the voice. That is what `audio_master.py master` is
for; the decision — accept the quieter mix, or master outside the editor — belongs to the user.

`duck_under` was abandoned for a hand-built envelope because it samples one rest level for
the whole clip and appends keys on re-run, which pumps between words.

## Argument traps that cost round-trips

These are unchanged — they are how the ops are, not defects.

| Mistake | Correct |
|---|---|
| `move_clip {clip, start}` | `move_clip {clip, at}` |
| `remove_transition {id}` | `remove_transition {track, id}` |
| `analyze_loudness {}` | `analyze_loudness {clip}` or `{start, duration}` |
| Keyframing `w` / `h` | `width` / `height` |
| `export_video` with settings omitted | Every field explicit — omitted ones inherit the previous render, which produced an audio-only file |
| Referencing an id created earlier in the same `apply` batch | Split the batch; read the id from `done[i].result.id` |

## What the editor cannot do that plans assume it can

- **`auto_reframe`** wrote square crop boxes that stretched the picture and zoomed ~3×. Fixed: it keeps the source's aspect, fits the target inside the canvas, and reports `scale`/`upscaled`. It still cannot resolve finer than the canvas, because the decode is canvas-bounded — that limit is real and documented.
- **`detect_beats`** locked to half time on a clean 120 BPM track. Fixed with octave correction; the real track now reports 120.19 at confidence 0.5, which honestly reflects a close call. Grids are still transient — check `stale`.
- **`split_clip`** lost the effect stack on the new piece, and shifted the tail's animation. Both fixed.
- **`list_stickers`** has no generic icon set. The build shipped an emoji. Unchanged.
- **`duotone`** rendered black through MCP. Fixed.

## Process failures, which cost more than any op

- **The MCP connection dropped mid-session** and the tools did not come back; the session could not recover on its own and needed the user to run `/mcp reconnect drift`. Anything scripted against the HTTP endpoint kept working throughout.
- **Two background agents died silently** — one at a rate limit, one when the session ended. Both left empty asset directories that looked like completed work. Always check the actual output files before assuming a stage landed, and resume the agent rather than restarting it.
- **A rate limit hit mid-pipeline.** Stages that write a document as they go can resume; stages that hold everything in context cannot.
- **No Whisper CLI**, so the voiceover text was never verified against the script. This was reported as unverified rather than glossed over, which is the right call.
- **Nothing was ever watched or listened to.** Every claim about the result rests on stills and measurements. Say so plainly, and leave playback judgements to the user.

## The rejection, and what actually fixed it

The pilot came back with: *"It looks bad, specially the colors don't match, background
and foreground colors don't match, creates low contrast. Also a lot of text effects you
used look like they came from an old tv advertisement from 2000."*

Root causes, all avoidable:

- Stock text presets applied straight out of the box (`impact`, `neon`, `chrome`, `retro-3d`, `fire`, `glitch`), each carrying its own palette, so no two sections agreed on a colour.
- No contrast check of text against the footage behind it.
- 1080p 16:9 footage cover-cropped into a 1080×1920 canvas — roughly a 3× upscale.

The rebuild passed review on typography, contrast, palette and "nothing looks dated"
because it started from a written design system with computed contrast ratios, built text
stacks by hand instead of calling `apply_text_look`, and gated every clip on resolution
before it reached the bin. Where it still scored low — 2 out of 5 on *clarity of features*
and *audio* — the cause was that four beats did not actually demonstrate the feature they
claimed, which no amount of Drift skill fixes. That is a storyboard problem, and it is why
the pipeline has a reviewer who is not the builder.

A design can be consistent and still be generic. *Craft* in
`references/design-system-template.md` is the check for that: the subject, the signature,
and the three default looks.
