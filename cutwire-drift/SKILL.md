---
name: cutwire-drift
description: Build, edit, verify and export real videos in the CutWire Drift editor through its MCP tools (mcp__drift__*), and run a full promo, showcase, or long-form explainer from brief to graded export. Use this whenever the work touches Drift, the drift MCP, a timeline, clips, cuts, captions or subtitles, transcripts, cutting filler words or retakes from talking-head, interview, tutorial or podcast footage, picking the best take, speaker labels, voiceover or sound effects, transitions, keyframes or motion, speed ramps, Lottie or animated diagrams, screen-recording window cards, a programmatic rebuild of a timeline, 3D models, 3D tilts/perspective/depth on clips, depth-map effects (relight, depth of field, fog, text behind a subject), stickers, face or audio effects, beat-syncing, a showcase/promo/reel/trailer, or exporting a finished video — even when the user never names the skill or the editor. It carries the field-tested operating loop, the workarounds for ops that are currently broken, and bundled scripts (drift_cli.py, keyframes.py, media_qc.py, audio_master.py, fetch_stock.py, tts_fish.py) that replace work agents otherwise redo by hand every time.
---

# CutWire Drift

Drift is a desktop video editor that exposes the open project over MCP, so you can
build a real edit — footage, text, effects, keyframes, audio, export — without a
human touching the timeline. The tools are well documented; what this skill adds is
what only shows up once you have built something long: which ops lie, which ones
quietly cost you hundreds of wasted calls, and how to tell whether what you made is
any good when you can neither watch nor hear it.

Two measured builds sit behind this. A 69-second showcase took 2,279 ops, 122 `apply`
batches and two review rounds. A 9:53 explainer (about 284 clips, diagrams, screen
recordings, music and a 77-line voiceover) was rebuilt from a script instead of from
chat. That method is `references/longform-build.md`.

## Where the reference material lives

- `catalog({guide:true})` — the editor's own agent guide, always current for the build you are driving.
- `docs/MCP.md` in the Drift repo — the full 480-line reference, including a `Traps` section. Read it when you are working inside the repo.
- `references/field-notes.md` — what went wrong in a real build and what it cost. Read before a long build.
- `references/production-pipeline.md` — running a film from brief to export with sequential agents and written hand-offs. Read when the ask is "make a video", not "change this clip".
- `references/longform-build.md` — a scripted rebuild for a long, graphic-heavy film: one timeline writer, offline Lottie, window cards, lane map, voiceover, and the deletes that emptied a timeline. Read it before building anything past a short montage.
- `references/design-system-template.md` — craft notes (identity, type, copy, motion) and a worked design system (palette, type, motion tokens, banned effects) that survived review. Adapt or replace the example; do not ship its defaults unexamined.

## Preflight, every session

1. `inspect()`. It tells you `w/h/fps`, `dur`, `overlap`, `dirty`, `path`, `revision` and the track list. Take thirty seconds over it.
2. If `dirty` is true and `path` is set, `save_project` before anything destructive. **`new_project` discards the open timeline with no warning and clears undo.**
3. If the `mcp__drift__*` tools are missing or erroring, the client connection has dropped. It does not recover on its own: ask the user to run `/mcp reconnect drift`. Meanwhile `scripts/drift_cli.py` talks to the same editor over HTTP and keeps working — it finds the URL and token in `$XDG_RUNTIME_DIR/drift/mcp-session.json`, which the editor rewrites on every launch.
4. Decide the canvas before importing anything, and gate the footage against it (see *Footage*).

## The operating loop

**Discover → schema → apply → verify.** In the reference build this produced roughly
four hard failures in 2,279 ops, and every one of them came from skipping the schema step.

