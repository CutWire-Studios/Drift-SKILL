# Design system template

A design system is what stops a build turning into a pile of stock presets. *Craft* below
is the judgment — identity, the looks to refuse, words on screen, motion — taken from
studio practice and from Apple's fluid-interface rules, translated into a timeline.
"Graphite & Amber" is one system that passed review on typography, contrast, palette and
"nothing looks dated". **Derive your own from the brief; use the example for structure,
and for the parts that are really about Drift** (the grade stack, the shading stacks, the
easing maths, the banned list).

## How to derive one

1. **Name the film.** Subject, audience, and its single job. If the brief leaves them open, choose and write the choice down. Palette, type, and the opening shot come from that world's materials, tools, and vernacular.
2. **Anchor the palette in something real** — a logo, a product surface, the footage you already have. Here it came from the amber in the Drift mark. Four to six named colours, with a job each.
3. **Compute contrast, do not eyeball it.** Every text colour against every background it will sit on. Text over footage is the case that fails.
4. **Pick two faces and a scale**, with tracking and leading per role. One face is monotonous, three is noise. The display face is a character; the body face reads small.
5. **Decide the motion vocabulary** — a handful of timing and easing tokens, used everywhere — before any keyframe is written. The rules those tokens have to satisfy are in *Craft* below.
6. **Name one signature and one emotion.** The signature is the single element the film is remembered by. The emotion (calm, confident, excited) is what every other token is checked against. Delight is that check passing, not a second layer of effects.
7. **Write the banned list.** It is more useful than the allowed list, because the default failure is reaching for a preset that carries its own look.
8. **Set the footage floor** (resolution, grade, what to avoid) so sourcing can be gated mechanically.
9. **Critique the plan, then build it.** Read the system as if the product were a different one in the same genre, and against the three default looks in *Craft*. Revise whatever still fits. Keyframes after that derive every colour and face from the revised plan.

---

## Craft

Judgment that sits above any one palette. The worked example further down already has the numbers this skill has measured (contrast floors, tracking, the bezier tokens). What follows is the part that decides whether those numbers describe *this* film.

### Identity

The opening shot is a thesis: the most characteristic object, gesture, or phrase in the subject's world. A large statistic, a small label, and a gradient accent is the opening a template would give any product. Use it when that statistic is the film.

Typography carries the personality. Weight, width, and tracking are part of the face, not a neutral delivery of the words. The treatment should still be recognizable in grayscale. Tracking is size-specific — the type table below tightens it as size grows, and body stays near 0. Leading goes the other way: tight on a display line, looser on a caption. Hierarchy is weight plus size plus leading together. Emphasize with weight when the line cannot afford to grow.

Structural devices encode something true about the content. A numbered marker (`01` / `02` / `03`), an eyebrow, or a divider belongs when the film is a sequence and the order is information the viewer needs. On a film that is not a sequence, they are decoration.

Match the build to the direction. A maximalist brief needs the elaborate version actually finished. A quiet brief needs exact spacing, type, and timing. One orchestrated moment lands harder than a small effect on every beat; extra motion is what makes a film read as generated. Spend the boldness in the signature, keep the surrounding beats disciplined, and remove one decoration before the board is locked.

### Defaults to refuse

Left free, a design converges on one of three looks, whatever the subject: a warm cream field near `#F4F1EA` with a high-contrast serif and a terracotta accent; a near-black field with a single acid-green or vermilion accent; a broadsheet of hairline rules, square corners, and newspaper columns. Each is legitimate when the brief, or the product's own materials, asks for it. When an axis is free, spend it on the subject. The Graphite & Amber example is a product film whose accent was taken from a real mark. Copy its structure. Copy its hex values only when this product is that product.

### Words on screen

A line is on screen to make the frame easier to understand. Write it from the viewer's side: name what they recognize and control, in the product's language rather than the implementation's. Specific beats clever. Active voice. The name of an action stays the same from the label to the result. Sentence case, plain verbs, no filler. One job per line — a label labels, an example demonstrates. An empty or failed beat tells the viewer what happens next, in the film's own voice.

### Motion

