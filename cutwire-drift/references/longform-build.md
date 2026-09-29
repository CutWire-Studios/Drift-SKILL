# A long film, rebuilt from a script

Measured on one 9:53 explainer (1920×1080 @ 30, about 284 clips, 36 Lottie scenes,
11 screen-recording cards, 4 music tracks, 77 voiceover lines, one independent
review). The picture was placed by a Python builder over `scripts/drift_cli.py`,
then thrown away and rebuilt when the lane map or the timing changed. Read
`SKILL.md` for the op traps that are still current (overlap and `placed`,
image tracks, `inspect({cues:true})`, `duck_under` between short lines,
`seek`). The birth-key animation is fixed; see the Was/Now table there. This
file is the method around what remains.

## What to do before any scene exists

Spend the first hour on a throwaway project. `new_project` clears undo, so this
is not the film.

1. `inspect`. Schema `set_transform` (confirm `rotationX` if you will tilt), `seek`, `add_lottie`, `add_text`, `set_text_animation`, `place_clip`, `export_video`.
2. One diagram with outlined text, imported and captured. Fix layer order here.
3. One screen recording baked into an alpha window card, placed, tilted (`perspective` 2000, a modest `rotationY` / `rotationX`), captured.
4. One Drift text clip with the presets you actually intend. This build used `rise-by-word`, `blur-in`, `fade-up-char` and `fade-shift`. Confirm the names with `list_text_animations` on the build you are driving.
5. Then write the design system and the storyboard. Authoring dozens of scenes before the kit renders is how a day disappears.

`set_text` carried the type by hand: `pixelSize`, `fontWeight`, `color`,
`letterSpacing`, `lineHeight`, `fontFamily`, `align`, `valign`, `wordWrap`,
and a fill layer. Box captions used `boxEnabled`, `boxColor`, `boxPadding`,
`boxRadius`. Colours were `#AARRGGBB`. No `apply_text_look`.

## Who talks to Drift

The permission boundary is in `production-pipeline.md`: one timeline writer,
and file-authoring agents do not open the editor. What that looked like here:

- Each scene agent owned its scripts and its Lottie JSON, appended a short report to the shared log, and wrote preview PNGs under a unique scratch name. It did not edit the shared kit.
- Card and wall renders ran at the same time. They are ffmpeg.
- The reviewer read the export and wrote `review-vN.md`.
- The builder ran after those files existed.

Offline preview is what makes the "do not open Drift" rule workable. An agent
that checks one frame in the editor races the builder.

## The clock and the parts

One module maps a scene id to a start time by summing durations. Captions, the
builder and the review timestamps all import it. Changing a scene's length is
one number and a rebuild.

Split the builder into parts: `setup`, then the picture front to back, then
voiceover last. A narration change re-runs the voiceover part. A lane-map
change re-runs everything, because track indexes are the map.

The builder refuses a lane overlap itself (intervals closed at about 1 ms)
instead of letting Drift gap-push a clip. `apply` in chunks of about 200.
On failure, read `inspect` and continue from what landed; do not replay the
chunk. `apply` is not atomic.

`place_clip` is followed by `set_trim` (`in` / `out` in source seconds, `out`
= in + duration × speed) and, when needed, `set_clip_speed`. Check
`placed` against `requested` and abort on a mismatch. A 0.01× "hold" is the
wrong freeze — export a PNG of that frame and place the image.

Text was created at a park time past the end of the film, then
`move_to_track` to the real lane and time, then `set_duration` and `set_text`.
`add_text` still takes no `track`. With overlap off it will not open a new
lane the way `add_shape` does; a second title at a busy time is pushed to the
next gap.

Keyframes go through `scripts/keyframes.py` (`linear` on x / y / width / height,
`glide` on rotation). `set_transform` takes `w` / `h`. The key names are
`width` / `height`.

## Lanes

Decide the full stack in `setup`, before the first clip. `add_track` inserts
at index 0, so add the desired types from the bottom of the stack upward, then
delete the default tracks that were pushed to the end. Assert the type list
equals the map. This film's stack, top to bottom:

- several text lanes (a caption, a headline, and enough extra lines that a six-line list can be on screen at once)
- shape lanes for titles' graphics and for still images
- several video lanes
- two shape lanes for diagrams that must overlap across a cut
- video lanes for full-frame footage
- a background shape
- two voice lanes and two music lanes

Adding a lane after clips exist renumbers every index the builder stored.
That is a rebuild, not an edit.

Two diagram lanes are what remove the empty-canvas dip. Review of the first
cut found 34 gaps of 0.3–0.9 s where one Lottie had exited and the next had
not started. The fix that shipped: start the next diagram about 0.3 s early
on the free diagram lane and lengthen it by the same amount, with
`add_lottie` `loop:"hold"`.

`loop:"hold"` is also what keeps a section icon on screen for the whole title
card. An icon that finishes its own loop leaves an empty tile while the Drift
title is still up.

## Lottie, authored as files

One script per scene writes one JSON at the project fps and a transparent
background. The canvas colour comes from `set_background` in Drift. Scene time
0 is the scene start. Headlines, kickers and captions are Drift text, so a
person can edit them later. Lottie text is for labels that belong to the
diagram. Leave the regions the storyboard reserved for Drift text empty in
the JSON.

Layer order is front-first. Drawing a card after its label covers the label.
A helper that accepts painter's order has to reverse on the way out.

Diagram text that must stay crisp is outlined (fontTools + uharfbuzz), not a
live font inside the JSON. Icons are SVG contours converted to paths and
recoloured. A downloaded icon Lottie is often a tiny glyph in a large canvas —
measure the bounds and scale it, or it arrives as a speck.