- `search({q})` to find an op, `toolbox({ops:[…]})` for its exact schema **before its first use**. Arguments that look obvious are often not: `move_clip` takes `at`, not `start`; `seek` takes `at`, not `t` (`t` stops the batch with `bad_args`); `remove_transition` needs `{track, id}` because ids are unique per track only; `analyze_loudness` needs `clip` or `start`+`duration`.
- Enumerate ids, never invent them: `list_effects`, `list_transitions`, `list_text_presets`, `list_text_animations`, `list_shapes`, `list_stickers`, `list_fonts`, `list_export_options`. Ask once, early, and keep the answer.
- One `apply` batch = one undo step. A batch **cannot** reference an id produced inside itself, and `apply` is **not atomic** — on failure `done` holds the ops that already ran and `stopped` says where it broke. Recover by re-reading `inspect`, not by replaying the batch.
- Verify each section as you finish it, not at the end. Fixing beat 3 after beat 11 is built means re-checking everything downstream.

Batch mechanical work through the CLI instead of the MCP tools when the reply JSON
would be noise you never read — hundreds of keyframe or cleanup ops, for example:

```bash
scripts/keyframes.py emit motion.json | scripts/drift_cli.py apply -
```

## A long film is a script, not a chat

Anything past a short montage — repeated titles, many diagrams, screen recordings,
a voiceover measured in dozens of lines — is rebuilt from a program that calls
`scripts/drift_cli.py`, not from a few hundred chat turns. The 9:53 explainer was
that program: a lane map, a timing module, overlap checks, and parts you can re-run.
`references/longform-build.md` is the method. Before the first scripted `place_clip`,
read the still-true table below (`place_clip`, images, `cues:true`, `duck_under`).
The failures that cost a full rebuild:

- One writer on the open project. Who else may run, and what they may not touch, is in `references/production-pipeline.md`.
- Prove the kit on a throwaway timeline before the storyboard gets long: one diagram, one tilted window card, one text preset.
- Build every lane in setup, before any clip. Inserting a lane later renumbers the map the script stored. For exact times, turn overlap on and check `placed` against `requested`.
- Do not save after a bulk delete until `inspect` shows you removed only what you meant. If the timeline is already empty, `list_history` and `undo_to` still reach the earlier step — save does not clear undo — then audit and save.
- Pre-render screen recordings to alpha cards with an explicit duration. A looping still used as an ffmpeg input encodes forever when duration is omitted.

## Editing speech: read it, don't watch it

Talking footage (interviews, tutorials, launches, podcasts) is edited from the transcript. You
cannot watch 30,000 frames, and you don't need to: the words with their times tell you where
every cut can go, and pictures are only worth looking at the cuts. Drift keeps a word-level
transcript on each asset, in source time, so it survives every later cut and undo.

1. **Inventory.** `inspect`, then `transcribe({clip})` for every source that has speech (it
   covers the whole file, once; poll `get_job`). Use `engine:"elevenlabs"` when the user has a
   key and wants fillers kept, audio events tagged (`(laughter)` marks a beat worth keeping) or
   speaker labels on a hard recording. It is billable, so ask first. `diarize:true` labels
   speakers locally.
2. **Read.** `get_transcript({asset})` gives each take as `compact` lines, `[start-end] S1 text`,
   in source seconds: the cheapest full read. One pass over it for slips, mis-speaks, false
   starts and retakes to avoid. `view:"words"` when you need word indices.
3. **Converse, then propose, then wait.** Say in plain English what the material is and ask the
   questions it raises: length, pacing, must-keep and must-cut moments, captions, look. Then
   propose the edit in 4–8 sentences: structure, take choices, cut style, captions, estimated
   length. **Do not touch the timeline until the user has confirmed that plan.**
4. **Cut on words.**
   - `assemble({edl:[{asset,start,end}]})` builds a sequence from the best take of each beat
     across sources. `keep_ranges` does the same for one clip.
   - `cut_words({clip, text:"um"})` or `({clip, words:[[i,j]]})` takes out fillers, false starts
     and retakes.
   - `remove_silence({method:"vad"})` removes dead air without mistaking music or room noise
     for speech.

   Every cut lands between words and gets a 30 ms de-click. Linked audio and video stay
   together. Keep `padding` in the 30–200 ms window: tighter for fast social cuts, looser for
   documentary. Pauses of 400 ms or more are the cleanest cut points. For a gap tighter than
   that, `snap:"silence"` cuts at its quietest point. Extend past a punchline to keep the laugh.
