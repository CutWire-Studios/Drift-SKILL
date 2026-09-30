# Cartoons: characters, a world, and a story, all in Lottie

Measured on one build: "Millo, The Big Tomato", a 101 s preschool short at
1920×1080 / 30 fps. It has three bird characters, one prop, one garden, 22
voice lines, and no footage. It started from another model's build that had a
good script and voice but toddler-level art. It was rebuilt in two rounds:
first the art, then the staging after the user reviewed it. The generator is
`scripts/cartoon_lottie.py`.

## What the first build got wrong

These are the defaults to refuse. Each one is easy to produce and reads as cheap.

| Symptom | Cause | Fix |
|---|---|---|
| Characters "drawn by a toddler" | Flat circles in six colours, navy outlines, no shading | Egg body with a radial gradient, a darker outline in the same hue, big dark eyes with two highlights, blush, brows, a beak with a mouth inside |
| Boring world | A green rectangle and one circle on a flat sky colour | A layered scene with ambient motion (see *The world*) |
| Nothing moves | Its design system banned gradients, shadows, bounce, and "more than two things moving", on the belief that rlottie renders the files | Drift renders Lottie with **Skottie**: gradients, alpha gradients and bezier easing all work. A preschool film wants squash, stretch and overshoot |
| Wings cut off when spread | The character canvas was only as wide as the body | Pad the canvas (480 → 640 wide) and recompute every clip box |
| The lift looks fake | The prop was above the characters' heads and out of reach, it rose 36 px, and the "carry" was a straight x glide | Put the prop within wing reach and stage grab, strain, pop, hold, carry and put-down as separate actions |
| Step sounds off the picture | The sounds were placed on a guessed rhythm and the picture had no steps | Sounds go on the landing frames of a hop cycle |
| A line that sounds explicit | "It will not come." in a children's film | Read every line aloud as an adult would hear it. Regenerate the line (see *Voice*) |
| Titles | Navy text on sky blue with a fade | A chunky gradient display word with extrude and stroke, a letter-by-letter drop, and a ribbon behind the subtitle |

## Pipeline

1. **Script and voice first.** The measured VO takes are the clock, not the storyboard's estimates. Keep `vo/timing.md` in sync after every change.
2. **Generator.** One Python file writes every Lottie document (`cartoon_lottie.py build --out lottie/ --seconds <film length>`). Never hand-edit the JSON: every fix is a code change and a rebuild.
3. **Place** with `add_lottie`, or swap the documents under existing clips with `set_lottie_source`. The latter keeps timing, box, fit and loop mode.
4. **Verify** with `frames({at:[…]})` at every action beat, and `capture` at every contact point (wing on prop, prop on ground).
5. **Export.** Rich vectors render slowly: 101 s took about 40 min at crf 18. Poll `export_status`. Do not wait on file size, because the file stops growing long before the encode finishes.

## Character rig

One Lottie per character per action. Every action of a character shares one canvas and one foot line, so a cut between two clips in the same box never jumps.

- **Canvas.** 640×560. The body is drawn on a 480-wide grid with its feet on y = 520, then the layer is shifted right by 80. The padding exists for the wings: a wing pointing sideways from the shoulder reaches past a body-sized canvas and gets clipped.
- **Draw order**, top first:
  1. The wings, which pivot at the shoulder.
  2. The face group: glasses, eyes, happy-eyes, brows, beak, cheeks. Offset the face 10 px toward whoever the character mostly faces.
  3. The belly and the body, with a tuft or bow above or below the body as it should overlap.
  4. The feet.

  The ground shadow sits outside the root group, so a hop shrinks it instead of lifting it.