An interface feels physical when a move continues from the value already on screen, keeps the speed of whatever set it moving, and can be reversed without a jump. Drift authors that with keyframes. The easing tokens stand in for a spring's damping, and the timing table stands in for its response: `settle` is the critically damped arrival, `glide` is the on-screen move, `exit` is the leave. A move of 0.45–0.60 s is the same band as a 0.4 s response.

- **Damping by default.** Arrivals use `settle`, leaves use `exit`. No overshoot on titles, captions, fades, or anything that simply appears. A little overshoot is earned only when the picture itself was thrown — a card flicked, an object landing, a sheet that had momentum. The worked example bans bounce, elastic, and back everywhere, because nothing in that film is thrown. A later system may add one overshoot token and then spend it only on those beats. Text-animation slots still do not take `back`, `bounce`, or `elastic`.
- **Same path out as in.** A panel that enters from the right leaves to the right. An element that rises into place leaves along that rise. The exit runs about 60% as long and eases in, which the timing table already states.
- **Anchor to the source.** A callout, label, or sheet starts at the thing it describes and settles into its resting box. Growing from the centre of the canvas, away from that thing, drops the link between label and subject.
- **Telegraph the end.** The in-between frames point at the outcome: a card turning toward the feature it is about to show, a rule drawing itself toward the word it underlines.
- **Materialize.** Pair opacity with scale, never from 0 — the floor is 0.90, already in the motion principles below. A blur or glass plate animates its blur radius together with opacity, so the surface arrives as a material rather than a dissolve.
- **Weight is hierarchy.** A structural plate (a lower-third bed, a sidebar) is darker and more blurred than the chip the viewer should read. Two light translucent plates stacked on each other lose the type. A larger plate gets a stronger blur and a deeper shadow than a small pill; over busy footage the shadow goes deeper, over a flat field it goes lighter. Dim and push the background when the beat is an aside. Offset the plate without a full dim when the film stays in the same flow. Type sitting on a blurred plate is the palette's primary text colour, at a slightly heavier weight. Secondary gray on glass fails the contrast check.
- **Soft edge where the plate meets the picture.** Fade the plate out over the footage it floats on. A hard 1 px rule is the weaker form of that separation.
- **Picture and sound on one frame.** A hit, a snap, or a punched word lands on the frame the picture commits. Add a hit only where it marks a commit, an error, or an arrival.
- **Readable speed.** Check a move at 25/50/75% of its duration. If the object is a smear with no direction, shorten the distance or lengthen the move. Ease a brightness change between sections.
- **A calm or accessible brief.** Short dissolves in place of slides and parallax, no overshoot, no full-frame background that keeps moving, no pulse near one cycle every five seconds.

### Familiarity and simplicity

Things that look the same move the same way and sit in the same box on every beat. Change a pattern when the new one is clearer, and say why. Simplicity means the point of the beat is obvious. A label that tells the viewer what they are seeing can be the thing that makes a frame simple. Every spacing, timing, and alignment value is a token from this system. Review motion the way a cut is reviewed: captures at the in-betweens, not a sense that the move looked fine at full speed.

---

## Worked example: Graphite & Amber

One black, one white, one accent. The accent is used as a *line that explains* — a tap
ring, a before/after divider, a crop box, a title that draws itself — never as decoration.

### Palette

| Token | Hex | Role |
|---|---|---|
| `ink` | `#0F1218` | Canvas background, graded black point, scrim colour |
| `graphite` | `#1A1E26` | Surfaces: light pools, pill boxes |
| `slate` | `#2A2F3A` | Hairlines only. Never text |
| `paper` | `#F2F0EB` | Primary text; the only text colour allowed over footage |
| `mist` | `#9EA5B2` | Secondary text, on ink or graphite only |
| `amber` | `#FEC003` | Accent: wires, karaoke word, URL |
| `amber-deep` | `#FDA505` | Gradient partner |
| `amber-light` | `#FFE7A3` | Gradient highlight stop; never used alone |

Contrast on ink: paper 16.5:1, mist 7.6:1, amber 11.4:1, amber-deep 9.4:1.
Alpha variants are `#AARRGGBB`: scrim dense `#D90F1218`, scrim mid `#800F1218`,
scrim clear `#000F1218`, pill box `#CC1A1E26`.

### Text over footage

The rule that made the difference between the rejected pilot and the accepted build:

1. Only `paper`, plus `amber` for a karaoke accent at ≥ 64 px. Never `mist`.
2. Minimum 44 px, except pills at 28 px on their own box.
3. **Something must darken the area behind the glyphs** — exactly one of: a gradient scrim shape on the lane under the text; the plate's grade exposure pushed down ≥ 0.6 stops; or a blur plate (exposure −1.2, gaussian blur ≥ 24).
4. **Verify it.** In a `capture` at the text's midpoint, the brightest area directly behind the glyphs must be no lighter than `#4A4F58` (paper ≥ 7.2:1). If it is lighter, drop that clip's exposure in −0.2 steps to a floor of −1.0; if it still fails, change the footage.

### Footage grade

Build this stack once, `save_effect_preset` it, `apply_effect_preset` it to every footage
clip. Its job is to make *any* source resolve to the palette's black and white points, so
footage screens and design-only screens share a colour world — the specific fix for
"background and foreground colors don't match".

| fx | Effect | Params |
|---|---|---|
| 0 | `adjust_exposure` | tuned per clip, start −0.20, range [−0.8, +0.4] |
| 1 | `adjust_highlights` | −0.30 |
| 2 | `adjust_shadows` | −0.05 |
| 3 | `adjust.contrast` | 1.08 |
| 4 | `adjust.saturation` | 0.85 |
| 5 | `adjust_hsl_saturation` | red −0.15, yellow −0.05, green −0.40, aqua −0.35, blue −0.20, purple −0.60, magenta −0.60 |
| 6 | `asc_cdl` | slope 1.00/0.97/0.90, offset 0.004/0.018/0.044, power 1.0 |
| 7 | `levels` | outBlack 0.055, outWhite 0.94 |
| 8 | `film_grain` | amount 0.06, size 1.0, softness 0.4 |

Stages 6–7 land input black on `#0F1218` and input white on `#F0EDE3`. Stage 5 is what
kills the multicoloured-neon problem while leaving the amber family alone. Only fx.0 varies
per clip. Models, vector clips, stickers and text get no grade.

### Typography

Display **Outfit** (600 titles, 700 hook only), supporting **DM Sans** (400–600). No third
face, no italics, sentence case. `letterSpacing` in Drift is absolute px at `pixelSize`.

| Role | Font | Weight | px | tracking | lineHeight |
|---|---|---|---|---|---|
| Display XL (hook) | Outfit | 700 | 240 | −7 | 0.95 |
| Display L | Outfit | 600 | 160 | −4 | 1.00 |
| Title | Outfit | 600 | 96 | −2 | 1.05 |
| Subtitle (auto captions) | DM Sans | 600 | 64 | 0 | 1.20 |
| Support | DM Sans | 400 | 44 | +0.2 | 1.35 |
| Pill label | DM Sans | 500 | 28 | +0.6 | 1.00 |

Tracking tightens as size grows. Title ≤ 28 characters per line. If a capture shows a line
wider than its box, reduce `pixelSize` in −4 px steps — never tighten tracking to fit.

### Text shading stacks

Build these by hand with `set_text {style:{layers:[…]}}`, back-most first. **Do not call
`apply_text_look`**: every look carries its own palette, and that is exactly how the
rejected pilot ended up with eight unrelated colour schemes.

- **PLAIN** — one solid `paper` fill.
- **DEPTH** (hook) — a soft shade pool, not a drop shadow: `shadow` in ink, opacity 0.35, blur 60, offsetY 8, under a paper fill.
- **CAPTION** — shadow in ink, opacity 0.45, blur 28, offsetY 2, under a paper fill.
- **WIRE** (draw-on) — paper fill at opacity 0, plus an amber `stroke` width 3, `strokeAlign:"center"`, `trimStart:0`, `trimEnd:0` keyframed to 1.
- **AMBER** — one gradient fill, `oklab:true`, stops amber-deep → amber-light → amber-deep, `offsetSpeed` 0.2.
- **PILL** — PLAIN plus `boxEnabled:true`, `boxColor:"#CC1A1E26"`, `boxPadding:14`, `boxRadius:28`.

For everything else: `boxEnabled:false`, `accent:{rule:"none"}`, `wordWrap:true`.

### Layout