5. **Check every cut before showing anything.** For each cut, over ±1.5 s:
   - `get_waveform({image:true, start, duration:3})`: its word lane shows what is either side,
     and the waveform shows a spike where a pop slipped through.
   - `frames({at:[cut−0.2, cut+0.2]})` for a jump in the picture.

   Also sample the first and last 2 s. Fix what fails and check again, **at most three passes**,
   then report what is still wrong rather than looping.
6. **Captions last.** `generate_subtitles` on transcribed media is instant and lands on the
   words, so run it after the cut is final; style it after that.
7. **Remember.** Append a section to `<videos_dir>/edit/project.md`: date, the strategy, take
   and cut decisions with a one-line reason each, and what is outstanding. On the next session,
   read it first and sum up the last session in one sentence before asking whether to continue.

## Clip references

Address clips by **UUID** from `inspect({clips:true})`. `track`+`index` is positional and
shifts under you: `add_track` inserts at index 0 and renumbers every track. Clip ops
never fall back to the selection — the selection-based ops (`separate_audio`,
`merge_clips`, `copy_selection`, …) need `select_clip` first, and they are the exception.

After anything structural — `add_track`, `split_clip`, `set_speed_curve`, `apply_denoise`,
a delete — re-read `inspect`. `set_speed_curve` in particular returns a **new** clip id and
puts the retimed clip on a **new lane**; end the batch there.

## Keyframes

A visual clip is still born with one key at its start on x, y, width and height. On a
current build, `set_transform` **moves that key**, so a plain reposition holds for the
whole clip. It used to add a second key at the playhead, and the two keys played as an
animation — the showcase spent 666 `remove_keyframe` ops undoing that. Do not remove
the birth keys, and do not seek before a constant `set_transform` to "stop it animating".

`set_transform` writes a new key at the playhead only when that property already has
two or more keys, or when auto-key is on. Seek to the time you mean before that write,
or call `set_property_keyframes_enabled(false)` to force a constant. Writes are clamped
into the clip's own span. The old cost is written up in `references/field-notes.md`.

- Keyframe property names are not the transform names: `width`/`height`, not `w`/`h`. Also `x`, `y`, `rotation`, `rotationX`, `rotationY`, `z`, `perspective`, `opacity`, `volume`, `fx.<i>.<param>`, `mask.<key>`, `text.<key>`, `text.layer.<id>.<field>`, `shape.<key>`, `model3d.<key>`. The four 3D names are the same in `set_transform` and `set_keyframe`.
- `set_keyframe_interpolation` **moves the playhead** to `at`, which changes the default time of later ops in the same batch. Seek back after a run of them.
- `set_keyframe_tangents` sends omitted handle fields as 0. Pass all four every time.
- `remove_keyframe` deletes the **nearest** key with no distance limit. Read exact times from `list_keyframes` or `inspect` detail first.
- A `set_keyframe` time past the clip is stored at the clip's edge. On an 8s clip, `at: 50` was kept at 8. The reply can still echo the time you sent, so read the keys back.
- `inspect` lists `keyframes` only for properties that are actually animated. A single key holds.

`scripts/keyframes.py` emits the whole correct sequence — seek, values, interpolation,
bezier handles, seek back — from a short spec, with named easing curves
(`settle`, `glide`, `exit`, `linear`, `hold`) defined in the design-system reference.

`scripts/drift_cli.py audit` finds keys outside their clip and implausible
transitions in the open project, and `--emit-fix FILE` writes the cleanup batch.
A single key is reported as a note, not a problem: it holds.
Run it after each major section and before every export. On the shipped v2 of the reference
build it found two stray keys that two humans and two agents had missed.

## 3D: tilting clips, depth, and depth effects

Needs a Drift build from 2026-09-26 or later. If `toolbox({ops:["set_transform"]})` lists no
`rotationX`, the build doesn't have it. Don't try to fake a tilt with a
narrowing `width` animation; it reads as a squash, not a turn.