- **Root transform.** Anchor it at the feet, `(240, 520)`. Squash and stretch are then a scale on that anchor, so the feet stay planted.
- **Channels.** Each action is a dict of keyframe lists, applied onto one rig:
  - Root: `root_pos`, `root_scale`, `root_rot`.
  - Face: `eyes` (blink scale), `eyes_op`/`happy_op` (swap to ^^ eyes), `brow_y`/`brow_rot`, `jaw` (lower beak drop plus a mouth-interior scale), `cheek`.
  - Limbs: `wing_l`/`wing_r` (degrees at the shoulder), `foot_l`/`foot_r`, `tuft`, `shadow`.
- **Wing angles.** Lottie rotation is clockwise. The left wing raises with positive degrees and the right with negative. Rest ±10, point ±96, wave ±132, up ±150.

### Actions

| Action | Loop | Length | Content |
|---|---|---|---|
| idle | loop | 4 s | breathing stretch, sway, one blink, tuft lag |
| talk | loop | 2 s | jaw chatter at about 7 openings a second, head bobs, a gesturing wing on the facing side, brows up |
| walk | loop | 2 s | four hops: squash on landing, stretch on take-off, feet alternate, wings flap, shadow shrinks at the apex |
| wave / point | hold | 6–8 s | anticipation dip, overshoot into the pose, then the wave keeps waving |
| smile | hold | 8 s | swap to happy eyes, open beak, two hops, sway |
| strain | hold | 20 s | inner wing grips the prop, outer wing up, a heave every 30 frames with the beak opening on each "up" |
| hold | hold | 20 s | inner wing under the prop, a proud bounce |
| carry | loop | 2 s | hold pose plus four small hops. Landings on frames 15, 30, 45, 60 |
| put_down | hold | 10 s | crouch as the prop goes down, stand, wings to rest, beam |

**A hold clip freezes on its last frame.** Make hold documents long, 6–20 s, with live secondary motion (breathing, blinks, a small oscillation) running to the end. Then a 14 s clip is never a still. Keep loops seamless: the first and last keys must be equal.

Each action is authored in time with the others it plays against. The prop's `strain` jiggles on the characters' heave frames. The prop's `carry` rises on the characters' hop apexes, at frame 7.5 + 15k.

## Lottie traps (Skottie, Drift)

- **A fill or stroke paints every path before it in its group, child groups included.** A body outline listed after a "rim highlight" group also stroked that highlight and filled its open path. The same happened to a tomato's specular, the lawn's grass tufts and the flower heads. Wrap each shape and its own paint in its own group, always.
- **Drift caches a document by path.** Regenerating the JSON changes nothing on the timeline. Re-issue `set_lottie_source` for every clip after each rebuild. For 70+ clips, generate the op list from the project file (below) and expect the reply to overflow into a file. Check `ok` and `n` there.
- **`inspect_lottie` is an op, not a tool.** Call it through `apply`. Its `unsupported` list caught a path that had been wrapped twice ("Could not parse (explicit) static property").
- **Resizing a canvas moves everything.** Clip boxes are contain-fit, so a wider canvas shrinks the character. Keep the scale `s = min(w/480, h/560)`, then set `w' = 640·s` and `x' = x − 80·s`, and apply the same shift to **every keyframe value of x**. `cartoon_lottie.py box --w --h` prints where the feet, shoulders and body edges land inside a box.
- A text clip that already has settle keyframes on x, y, width, height and opacity fights a text-animation preset. Remove the start and end keys (`remove_keyframe` at the exact times) and keep the middle one.

### Reading the project file

`*.drift` is `DRIFTPRJ` plus a header, then a zstd frame. Find the magic bytes `28 b5 2f fd` and pipe from there through `zstd -d`. The JSON has `document.tracks[].clips[]`, with `vector.path`, `vector.loop`, `timelineStartUs`, and `x/y/width/height.keyframes[]` (times relative to the clip). One read gives every clip's box and keys, so the swap and the box conversions can be generated rather than inspected clip by clip. `save_project` first, so the file is current.

## Staging an interaction

Characters doing something with a prop is where a cartoon reads as real or fake.