System Python usually lacks fontTools, uharfbuzz, svgelements, Pillow and
rlottie. Run the authoring scripts with `uv run --with` those packages. Do
not install them into the OS interpreter.

Preview with rlottie and read the PNG. Budget a handful of iterations per
scene, then stop. rlottie does not draw drop shadows or blur; a missing
shadow in the preview is not a bug. Stroke-heavy icons can also disagree with
the Skottie Drift renders with. When the contours are correct and only the
preview looks wrong, capture the clip in Drift before changing the kit.

Motion that survived review: entrances about 0.6 s, ease-out, a 20–24 px rise,
scale from about 94 rather than from 0, no overshoot, at most two things
moving, exits about 0.35 s. A scene either holds its last frame for the next
scene or has cleared itself in the last 0.4 s. Say which in the scene report.

Complex scripts need a font that shapes them, and a look at the preview.
Sinhala and Tamil set in a Latin font are blank or boxes.

## Screen recordings

Look at the first frames before you cut. A recorder overlay ("Spectacle is
Recording") covered the first ~4.5 s of every desktop capture in this film;
cards started at 4.6 s or later.

Two devices recorded at the same time will not share a zero. Match a visible
event — the frame a message appears in both — and store the offset. File
start times are not that offset. When both must be on screen and legible,
crop to the pane that matters rather than showing two full desktops.

Bake the chrome in ffmpeg, then place one clip:

- Rounded window or phone bezel, title bar, shadow, on transparent padding.
- Codec FFV1, `yuva420p`. VP9 was too slow on flat UI. The cost is disk: 11 cards were 2.4 GB, the card directory about 3.2 GB.
- Duration is always explicit, on the output and derived from the source (`ffprobe` duration minus start, minus a short tail). `-loop 1` stills used as overlays never end. `shortest=1` in the filter did not stop a graph whose mask input was looping. The encode grows without bound; kill it and delete the partial.
- A wall of many live tiles is one plate, larger than the canvas, that Drift pans and tilts. It is not twenty clips.

## Music and voice

Measure each music file's integrated loudness before you set `set_volume`.
Give the tracks two lanes, overlap them by about 1.5 s, and fade both so a
section change is not a level jump. Review caught a ~7 LU hole at one
boundary. Trim into a track so a strong beat lands on a visual hit, and so
the last track's own ending is the film's ending.

Voice lines are short clips, one per sentence, on two audio lanes so
neighbours can overlap by a few tens of milliseconds if they must. Estimate
duration against a measured words-per-minute for **this** voice before
synthesising the batch — the 240 wpm figure in the pipeline is a different
voice. Speak a test line, then the rest. Manifest paths came back relative
and broke `import_media` after the picture was already built; resolve them
to absolute paths.

`duck_under` (amount 0.35, attack 0.2 s, release 0.7 s) let the bed rise
between sentences. The mix that shipped set the music once, about 12 LU under
a −16 LUFS voice, and left it. After export, `audio_master.py windows` on
speech ranges versus gaps is the check. This film's narration measured about
14 LU above the bed.

Integrated loudness can be on target while true peak is hot (−0.2 dBTP here,
against a −1.5 ceiling). Master the **file** with `audio_master.py master`
and say that the project itself was not re-mixed. The export that matched the
timeline passed every field: `video:"h264"`, `audio:"aac"`, `audio_bitrate:256`,
`rate:"crf"`, `crf:18`, `preset:"medium"`, `fps:0`, `height:0`, `scale:"source"`,
`audio_only:false`, `gif:false`, `work_area:false`. Poll `inspect().export.active`,
then `ffprobe` the file.

Keys stay in the environment or in Drift's cloud-provider settings. A key
written into a shell command is stored in the session transcript.

## Checking words you cannot hear

`generate_subtitles` on a voice lane (poll `inspect` detail `jobs.subtitleGen`)
produces cues you can diff against the script. A word-level ratio near 1 with
a handful of substitutions is the result to expect; flag those lines for a
re-listen or a re-speak. Whisper in this build heard "outage" as "out is" and
a proper name as a different word — either a mis-hear or a real
mispronunciation, and the line files are how you redo one of them.

Delete the generated clips by track type `subtitle`, then remove those tracks
if they are empty. Count before and after. `inspect({clips:true, cues:true})`
still returns `subtitleCues: []` on every clip; `detail:true` is what omits
the empty array. A history label of `delete_clip` plus a large "more" is the
moment to undo rather than save. `list_history` returns the newest 20 unless
you pass `limit`.

## What review is for, on an explainer

The rubric in `production-pipeline.md` still applies. The misses that were
not about taste:

- A step caption that described a later moment in the recording (the booking shown as already done while the phone was still asking for a date).
- A claim about who is on screen that the frames did not support.
- Captions that left before they could be read.
- Footage of test data sitting next to a polished mock of the same screen, with nothing saying which was which.
- A recorder overlay, and a diagram that invented a log, a chat or a config file. Label illustrations as illustrations.

Sample the storyboard's verify times as one contact sheet (capture, tile,
label with the requested time) and read that image. One sheet per section
beats one read per frame.

## Speed, in the order that mattered

- Feasibility spike, then documents, then parallel file work, then one builder.
- Do not wait on a render by chaining `sleep`. An `until` on the file, the log, or `inspect().export.active` is the wait.
- Re-run a part when only that part failed. Re-run `all` when the lane map, the snap setting, or the timing module changed.
- Save after a section that `inspect` and `audit` agree with, not after a surprising delete.
- Say what you did not hear and did not watch. Loudness, a word diff, and stills are the evidence. Playback is the user's.