**Clip transforms in 3D.** Every video, image, text, shape, sticker or Lottie clip can be made a
**3D layer**. This is a per-clip switch, `layer3d`, and it is off by default. A 3D layer has four
more transform properties; `set_transform` and `set_keyframe` take them under the same names.
Writing any of the four turns the switch on for you. `set_transform({layer3d:false})` flattens the
clip: all four go back to their defaults, keys included, and only `undo` brings them back:

| Property | Default | Meaning |
|---|---|---|
| `rotationX` | 0 | Tilt in degrees; + tips the **top edge away** from the viewer |
| `rotationY` | 0 | Tilt in degrees; + swings the **right edge away** from the viewer |
| `z` | 0 | Depth in project pixels; − pushes away (smaller), + pulls toward the viewer |
| `perspective` | 2000 | Distance from the eye to the canvas, in px; lower = stronger foreshortening |

`rotation` is still the flat in-plane spin, and it turns the clip within its tilted plane.

- **The eye sits in front of the canvas centre, not the clip.** A clip away from the centre drifts
  toward the centre as `z` goes negative, the way a real camera sees it. At `z = −perspective`
  the clip is half size. At `z ≥ perspective` it is behind the eye and disappears.
- **Stacking is still track order.** A clip with a lower `z` on a higher track still draws on top,
  and tilted clips never cut through each other. To put something behind, move it to a lower
  track.
- **There is no back face.** Past 90° of tilt you see the clip mirrored. A card flip needs two
  clips: the front animates 0→90, then a cut to the back clip, which animates −90→0.
- **Pick `perspective` once per project** and use the same value on every tilted clip, otherwise
  clips side by side look as though they were shot through different lenses. Around 1500–2500 on
  a 1080p canvas looks natural; below ~800 it starts to look like a fisheye.
- A tilt around 60–75° reads as a strong turn. Tilts of 5–15° with `glide` easing give the subtle
  "card floating" look. Animate `z` and `perspective` with `linear` for a camera-like push.
- **3D model clips (`add_model3d`) ignore all four.** They have their own `model3d.rotX/rotY/rotZ`
  and `model3d.depth`.
- **Reading and resetting.** `set_transform` returns `layer3d` and the four fields only on a
  3D layer. On an `inspect` detail row they live inside `transform`, not as sibling keys.
  `reset_transform` clears them and switches 3D off.
- Masks and effects follow the tilted clip, because they are applied in the clip's own frame
  before the tilt. Intro/outro animations and text animations stay flat on top of the tilt.

**Depth effects** work from a *depth map estimated from the footage*. They are not related to the
clip's `z`. Each map value is relative within that clip: 0 is its farthest point, 1 its nearest.

1. Check `ai_capabilities` for `depth-model`; if it is missing, `install_addon`.
2. `estimate_depth({clip, quality})` returns `{job_id}`; poll `get_job`. It is slow, about 0.5 s per
   frame on CPU at `draft`, so estimate once the cut is final.
3. `add_effect` with one of:
   - `depth.relight`: up to four 3D lights, with shadows;
   - `depth.focus`: depth of field;
   - `depth.fog`: haze that thickens with distance;
   - `depth.view`: shows the map itself (for debugging);
   - `depth.occlude`: goes on a layer *above* the footage (text, sticker, model) and places that
     layer inside the scene. Set its `target` to the footage clip's id, and estimate depth for
     that footage clip, not for the layer.
4. `sample_depth({clip, x, y, time?})` reads the depth at a point. Use it to set `focusDepth` on
   the subject, or `depth` on `depth.occlude` to just behind them. The classic use is title text
   behind the person.

`inspect` detail rows report `hasDepth`. The map is cleared when the clip's pixels change
(replace source, switch angle, orientation), so re-estimate after those.

## Ops that are broken, fixed, or merely surprising

Everything in the first table was found by driving a real build and has since been **fixed in
the development build after 0.6.0**. Keep the workarounds only if you are driving an older
Drift; on a current build, using them costs you quality for no reason. Check the app's version
before deciding — `inspect()` does not report it, so ask the user or read the release notes.

