# Producing a finished video, stage by stage

When the ask is "make a video" rather than "change this clip", one pass through the
timeline will not survive contact with review. The structure below came out of a build
that was rejected once and then passed: **six stages, each ending in a document the next
stage reads.**

The documents are not ceremony. They are what lets a stage be *resumed* after a crash or
a rate limit — both of which happened — and what lets a reviewer judge the result against
something written down rather than against taste in the moment.

```
brief → design → sourcing → voiceover → build → review → fix → (review again) → ship
          │         │           │         │        │
   design-system  manifest    vo-        build-  review-vN.md
   storyboard     credits     manifest   log
```

## Running it with agents

Run the stages **in order**: each one needs the previous one's document. Inside a
stage, parallel workers are safe only when they do not share the open timeline.
Sourcing (many downloads) is one case. Authoring Lottie and other graphics as files
is the other — `longform-build.md`. The timeline has one writer.

- Give each agent the file paths it must read, in full, before doing anything.
- Tell it exactly which documents to write and where. A stage that writes nothing cannot be resumed.
- Tell it what it may not touch: the design agent does not edit the timeline, the sourcing agent does not open Drift, a graphics agent writing files does not open Drift either, the reviewer does not modify the project. File-authoring details are in `longform-build.md`.
- When an agent stops early, check its output files before assuming the work landed. Two agents in the reference run reported nothing and left empty directories. Resume the agent with a message naming what already exists, rather than starting over.
- Budget: the build stage is the expensive one — in the reference run, roughly 950k tokens and 247 tool calls for 69 seconds of video.

## Stage 1 — Design

**Writes:** `design-system.md`, `storyboard.md`. **Touches the timeline:** no.

The design system is the contract that stops the build drifting into stock presets. It
must contain, at minimum: the subject, the audience, and the film's single job; the one
signature element and the emotion the film is tuned to; palette tokens with **computed
contrast ratios**; the type scale with per-role tracking; standard text shading stacks
written as literal `set_text` layer arrays; layout boxes in canvas pixels; motion timing
and easing tokens; a **banned list**; footage requirements (resolution floor, grade, what
to avoid); audio targets; and the end card spec. `references/design-system-template.md`
is a worked one. Its *Craft* section — identity, the three default looks, on-screen copy,
motion — is the brief for this stage. Read it before choosing a token.

The storyboard turns it into beats. Per beat: time span, footage brief, the exact clips and
lanes, camera keys, text with its box and animation, overlays, and — the part that is
always skipped and always missed — a **Verify** block listing the times to capture and what
must be true in each. Also global setup (canvas, background, overlap off, lane map), the
music/beat grid with a rule for rescaling every time if the track's BPM differs, and a
sourcing checklist the next stage can work through item by item.

Read *Craft* in the design-system template before writing. The difference between "a
palette" and a palette with ratios computed against each background shows up immediately
in review, and so does a system that would fit any other product in the category. Send
that one back.

## Stage 2 — Sourcing

**Writes:** `assets/manifest.md`, `credits.md`. **Touches the timeline:** no.

Work the storyboard's checklist. For every item: download, verify with
`media_qc.py check --canvas <WxH> --crop-headroom <planned punch-in>`, look at a contact
sheet, record the licence. `fetch_stock.py` writes the credit row as it downloads.

The manifest is where the build stage learns what it is actually getting, so record the
**misses** as loudly as the hits: a clip 30 fps where the ramp needs 50, a face too small
for the reframe, a tap point that lands on background, a bitrate under the floor. In the
reference run six of fifteen clips missed spec, and the build only survived because each
miss was written down with a suggested adaptation.

Mixkit needs no key but caps free video at 1080p. Pexels (`$PEXELS_API_KEY`) is where 4K
comes from. Never let a clip below canvas resolution through because it was the best
available — say so and let the user decide.

## Stage 3 — Voiceover

**Writes:** `vo/vo-manifest.json`. **Touches the timeline:** no.

Lines must fit their beat. Synthesised speech runs far faster than scripts assume —
about 240 wpm measured — so run `tts_fish.py estimate` **before** spending API calls, and
rewrite the doomed lines. When a line still overruns, shortening the words beats speeding
up the read; the reference build shipped one line cut from "Loud room behind you?" to
"Loud room?" after two failed retries.

Synthesise with Drift's `tts_generate` (ElevenLabs or Fish Audio, from the user's key in
Settings → Cloud providers; `list_voices` for ids) or `tts_fish.py` on an older build. Then
`transcribe` each line and compare the words with the script before it goes near the timeline.
Normalise every line to the mix target (−16 LUFS / −2 dBTP works) and record the actual
durations. The API key comes from the environment or Drift's settings, and is never written to a
file, a manifest or a log.

## Stage 4 — Build

**Writes:** the project, the export, `build-log.md`. **Touches the timeline:** yes, only this stage.

Follow the storyboard exactly, and when something is impossible, adapt and **log the
deviation** with the measurement that forced it. The build log is what the reviewer and
the next builder read; in the reference run it carried 23 deviations, and every one of
them turned out to matter later.

Working order that held up:

1. Project setup, background, overlap **off**, save.
2. Import everything, place the music, fix the beat grid.
3. Beat by beat, front to back: footage, then grade, then graphics, then text, then audio.
4. After each beat: `capture` the times the storyboard's Verify block names, and check what it says must be true.
5. After each section: `drift_cli.py audit`.
6. Before export: audit again, confirm the timeline duration, confirm every track's transitions are the intended ones.
7. Export with **every** setting explicit, poll, then `ffprobe` the file and measure its loudness.

## Stage 5 — Review

**Writes:** `review-vN.md` plus stills. **Touches the project:** no.

The reviewer must not be the builder. The builder has already decided each beat is fine;
that is exactly the judgement under test. In the reference run the independent reviewer
found the music burying the voice, a before/after wipe revealing the *shadow* side of a
face so the retouch read as worse, and two "different" looks differing by one code value.
None of those appear in the builder's own notes.

Review from the **exported file**, not the timeline: dense contact sheets, full stills at
each beat's key moment and at transition midpoints, and audio measured per range.

Report as a scored rubric plus prioritised, actionable items:

| Criterion | 1–5 |
|---|---|
| Colour harmony | |
| Contrast | |
| Typography | |
| Motion | |
| Clarity of the feature being shown | |
| Pacing | |
| Audio | |
| Technical quality | |

- **P0** — ships broken without this. Each item: what, where (timestamp), the measurement that proves it, and the specific fix.
- **P1** — should fix. **P2** — nice to have.
- End with a verdict: ship, fix-then-ship, or rebuild.

## Stage 6 — Fix, then review again

Hand the review back to the **same builder agent** so it keeps its project knowledge.
Ask for P0 and P1, P2 only where cheap. Require a status line per item — fixed, partially
fixed, not fixed — with the verification time or measurement. Then have the reviewer check
v2 against its own list *and* look for regressions the fixes introduced, without taking the
build log's word for anything.

Stop when the remaining items are ones the user should decide on (a substitute look, a
loudness target that needs an external master, footage that should be re-sourced) rather
than ones you can fix. List those plainly instead of quietly shipping around them.