Title-safe 5% inset (x 96–1824, y 54–1026 at 1920×1080); content margin x 144 / 1776.
Name the boxes and reuse them so beats stay aligned:

| Box | x, y, w, h | align |
|---|---|---|
| `BOX-BL` bottom-left headline | 144, 796, 1200, 180 | left / bottom |
| `BOX-L` left-centre headline | 144, 400, 1000, 280 | left / centre |
| `BOX-C` centre display | 96, 390, 1728, 300 | centre / centre |
| `PILL-TL` / `PILL-TR` | 144 / 1536, 96, 240, 64 | left / right, top |

One idea per screen; subject and text on opposite thirds. Two pills on screen at once need
two lanes — they cannot share one.

### Motion

Principles that survived review: every motion reveals, changes state or hands over;
critically damped, no overshoot or bounce; entrances ease out, exits ease in along the
same path and run ~60% as long; nothing grows from 0 (minimum start scale 0.90, always
paired with opacity); at most two elements animating at once. Bounce is banned in this
film because nothing in it is thrown. *Craft* is the rule for a film that has a flick.

| Token | Value |
|---|---|
| title in / out | 0.60 s / 0.35 s |
| micro in / out (pills, captions) | 0.30 s / 0.25 s |
| move | 0.45–0.60 s |
| stagger word / char / element | 0.07 / 0.02 / 0.08 s |
| cut padding | text starts ≥ 0.15 s after a cut, exits ≥ 0.08 s before the next |
| minimum readable hold | 0.8 s + 0.3 s per word, fully settled |

**Easing tokens.** Text animation slots take the enum (`smooth`, `easeOut` for entrances,
`easeIn` for exits; `back`, `bounce`, `linear` banned on text). Transform, shape and effect
keys are bezier: for a segment A(t0,v0) → B(t1,v1) with T = t1−t0 and Δ = v1−v0,

| Token | A out-handle | B in-handle | Use |
|---|---|---|---|
| `settle` | (0.23·T, 1.0·Δ) | (−0.68·T, 0) | entrances, arrivals, materialising blur/exposure |
| `glide` | (0.45·T, 0) | (−0.45·T, 0) | on-screen moves, write-ons, turntables, mask wipes |
| `exit` | (0.55·T, 0) | (0, −0.55·Δ) | opacity and position exits |
| `linear` | `mode:"linear"` | — | camera push-ins, light sweeps, jitter |

`scripts/keyframes.py` implements exactly this table. Verify the first curve you build with
`list_keyframes` and captures at 25/50/75% of T: a `settle` should reach ~80% of Δ by 25%.

### Banned

- `apply_text_look` entirely; specifically `neon`, `chrome`, `shine`, `holographic`, `glitch`, `echo`, `splice`, `curve`, `outline`, `lift`, and the preset packs `fire`, `ice`, `candy`, `retro-3d`, `comic`, `rainbow`, `gold-luxe`, `sticker`.
- Any `extrude` or `glow` shading layer.
- Bounce, elastic and back easing anywhere.
- More than one accent colour; any colour not in the palette.
- Text over a subject's face, unless the design is that the subject passes in front of it.

### Footage requirements

Native resolution ≥ canvas, and ≥ canvas × the planned punch-in. Prefer 4K for anything
that will be cropped, reframed or cut out. Frame rate ≥ the slowest speed ramp needs
(a 0.3× ramp on 30 fps source stutters — 0.5× is the practical floor). Gate mechanically:
`media_qc.py check --canvas <WxH> --crop-headroom <factor> --min-fps <n>`.

Tonally: prefer material that already has a dark background and a single light source,
because the grade deepens shadows. Avoid busy multicoloured neon, visible brand logos, and
faces framed so text has nowhere to go.

### Audio

Music bed plus voice. Voice sits 8–12 LU above the ducked bed. Delivery target −14 LUFS
integrated, true peak ≤ −1 dBTP. Drift's meter now agrees with ffmpeg, but `audio_master.py`
is still the check that matters, because it measures the file you are actually shipping. `duck_under` handles this now — it takes a rest level per dip and replaces its own previous
pass rather than stacking keys — though a hand-written envelope (attack ~0.10 s, release
~0.50 s) still gives you the most control. If the target is unreachable without clipping the voice,
master the export rather than pushing the mix, and tell the user which you did.