| Op | Was | Now |
|---|---|---|
| `duotone` | Rendered black — the colour params were declared as a type the loader degraded to float, so 0.0 went to a `vec3` uniform. | Works, and takes colours. A package with an unknown param type now fails to load loudly instead of rendering black. |
| `analyze_loudness` | `true_peak_db` always 0.0: measured after the master soft clipper, with an interpolation that could not see between samples. | Real 4× oversampled true peak, measured before the clipper. |
| Loudness generally | Every reading was 3.01 dB low (channels averaged, not summed), so `normalize_volume` applied 3 dB too much gain and clipped. | Matches BS.1770 and ffmpeg's `ebur128`. Normalise is relative to the clip's existing volume, idempotent, and warns when the target would clip. |
| `utility.limiter` | Added ~4 dB instead of limiting; lowering the ceiling added more. | A real ceiling limiter. |
| `duck_under` | One rest level for the whole clip, and appended keys on every re-run, so the mix pumped. | Per-dip rest level, and a re-run replaces its own previous pass. |
| `detect_beats` | Locked to half time on music with a strong downbeat — 60 BPM on a 120 BPM track, at confidence 1. | Octave-corrected; confidence drops when the two octaves are genuinely close. Analysis is still transient — check `stale`. |
| `split_clip` | The new piece lost its effect stack, and the tail replayed the animation shifted later. | Both halves keep effects, and the animation is continuous across the cut. |
| `auto_reframe` | Square crop boxes that stretched the picture and zoomed ~3×. | Keeps the source's aspect and fits the target inside the canvas; the reply carries `scale` and `upscaled`. |
| `add_lottie` / `add_model3d` / `add_emoji` / `add_shape` | All landed on one graphic lane and gap-pushed each other down the timeline. | Each stacks onto its own lane at the time you asked for. `add_emoji` takes a `track`. |
| `set_effect_param` and siblings | Accepted any key or index and stored it silently. | Fail `not_found`. **A batch that relied on the silent no-op now stops at the bad op.** |
| `set_volume` at an existing key | Minted a duplicate key a fraction of a millisecond away. | Snaps onto the key that is there. |
| Keyframe writes | Not clamped to the clip, so a write with the playhead outside it landed outside it. | Clamped to the clip's own span. |
| `set_transform` on a one-key property | Added a second key at the playhead, so the birth key and the new one played as a move. | Moves that single key. The value holds. A playhead key is added only when the property already has two or more keys, or auto-key is on. |
| `export_video` | Inherited *every* omitted setting from the last render, including `audio_only` — one build shipped an audio-only file. | `audio_only` does not carry over. An audio-only export followed by one that passed only `path` wrote a 1080p h264 mp4 with aac, not another audio file. Other omitted settings inherit from the last export in this app profile, then defaults. Pass every field. |

| Overlap + trimming | Minted phantom crossfades, one spanning −4.9 s → 18.7 s over the wrong footage. | Fixed in 2026-09; transitions also bind to the clip at the cut rather than the earliest overlapping one. |
| Lottie `loop:"hold"` | Could seek one frame past the end. | Folds to the last drawn frame. |
| `split_clip` fades | Both halves kept the clip's fade-in and fade-out, so an invisible cut dipped at the split. | Inner edges get no fade; outer fades stay. Split-left/right keep the fade on the edge that moved. |
| Split-left / split-right on linked A/V | Trimmed only the clip you named; its linked audio or video stayed long and followers on the other track didn't ripple — desync. | The whole linked group is trimmed and every one of its tracks ripples. |
| Audio at every cut | Up to ~20 ms of the removed audio leaked past each clip's out point, clicking at the join. | Silenced at the out point; cut ops also add a de-click ramp. |
| `remove_silence` on a video with separated audio | The picture read as silent (its sound is on the partner) and was deleted outright. | Listens to the linked audio; both halves are cut together. |
| `remove_silence` near a clip edge | Silently skipped cuts within 100 ms of an edge but still listed them in `removed`. | Cuts them, and `removed` reports only what went. |
| Transitions on audio tracks | Refused; a butt cut between separated audio clips could only hard-cut. | `add_transition` works on audio tracks, with a true crossfade from the media past the cut, and a video transition mirrors onto the linked audio. |