1. **Compute contact, don't eyeball it.** From the rig: shoulder screen point = box x + (shoulder x + pad)·s, and wing tip = shoulder + 134·s·(−sin θ, cos θ). Place the prop so the tip lands on it. The prop's centre comes from its box as `y + 222·(220/360)` at rest.
2. **The prop within reach.** The tomato first hung high in the bush, above the birds' heads. It moved to the base of the plant, and the birds stand touching it.
3. **Beats, one clip each.** Walk to it → strain (the prop jiggles on each heave, "Up, up, up" on the heaves) → pop free on the sound cue (y keys: up past the target, then settle) → hold → carry (all three clips hop together, with x keys over the same span) → put down (the characters crouch while the prop's y key drops) → react.
4. **Draw order is track order.** The prop is on a lower track, so it passes behind the characters. Set it down *in front of their feet*, lower on screen, not between their bodies, where it vanishes.
5. **Sound on the commit frame.** Put step sounds on the hop landings (carry from 78.0 s → 78.5, 79.0, 79.5, 80.0). The "boop" is the pop.

## The world

One 1920×1080 Lottie, as long as the film (`--seconds`), placed from 0 to the end so the title and end card sit in the same place. Layers, top first:

1. Foreground grass and flowers in the corners.
2. Butterflies on waypoints every 2 s, with wing flaps every 6 frames.
3. The plant (scalloped leaf clumps, a stake, small fruit, blossoms).
4. A flower row along the fence.
5. Soil, then lawn: a gradient, mowing patches, grass tufts.
6. A picket fence, then near hills with lollipop trees, then far hills.
7. Clouds drifting linearly over the whole film.
8. The sun: a pulsing alpha-gradient glow and rotating rays.
9. A gradient sky.

Ambient motion is cheap and makes the frame feel alive. The characters still carry the attention.

## Titles and end card

- **Show name:** Fredoka 700 at ~300 px. Layers, back to front:
  - a shadow (blur 18, y 26, 35%);
  - an extrude in a darker orange (18 px, 90°);
  - a dark stroke, outside;
  - a fill with a vertical gradient from light to deep yellow-orange.

  Animate in with `drop` by character (stagger 0.09) and out with `pop`.
- **Episode title:** white text with a dark red outside stroke on a red ribbon, drawn in the title-card Lottie (the ribbon scales in with `back`). `pop` by word, delayed until the ribbon has landed.
- **Title card Lottie:** a rotating sunburst, a glow, the ribbon, twinkling sparkles, and a layer fade at the end. Add the main character waving (`slideLeft` with `back`) and the prop wobbling (`pop`), both with a fade-out of 0.35 s. Give the first story clips `animIn: pop` so the cut into scene 1 lands.
- **End card:** a rounded cream panel pops in, with confetti falling and spinning, and the words rise in by word. Split the fill gradient hard at mid-word to colour the brand name.

## Voice

- Screen a children's script as an adult listener would, for double meanings, before synthesis and again after.
- To replace one line, run `tts_generate({provider:"fish", voice:<same id>, speed:<same>, text})` and poll `get_job`. Then delete the old clip, `place_clip` the new asset at the same time, and copy the clip's `volume`. The talk clip under it may need a trim if the length changed. Copy the MP3 into `vo/` and update the script, storyboard and timing docs.
- The talk action's jaw loop is generic lip-flap. Put talk clips exactly over the voice clips, and put idle in the gaps.

## Checklist before export

- [ ] Every action clip's source was re-set after the last rebuild.
- [ ] Frames at each interaction beat, plus captures at the contact points.
- [ ] No wing or limb clipped at its widest pose (`capture` during point, wave, strain).
- [ ] Every sound effect lands on a frame where the picture commits.
- [ ] The prop's resting place is visible in front of the characters.
- [ ] The script has been read aloud for double meanings.
- [ ] The export is polled to `Export complete`, then checked with `ffprobe` (duration, both streams, frame count).