Still true, and worth knowing:

| Op | Behaviour |
|---|---|
| `set_mask`, `set_subtitle_cues` | Replace the whole object; omitted keys revert. Read, merge, send back. |
| `place_clip` | The reply has `placed` and `requested`, and every number is rounded to 3 decimals. With overlap on, a live check landed on the requested time down to one frame, snap on or off. With overlap off, a time that hits an occupied span is pushed to the next free gap and the reply sets `reason` to `"gap"`. `asset` accepts the bin id or the file name. Turn overlap on when the script needs that exact `at`. |
| `place_clip` of an image | `type_mismatch` ("Track does not accept this asset") on a video track. Images go on a shape track. A placed image is contain-fit and centered: a 100×100 file became 1080×1080 at x=420, y=0 on a 1920×1080 canvas. `list_assets` returns `name` and `id`, not a path; the detail row has `path`. A relative `import_media` path fails `import_failed` ("No readable files") rather than a `missing` list. |
| `add_text` | No `track` argument, so every title shares one text lane until you move it. With overlap off, a second title at a busy time is pushed later (requested 3s, landed at 8s on a 5s clip). Shapes, emoji and Lottie at the same time each get their own lane. With overlap on, the two titles share the lane. Simultaneous titles on separate lanes still need `add_track` and `move_to_track`. `add_shape` is not contain-fit: a rectangle landed as a 518.4×324 box at (0, 0). |
| `inspect({clips:true, cues:true})` | Still puts `subtitleCues: []` on every clip, including images, text and shapes. Deleting where the field is present wipes the timeline. `detail:true` omits that empty array, so the field is absent on clips with no cues. Delete by track type `subtitle`, and count first. |
| `duck_under` across sentence-length clips | The stacked-key bug is fixed: each dip returns to the level the music was at, and a re-run replaces the previous pass. The release between separate sentence clips is that envelope working. When the rise is unwanted, set one music gain about 12 LU under a −16 LUFS voice. Confirm with `list_keyframes` on `volume`, and with `audio_master.py windows` on speech ranges versus music-only gaps. |
| `list_stickers` | Has no generic icon set — no clapper, film, or plain arrow. Use `add_emoji` with the character. |
| A Lottie that ends empty | Still holds an empty frame, because that is what the document draws. Check the artwork before blaming the loop mode. |
| `auto_reframe` sharpness | The decode is bounded by the canvas, so a crop can never resolve finer than canvas resolution however good the source. |
| `detect_beats` | The analysis dies on the next edit that changes the mix. Read the grid out before mutating. |
| Effect stacks | Live on an adjustment clip on its own lane. Keep addressing the original clip; expect the extra lane in `inspect`. |
| `set_guides` | Removed. Preview guides are now user-edited guide sets in the UI, not an MCP op. |

## Seeing and hearing what you built

You cannot watch or listen. Do not claim you did. The honest path:

- `activity({start,end})` → where something changes. `frames({at:[…]})` → a labelled contact sheet of those moments. `capture({at})` → one full still for detail. Times always come back in the text block; do not trust burned-in labels alone.
- Check the *intent* of each section, not just that pixels exist: is the subject where the text isn't, is the "after" half of a before/after on the lit side of the face, are two "different" looks actually different? A reviewer on the reference build found two grades that differed by one code value.
- Audio: `scripts/audio_master.py measure` for integrated LUFS / LRA / true peak, `windows` for per-range levels. A voice should sit roughly 8–12 LU above the music under it. A steady bed does that; see the `duck_under` row for why sentence-length clips should not be ducked.
- Spoken text is checkable now: `transcribe` the voiceover or the export's source clips and compare `get_transcript({view:"text"})` with the script. If no transcription model is installed (`ai_capabilities`), say the VO text is unverified rather than implying it was checked.

## Footage

Resolution is the one defect you cannot fix in the edit. A pilot was rejected for
cover-cropping 1080p 16:9 clips into a 1080×1920 canvas — a ~3× upscale.

```bash
scripts/media_qc.py check --canvas 1080x1920 --crop-headroom 1.6 assets/video/*.mp4
scripts/media_qc.py sheet clip.mp4 --n 9 --out /tmp/clip.jpg   # then Read the jpg
```

`--crop-headroom` is the punch-in you plan: a clip you will zoom 1.6× has to still cover
the canvas afterwards. Source with `scripts/fetch_stock.py` — Mixkit needs no key but caps
free video at 1080p; Pexels (with `$PEXELS_API_KEY`) is where 4K comes from. Every download
appends a licence row to `credits.md`, so the trail exists before anyone asks for it.

## Export

Pass every setting explicitly; `export_video` is async. Poll `inspect().export` or
`export_status`, then verify the file with `ffprobe` — duration, resolution, frame rate,
both streams — and measure loudness on the actual file. If the mix cannot reach the
delivery target inside Drift because the peaks fight back, master the export
(`audio_master.py master`) rather than pushing the mix into clipping, and say which you did.

## Taste, when the output is for an audience

A build can be mechanically perfect and still get rejected. The first pilot was, for
reasons worth generalising: stock look presets (fire, chrome, retro-3d, glitch, neon)
read as a 2000s TV advert; per-section colours had no common palette; text sat at low
contrast over busy footage. What passed review instead: one palette with checked contrast
ratios, text stacks built by hand rather than `apply_text_look`, at most two elements
animating at once, and one idea per screen.

Before the first keyframe, write the design down and reject it once. Name the subject,
who it is for, and the film's single job, and open on the most characteristic thing in
that world. Spend the boldness in one signature and keep the other beats quiet. A plan
that would fit any similar video is not finished. Three looks show up unprompted, and
they are defaults: warm cream with a serif and a terracotta accent; near-black with one
acid-green or vermilion hit; a hairline broadsheet. Use one when the brief or the
product's own materials require it.

Motion holds the same line. Arrivals are critically damped; overshoot is for a picture
that was thrown (a flicked card, a landing), not for a title. An element leaves along the
path it entered. A callout starts at the thing it names. A glass plate arrives by blur
and scale together. A sound hit lands on the frame the picture commits. On-screen words
do one job each, in the viewer's language.

`references/design-system-template.md` holds the craft notes and a worked system that
passed review. Derive the project's own palette and tokens from it, then hold every beat
to them.

## When the ask is a whole video

Build it in stages with written hand-offs rather than in one pass: design → sourcing →
voiceover → build → review → fix. Each stage leaves a document the next one reads, which
is also what lets a stage be resumed after a crash or a rate limit instead of restarted.
`references/production-pipeline.md` has the stage contracts, the document templates and
the review rubric.

## Scripts

All in `scripts/`, all standalone (`--help` on each), Python 3 + ffmpeg only.

| Script | Use it for |
|---|---|
| `drift_cli.py` | `inspect`, `call`, `apply`, `capture`, `frames`, `schema`, and **`audit`** — the stray-key and phantom-transition check. Works when the MCP client connection is down. |
| `keyframes.py` | Motion spec → a correct seek/keys/interpolation/tangents batch with named easing curves. |
| `media_qc.py` | Resolution/fps/bitrate gate against the canvas, and contact sheets to look at. |
| `audio_master.py` | ebur128 measurement, per-range levels, two-pass loudnorm master of the export. |
| `fetch_stock.py` | Mixkit and Pexels search/download with a licence row per file. |
| `tts_fish.py` | Fish Audio voiceover that fits its slot: estimate first, then synthesise, trim, normalise, retry. Its `estimate` step is still the way to check a line fits before spending calls; for the synthesis itself prefer Drift's `tts_generate` (ElevenLabs or Fish, imported straight into the bin with its provenance) when the user has set a key in Settings → Cloud providers, and keep this script for older builds or when Drift has no key. |
