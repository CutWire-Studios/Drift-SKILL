#!/usr/bin/env python3
"""Generate a cartoon kit as Lottie files for Drift: characters, a prop, a scene, title and end cards.

Built for "Millo, The Big Tomato" (a preschool short) and kept as a working
starting point. It is a rig generator, not an asset pack: edit the cast, the
prop, and the scene functions for a new film. See references/cartoon-build.md.

What it writes (all 30 fps, rendered by Skottie in Drift):

- <name>_<action>.json per character, 640x560. The rig is drawn on a 480-wide
  grid, feet on y=520, body centred on x=240, then shifted right by BIRD_PAD=80
  so raised and pointing wings stay inside the canvas.
  Actions: idle, talk, walk (loops); wave, wings_up, point, smile, strain,
  hold, carry (loop), put_down (hold on the last frame, 6-20 s of live motion).
- <prop>_<action>.json, 360x360, fruit centre (180, 222): rest (loop),
  wobble, lifted, strain, carry (loop), ground. Height comes from the clip box.
- garden.json 1920x1080, --seconds long: sky, sun, clouds, hills, trees,
  fence, flowers, a plant, butterflies. title_card.json, end_card.json.

Usage:
  cartoon_lottie.py build --out lottie/ [--cast cast.json] [--seconds 101]
  cartoon_lottie.py box --w 340 --h 420       # clip-box maths for the 640x560 rig

--cast replaces the built-in cast (Millo, Lolo, Nana). One object per
character, keys as in BIRDS below: hi/base/shade/line colours, belly, wing,
beak, beak_line, cheek, eye [w,h], facing (1 right, -1 left),
tuft (three|curl|bow), glasses, wave/point/inner (l|r: the wing toward the
other character or the prop).

Lottie rules this file depends on:
- Inside a group the first item draws on top.
- A fill or stroke paints every path listed before it in the same group,
  including paths inside child groups. Put each shape with its own paint in its
  own group, or one outline will stroke the highlights and details too.
- Keyframes carry the easing of the segment that starts at them.
"""

from __future__ import annotations

import json
import math
import argparse
import random
import sys
from pathlib import Path

OUT = Path.cwd()
FPS = 30

# The rig is drawn on a 480-wide grid and shifted right by BIRD_PAD so raised
# and pointing wings stay inside the canvas.
BIRD_W, BIRD_H = 640, 560
BIRD_PAD = 80
CX, FOOT_Y = 240, 520
TOMATO_SIZE = 360
W, H = 1920, 1080
GARDEN_FRAMES = 101 * FPS  # set by --seconds

EASES = {
    "io": (0.45, 0, 0.55, 1),
    "out": (0.33, 1, 0.68, 1),
    "in": (0.32, 0, 0.67, 0),
    "back": (0.34, 1.56, 0.64, 1),
    "lin": (0, 0, 1, 1),
}


# ---------------------------------------------------------------- primitives


def rgb(hex_color: str) -> list[float]:
    h = hex_color.lstrip("#")
    return [round(int(h[i : i + 2], 16) / 255, 4) for i in (0, 2, 4)]


def rgba(hex_color: str) -> list[float]:
    return rgb(hex_color) + [1]


def r2(v):
    if isinstance(v, (list, tuple)):
        return [r2(x) for x in v]
    return round(v, 2)


def prop(value):
    return {"a": 0, "k": r2(value)}


def anim(keys):
    """keys: [(frame, value, ease)]; ease shapes the segment to the next key."""
    if keys is None:
        return None
    if len(keys) == 1:
        return prop(keys[0][1])
    frames = []
    last = len(keys) - 1
    for i, key in enumerate(keys):
        t, value = key[0], key[1]
        ease = key[2] if len(key) > 2 else "io"
        v = value if isinstance(value, (list, tuple)) else [value]
        frame = {"t": round(t, 2), "s": r2(list(v))}
        if i != last:
            if ease == "hold":
                frame["h"] = 1
            else:
                x1, y1, x2, y2 = EASES[ease]
                frame["o"] = {"x": [x1], "y": [y1]}
                frame["i"] = {"x": [x2], "y": [y2]}
        frames.append(frame)
    return {"a": 1, "k": frames}


def pk(value, default):
    """A static value, a keyframe list, or None (the default)."""
    if value is None:
        return prop(default)
    if isinstance(value, list) and value and isinstance(value[0], tuple):
        return anim(value)
    return prop(value)


def xform(pos=None, anchor=None, scale=None, rot=None, opacity=None):
    return {
        "ty": "tr",
        "p": pk(pos, [0, 0]),
        "a": pk(anchor, [0, 0]),
        "s": pk(scale, [100, 100]),
        "r": pk(rot, 0),
        "o": pk(opacity, 100),
        "sk": prop(0),
        "sa": prop(0),
    }


def fill(color: str, opacity=100):
    return {"ty": "fl", "c": prop(rgba(color)), "o": pk(opacity, 100), "r": 1}


def grad(stops, start, end, radial=False, opacity=100, alphas=None):
    """stops: [(pos, hex)]. alphas: optional [(pos, 0..1)]."""
    k = []
    for pos, color in stops:
        k += [pos, *rgb(color)]
    if alphas:
        for pos, a in alphas:
            k += [pos, a]
    return {
        "ty": "gf",
        "o": pk(opacity, 100),
        "r": 1,
        "g": {"p": len(stops), "k": prop(k)},
        "s": prop(list(start)),
        "e": prop(list(end)),
        "t": 2 if radial else 1,
        "h": prop(0),
        "a": prop(0),
    }


def stroke(color: str, width: float, opacity=100):
    return {
        "ty": "st",
        "c": prop(rgba(color)),
        "o": pk(opacity, 100),
        "w": prop(width),
        "lc": 2,
        "lj": 2,
        "ml": 4,
    }


def ellipse(cx, cy, w, h):
    return {"ty": "el", "d": 1, "p": prop([cx, cy]), "s": prop([w, h])}


def rect(cx, cy, w, h, r=0):
    return {"ty": "rc", "d": 1, "p": prop([cx, cy]), "s": prop([w, h]), "r": prop(r)}


def smooth(points, closed=True, k=1 / 6):
    """Catmull-Rom through the points, as a Lottie bezier."""
    n = len(points)
    ins, outs = [], []
    for i in range(n):
        if closed:
            p0, p2 = points[(i - 1) % n], points[(i + 1) % n]
        else:
            p0 = points[max(i - 1, 0)]
            p2 = points[min(i + 1, n - 1)]
        tx, ty = (p2[0] - p0[0]) * k, (p2[1] - p0[1]) * k
        if not closed and i in (0, n - 1):
            tx = ty = 0
        outs.append([tx, ty])
        ins.append([-tx, -ty])
    return {"c": closed, "v": r2([list(p) for p in points]), "i": r2(ins), "o": r2(outs)}


def poly(points, closed=True):
    zeros = [[0, 0] for _ in points]
    return {"c": closed, "v": r2([list(p) for p in points]), "i": zeros, "o": zeros}


def path(shape):
    return {"ty": "sh", "ks": {"a": 0, "k": shape}}


def group(name, items, tr=None):
    return {"ty": "gr", "nm": name, "it": [*items, tr or xform()]}


def leaf_pts(length, width, bend=0.0):
    """Teardrop from (0,0) to (0,-length)."""
    return [
        (0, 0),
        (width * 0.5 + bend, -length * 0.35),
        (width * 0.28 + bend * 1.4, -length * 0.75),
        (bend * 1.6, -length),
        (-width * 0.28 + bend * 1.4, -length * 0.75),
        (-width * 0.5 + bend, -length * 0.35),
    ]


def star_pts(r_out, r_in, n=4):
    pts = []
    for i in range(n * 2):
        a = math.pi * i / n - math.pi / 2
        r = r_out if i % 2 == 0 else r_in
        pts.append((r * math.cos(a), r * math.sin(a)))
    return pts


def shape_layer(name, shapes, op, ks=None, ind=1):
    base = {
        "o": prop(100),
        "r": prop(0),
        "p": prop([0, 0, 0]),
        "a": prop([0, 0, 0]),
        "s": prop([100, 100, 100]),
    }
    if ks:
        base.update(ks)
    return {
        "ddd": 0,
        "ind": ind,
        "ty": 4,
        "nm": name,
        "sr": 1,
        "ks": base,
        "ao": 0,
        "shapes": shapes,
        "ip": 0,
        "op": op,
        "st": 0,
        "bm": 0,
    }


def comp(name, width, height, layers, op):
    for i, layer in enumerate(layers):
        layer["ind"] = i + 1
    return {
        "v": "5.7.1",
        "fr": FPS,
        "ip": 0,
        "op": op,
        "w": width,
        "h": height,
        "nm": name,
        "ddd": 0,
        "assets": [],
        "layers": layers,
    }


# ---------------------------------------------------------------- motion kit


def osc(total, period, amp, base=0.0, start=0, first_up=True):
    """Sine-like swing around base from `start` to `total`, starting and ending at base."""
    keys = [(0, base, "io")] if start > 0 else []
    keys.append((start, base, "out"))
    t = start + period / 4
    sign = 1 if first_up else -1
    while t < total - period / 4 + 0.01:
        keys.append((t, base + sign * amp, "io"))
        sign = -sign
        t += period / 2
    keys[-1] = (keys[-1][0], keys[-1][1], "in")
    keys.append((total, base))
    return keys


def osc2(total, period, amp, base, start=0):
    """osc for 2D values: amp and base are pairs."""
    keys = osc(total, period, 1.0, 0.0, start)
    return [(t, [base[0] + v * amp[0], base[1] + v * amp[1]], *e) for t, v, *e in keys]


def then(intro, tail):
    """Intro keys, then tail keys shifted to start where the intro ended."""
    return intro + tail[1:]


def blinks(total, at, base=100.0):
    keys = [(0, [100, base])]
    for b in at:
        keys += [
            (b - 2, [100, base]),
            (b + 1, [100, 8]),
            (b + 3, [100, 8]),
            (b + 6, [100, base]),
        ]
    keys.append((total, [100, base]))
    return keys


def remap(keys, fn):
    return [(k[0], fn(k[1]), *k[2:]) for k in keys]


# ---------------------------------------------------------------- birds

BIRDS = {
    "millo": {
        "hi": "#FFF6B0",
        "base": "#FFD93A",
        "shade": "#F0A012",
        "line": "#B86E08",
        "belly": ("#FFFDEB", "#FFE8A0"),
        "wing": ("#FFE670", "#F2A91C"),
        "beak": ("#FFB347", "#F2701A"),
        "beak_line": "#B04E0C",
        "cheek": "#FF7F9E",
        "eye": (60, 74),
        "facing": 1,
        "tuft": "three",
        "wave": "r",
        "point": "r",
        "inner": "r",
    },
    "lolo": {
        "hi": "#FFC890",
        "base": "#FF9446",
        "shade": "#E0602A",
        "line": "#9E3C16",
        "belly": ("#FFF8D6", "#FFDA7A"),
        "wing": ("#FFA864", "#DC5A26"),
        "beak": ("#FFD24A", "#F29A1A"),
        "beak_line": "#A35A0A",
        "cheek": "#FF5E8A",
        "eye": (58, 72),
        "facing": -1,
        "tuft": "curl",
        "wave": "l",
        "point": "l",
        "inner": "l",
    },
    "nana": {
        "hi": "#FFFFFA",
        "base": "#FBE6C6",
        "shade": "#E2B784",
        "line": "#9C6B3E",
        "belly": ("#FFFFFF", "#FFF1DC"),
        "wing": ("#FCEBD2", "#DDAF7A"),
        "beak": ("#FFC24B", "#EE8E1C"),
        "beak_line": "#A35A0A",
        "cheek": "#FF8FA8",
        "eye": (50, 60),
        "facing": -1,
        "tuft": "bow",
        "glasses": True,
        "wave": "l",
        "point": "l",
        "inner": "l",
    },
}

BODY_PTS = [
    (240, 116),
    (352, 158),
    (404, 290),
    (386, 420),
    (320, 498),
    (240, 512),
    (160, 498),
    (94, 420),
    (76, 290),
    (128, 158),
]
EYE_Y = 258
EYE_DX = 58
SHOULDER = {"l": (94, 296), "r": (386, 296)}
WING_L = [(0, -8), (20, 28), (18, 92), (0, 134), (-24, 116), (-32, 56), (-20, 8)]
REST = {"l": 10, "r": -10}
UP = {"l": 150, "r": -150}
POINT = {"l": 96, "r": -96}
WAVE = {"l": 132, "r": -132}


def default_channels(total):
    return {"total": total}


def bird_actions(c):
    """Channel keyframes per action. Rotations are degrees, positions px, scales %."""
    wave_s, point_s = c["wave"], c["point"]
    other = {"l": "r", "r": "l"}
    acts = {}

    # idle: breathing, sway, blink, tuft lag. Seamless 4 s loop.
    n = 120
    acts["idle"] = {
        "total": n,
        "root_scale": osc2(n, 60, [-1.2, 1.8], [100, 100]),
        "root_rot": osc(n, 120, 1.4),
        "tuft": osc(n, 60, 5, first_up=False),
        "eyes": blinks(n, [84]),
        "wing_l": osc(n, 60, 3, REST["l"]),
        "wing_r": osc(n, 60, -3, REST["r"]),
    }

    # talk: beak chatter, head bobs, a gesturing wing on the facing side. 2 s loop.
    n = 60
    jaw = [0, 12, 3, 13, 2, 11, 0, 0, 12, 4, 13, 2, 10, 0, 0]
    jt = [0, 4, 8, 12, 16, 21, 26, 30, 34, 38, 42, 47, 52, 56, 60]
    jaw_keys = [(t, v) for t, v in zip(jt, jaw)]
    bob = [(0, [0, 0]), (8, [0, -7]), (16, [0, 0]), (24, [0, -5]), (32, [0, 0]),
           (40, [0, -7]), (48, [0, 0]), (60, [0, 0])]
    gest = "r" if c["facing"] > 0 else "l"
    gsign = -1 if gest == "r" else 1
    acts["talk"] = {
        "total": n,
        "jaw": jaw_keys,
        "root_pos": bob,
        "root_scale": remap(bob, lambda v: [100 - v[1] * 0.25, 100 + v[1] * 0.3]),
        "root_rot": [(0, 0), (20, 2.5), (40, -2), (60, 0)],
        "brow_y": [(0, 0), (10, -8), (32, -8), (42, 0), (60, 0)],
        f"wing_{gest}": [
            (0, REST[gest]),
            (15, REST[gest] + gsign * 34),
            (30, REST[gest] + gsign * 18),
            (45, REST[gest] + gsign * 38),
            (60, REST[gest]),
        ],
        f"wing_{other[gest]}": osc(n, 30, (4 if gest == "r" else -4), REST[other[gest]]),
        "tuft": osc(n, 20, 6),
        "eyes": blinks(n, [44]),
    }

    # walk: four bouncy hops per 2 s loop, squash on landing, wings flap.
    n = 60
    pos, scl, fl, fr, shd, wl, wr, tuft, rot = [], [], [], [], [], [], [], [], []
    for h in range(4):
        t0 = h * 15
        pos += [(t0, [0, 0], "out"), (t0 + 7.5, [0, -30], "in")]
        scl += [(t0, [107, 93]), (t0 + 3, [96, 105]), (t0 + 7.5, [100, 100]), (t0 + 12, [98, 103])]
        lift = [(t0, [0, 0]), (t0 + 7.5, [0, -12]), (t0 + 15, [0, 0])]
        (fl if h % 2 == 0 else fr).extend(lift[:-1])
        (fr if h % 2 == 0 else fl).extend([(t0, [0, 0])])
        shd += [(t0, [100, 100]), (t0 + 7.5, [78, 78])]
        wl += [(t0, REST["l"]), (t0 + 7.5, REST["l"] + 34)]
        wr += [(t0, REST["r"]), (t0 + 7.5, REST["r"] - 34)]
        tuft += [(t0 + 3, -9), (t0 + 10, 9)]
        rot += [(t0 + 7.5, 3 if h % 2 == 0 else -3)]
    end = n
    acts["walk"] = {
        "total": n,
        "root_pos": pos + [(end, [0, 0])],
        "root_scale": scl + [(end, [107, 93])],
        "foot_l": fl + [(end, [0, 0])],
        "foot_r": fr + [(end, [0, 0])],
        "shadow": shd + [(end, [100, 100])],
        "wing_l": wl + [(end, REST["l"])],
        "wing_r": wr + [(end, REST["r"])],
        "tuft": [(0, -9)] + tuft + [(end, -9)],
        "root_rot": [(0, 0)] + rot + [(end, 0)],
    }

    # wave: anticipation squat, a hop, then a wing that keeps waving. Holds 6 s.
    n = 180
    s = wave_s
    sg = -1 if s == "r" else 1
    wave_keys = [(0, REST[s], "in"), (5, REST[s] - sg * 10, "back"), (14, WAVE[s], "io")]
    t, up = 14, True
    while t + 9 <= n:
        t += 9
        wave_keys.append((t, WAVE[s] + sg * (22 if up else -12), "io"))
        up = not up
    wave_keys.append((n, WAVE[s]))
    lean = 4 * (1 if s == "r" else -1)
    acts["wave"] = {
        "total": n,
        f"wing_{s}": wave_keys,
        f"wing_{other[s]}": [(0, REST[other[s]]), (14, REST[other[s]] - sg * 8), (n, REST[other[s]] - sg * 8)],
        "root_pos": [(0, [0, 0]), (5, [0, 8], "out"), (14, [0, -18], "in"), (22, [0, 0]), (n, [0, 0])],
        "root_scale": then(
            [(0, [100, 100]), (5, [106, 94]), (14, [96, 105]), (22, [104, 96]), (28, [100, 100])],
            osc2(n, 40, [-1, 1.5], [100, 100], start=28),
        ),
        "root_rot": then([(0, 0), (14, lean)], osc(n, 72, 2.5, lean, start=14)),
        "jaw": [(0, 0), (12, 7), (n, 7)],
        "brow_y": [(0, 0), (10, -7), (n, -7)],
        "tuft": osc(n, 18, 7),
        "eyes": blinks(n, [76, 150]),
        "cheek": [(0, 55), (14, 90), (n, 90)],
    }

    # wings_up: anticipation, both wings shoot up with overshoot, then an effort wobble. Holds 20 s.
    n = 600
    acts["wings_up"] = {
        "total": n,
        "root_pos": [(0, [0, 0]), (5, [0, 10], "out"), (13, [0, -12], "in"), (20, [0, 0]), (n, [0, 0])],
        "root_scale": then(
            [(0, [100, 100]), (5, [106, 94]), (13, [96, 105]), (20, [100, 100])],
            osc2(n, 30, [1.4, -1.6], [100, 100], start=20),
        ),
        "wing_l": then([(0, REST["l"]), (5, REST["l"] - 8, "back"), (14, UP["l"] + 14), (22, UP["l"])],
                       osc(n, 20, 6, UP["l"], start=22)),
        "wing_r": then([(0, REST["r"]), (5, REST["r"] + 8, "back"), (14, UP["r"] - 14), (22, UP["r"])],
                       osc(n, 20, -6, UP["r"], start=22)),
        "brow_rot": [(0, 0), (12, 14), (n, 14)],
        "brow_y": [(0, 0), (12, 5), (n, 5)],
        "eyes": blinks(n, [150, 330, 480], base=86),
        "tuft": osc(n, 20, 6),
        "root_rot": osc(n, 90, 1.5),
    }


    # The shared tomato lift. `inner` is the wing on the tomato side; it hugs the
    # fruit low (grip), pushes up on each heave, and sits under it once lifted.
    inner = c["inner"]
    outer = other[inner]
    sgn = -1 if inner == "r" else 1
    grip, push, under, low = sgn * 118, sgn * 138, sgn * 155, sgn * 100

    # strain: grab the tomato and heave in time with "Up, up, up". Holds 20 s.
    n = 600
    pos, scl, win, wout, jaw = [(0, [0, 0])], [(0, [100, 100])], [(0, REST[inner]), (10, grip)], [(0, REST[outer]), (10, UP[outer])], [(0, 0)]
    c0 = 12
    while c0 + 30 <= n:
        pos += [(c0, [0, 6]), (c0 + 10, [0, -8], "out"), (c0 + 22, [0, 6])]
        scl += [(c0, [105, 95]), (c0 + 10, [96, 105], "out"), (c0 + 22, [105, 95])]
        win += [(c0, grip), (c0 + 10, push, "out"), (c0 + 22, grip)]
        wout += [(c0, UP[outer]), (c0 + 10, UP[outer] - sgn * 10, "out"), (c0 + 22, UP[outer])]
        jaw += [(c0 + 4, 0), (c0 + 10, 9), (c0 + 18, 0)]
        c0 += 30
    acts["strain"] = {
        "total": n,
        "root_pos": pos + [(n, [0, 6])],
        "root_scale": scl + [(n, [105, 95])],
        f"wing_{inner}": win + [(n, grip)],
        f"wing_{outer}": wout + [(n, UP[outer])],
        "jaw": jaw + [(n, 0)],
        "brow_rot": [(0, 0), (10, 14), (n, 14)],
        "brow_y": [(0, 0), (10, 5), (n, 5)],
        "eyes": blinks(n, [140, 330, 500], base=72),
        "cheek": [(0, 55), (20, 95), (n, 95)],
        "tuft": osc(n, 15, 7),
    }

    # hold: the tomato is up; inner wing under it, outer wing high, proud little bounce. Holds 20 s.
    n = 600
    acts["hold"] = {
        "total": n,
        "root_pos": [(0, [0, 6]), (6, [0, -10], "out"), (14, [0, 2]), (20, [0, 0]), (n, [0, 0])],
        "root_scale": then(
            [(0, [105, 95]), (6, [96, 105]), (14, [102, 98]), (20, [100, 100])],
            osc2(n, 40, [-1.2, 1.6], [100, 100], start=20),
        ),
        f"wing_{inner}": then([(0, grip), (8, under - sgn * 8, "back"), (16, under)], osc(n, 40, 3, under, start=16)),
        f"wing_{outer}": then([(0, UP[outer]), (16, UP[outer])], osc(n, 40, -3 * sgn, UP[outer], start=16)),
        "jaw": [(0, 0), (8, 8), (n, 8)],
        "brow_y": [(0, 5), (10, -7), (n, -7)],
        "cheek": [(0, 95), (n, 85)],
        "eyes": blinks(n, [90, 260, 430]),
        "tuft": osc(n, 20, 7),
        "root_rot": osc(n, 80, 1.5),
    }

    # carry: four small hops per 2 s loop with the tomato held up. Landings on frames 15, 30, 45, 60.
    n = 60
    pos, scl, fl, fr, shd, tuft = [], [], [], [], [], []
    for h in range(4):
        t0 = h * 15
        pos += [(t0, [0, 0], "out"), (t0 + 7.5, [0, -18], "in")]
        scl += [(t0, [105, 95]), (t0 + 3, [97, 104]), (t0 + 7.5, [100, 100]), (t0 + 12, [99, 102])]
        lift = [(t0, [0, 0]), (t0 + 7.5, [0, -10])]
        (fl if h % 2 == 0 else fr).extend(lift)
        (fr if h % 2 == 0 else fl).append((t0, [0, 0]))
        shd += [(t0, [100, 100]), (t0 + 7.5, [84, 84])]
        tuft += [(t0 + 3, -8), (t0 + 10, 8)]
    acts["carry"] = {
        "total": n,
        "root_pos": pos + [(n, [0, 0])],
        "root_scale": scl + [(n, [105, 95])],
        "foot_l": fl + [(n, [0, 0])],
        "foot_r": fr + [(n, [0, 0])],
        "shadow": shd + [(n, [100, 100])],
        f"wing_{inner}": osc(n, 15, 4, under),
        f"wing_{outer}": osc(n, 15, -4 * sgn, UP[outer]),
        "jaw": [(0, 6), (n, 6)],
        "brow_y": [(0, -7), (n, -7)],
        "cheek": [(0, 85), (n, 85)],
        "tuft": [(0, -8)] + tuft + [(n, -8)],
    }

    # put_down: crouch to set the tomato on the grass, stand up, wings down, beam. Holds 10 s.
    n = 300
    acts["put_down"] = {
        "total": n,
        "root_pos": [(0, [0, 0]), (24, [0, 14]), (34, [0, -12], "out"), (42, [0, 0]), (n, [0, 0])],
        "root_scale": then(
            [(0, [100, 100]), (24, [107, 93]), (34, [96, 105]), (42, [101, 99]), (48, [100, 100])],
            osc2(n, 60, [-1.2, 1.8], [100, 100], start=48),
        ),
        "root_rot": [(0, 0), (24, 4 * (1 if inner == "r" else -1)), (40, 0), (n, 0)],
        f"wing_{inner}": [(0, under), (24, low), (38, REST[inner] - sgn * 6, "back"), (46, REST[inner]), (n, REST[inner])],
        f"wing_{outer}": [(0, UP[outer]), (24, UP[outer] - sgn * 40), (40, REST[outer], "back"), (n, REST[outer])],
        "jaw": [(0, 6), (24, 0), (40, 9), (n, 9)],
        "brow_y": [(0, -7), (24, 3), (40, -8), (n, -8)],
        "cheek": [(0, 85), (40, 95), (n, 95)],
        "eyes": blinks(n, [120, 230]),
        "tuft": osc(n, 20, 6),
    }

    # point: a hop and a wing thrown out toward the thing. Holds 8 s.
    n = 240
    p = point_s
    pg = -1 if p == "r" else 1
    lean = 5 * (1 if p == "r" else -1)
    acts["point"] = {
        "total": n,
        f"wing_{p}": then([(0, REST[p], "in"), (4, REST[p] - pg * 10, "back"), (12, POINT[p] + pg * 10), (18, POINT[p])],
                          osc(n, 40, 3, POINT[p], start=18)),
        "root_pos": [(0, [0, 0]), (4, [0, 6], "out"), (12, [0, -12], "in"), (18, [0, 0]), (n, [0, 0])],
        "root_scale": then(
            [(0, [100, 100]), (4, [105, 95]), (12, [97, 104]), (18, [100, 100])],
            osc2(n, 60, [-1, 1.5], [100, 100], start=18),
        ),
        "root_rot": [(0, 0), (12, lean), (n, lean)],
        "brow_y": [(0, 0), (10, -9), (n, -9)],
        "jaw": [(0, 0), (10, 6), (n, 6)],
        "eyes": blinks(n, [120]),
        "tuft": osc(n, 30, 6),
    }

    # smile: happy squint eyes, open beak, two little hops, cheeks glow. Holds 8 s.
    n = 240
    hops = [(0, [0, 0]), (6, [0, 6], "out"), (13, [0, -24], "in"), (20, [0, 0], "out"),
            (27, [0, -18], "in"), (34, [0, 0])]
    acts["smile"] = {
        "total": n,
        "root_pos": hops + [(n, [0, 0])],
        "root_scale": then(
            [(0, [100, 100]), (6, [106, 94]), (13, [96, 105]), (20, [106, 94]), (27, [97, 104]), (34, [100, 100])],
            osc2(n, 50, [-1.2, 1.6], [100, 100], start=34),
        ),
        "root_rot": then([(0, 0)], osc(n, 60, 3, 0, start=34)),
        "eyes_op": [(0, 100), (6, 100, "hold"), (8, 0), (n, 0)],
        "happy_op": [(0, 0), (6, 0, "hold"), (8, 100), (n, 100)],
        "jaw": [(0, 0), (8, 11), (n, 11)],
        "cheek": [(0, 55), (10, 95), (n, 95)],
        "wing_l": then([(0, REST["l"]), (13, REST["l"] + 40), (20, REST["l"] + 6), (27, REST["l"] + 36), (34, REST["l"] + 12)],
                       osc(n, 50, 5, REST["l"] + 12, start=34)),
        "wing_r": then([(0, REST["r"]), (13, REST["r"] - 40), (20, REST["r"] - 6), (27, REST["r"] - 36), (34, REST["r"] - 12)],
                       osc(n, 50, -5, REST["r"] - 12, start=34)),
        "tuft": osc(n, 14, 8),
    }
    return acts


def build_eyes(c, ch):
    ew, eh = c["eye"]
    parts = []
    for side, sign in (("l", -1), ("r", 1)):
        ex = CX + sign * EYE_DX
        shine = [
            ellipse(-ew * 0.16, -eh * 0.2, ew * 0.4, ew * 0.4),
            fill("#FFFFFF"),
        ]
        dot = [ellipse(ew * 0.2, eh * 0.22, ew * 0.16, ew * 0.16), fill("#FFFFFF", 85)]
        ball = [
            ellipse(0, 0, ew, eh),
            grad([(0, "#4A3A6A"), (1, "#1C1430")], (0, -eh / 2), (0, eh / 2)),
        ]
        parts.append(
            group(
                f"eye_{side}",
                [group("shine", shine), group("dot", dot), group("ball", ball)],
                xform(pos=[ex, EYE_Y], scale=ch.get("eyes")),
            )
        )
    eyes = group("eyes", parts, xform(opacity=ch.get("eyes_op")))

    happy = []
    for side, sign in (("l", -1), ("r", 1)):
        ex = CX + sign * EYE_DX
        arc = smooth([(-ew * 0.45, 8), (0, -eh * 0.28), (ew * 0.45, 8)], closed=False, k=0.25)
        happy.append(group(f"happy_{side}", [path(arc), stroke("#2A1E40", 9)], xform(pos=[ex, EYE_Y])))
    happy_g = group("happy_eyes", happy, xform(opacity=ch.get("happy_op", 0)))
    return [happy_g, eyes]


def build_brows(c, ch):
    out = []
    for side, sign in (("l", -1), ("r", 1)):
        ex = CX + sign * EYE_DX
        arc = smooth([(-20, 6), (0, -3), (20, 6)], closed=False, k=0.25)
        rot = ch.get("brow_rot")
        if rot is not None:
            rot = remap(rot, lambda v, s=sign: -v * s)
        out.append(
            group(
                f"brow_{side}",
                [path(arc), stroke(c["line"], 7)],
                xform(pos=[ex, EYE_Y - c["eye"][1] / 2 - 24], rot=rot),
            )
        )
    return group("brows", out, xform(pos=remap(ch["brow_y"], lambda v: [0, v]) if "brow_y" in ch else None))


def build_beak(c, ch):
    top, bottom = c["beak"]
    upper = smooth([(240, 286), (270, 294), (256, 322), (240, 336), (224, 322), (210, 294)])
    lower = smooth([(222, 326), (258, 326), (250, 344), (240, 350), (230, 344)])
    jaw = ch.get("jaw")
    lower_tr = xform(pos=remap(jaw, lambda v: [0, v]) if jaw else None)
    mouth_tr = xform(
        pos=[240, 326],
        anchor=[240, 326],
        scale=remap(jaw, lambda v: [100, 12 + v * 7]) if jaw else [100, 12],
    )
    return group(
        "beak",
        [
            group("upper", [path(upper), stroke(c["beak_line"], 6), grad([(0, top), (1, bottom)], (240, 286), (240, 336))]),
            group("lower", [path(lower), stroke(c["beak_line"], 6), fill(bottom)], lower_tr),
            group(
                "mouth",
                [
                    group("tongue", [ellipse(240, 344, 22, 10), fill("#FF7B8A")]),
                    group("hole", [ellipse(240, 336, 38, 30), fill("#6E1B2A")]),
                ],
                mouth_tr,
            ),
        ],
    )


def build_cheeks(c, ch):
    items = []
    for sign in (-1, 1):
        items.append(ellipse(CX + sign * 92, 318, 50, 28))
    return group("cheeks", [*items, fill(c["cheek"], ch.get("cheek", 55))])


def build_glasses(c):
    ew, eh = c["eye"]
    items = []
    for sign in (-1, 1):
        items.append(ellipse(CX + sign * EYE_DX, EYE_Y, ew + 30, eh + 26))
    bridge = smooth([(CX - EYE_DX + (ew + 30) / 2, EYE_Y - 4), (CX, EYE_Y - 12), (CX + EYE_DX - (ew + 30) / 2, EYE_Y - 4)],
                    closed=False, k=0.25)
    lens = group("lens", [*[ellipse(CX + s * EYE_DX, EYE_Y, ew + 30, eh + 26) for s in (-1, 1)], fill("#FFFFFF", 22)])
    frame = group("frame", [*items, path(bridge), stroke("#6B4A2F", 6)])
    return group("glasses", [frame, lens])


def build_lashes(c):
    ew, eh = c["eye"]
    items = []
    for sign in (-1, 1):
        ex = CX + sign * EYE_DX
        for i, (dx, dy, lx, ly) in enumerate(((0.42, -0.3, 14, -10), (0.5, -0.05, 16, -2))):
            x0, y0 = ex + sign * ew * dx, EYE_Y + eh * dy
            items.append(path(poly([(x0, y0), (x0 + sign * lx, y0 + ly)], closed=False)))
    return group("lashes", [*items, stroke("#2A1E40", 5)])


def build_wing(c, side, rot):
    pts = WING_L if side == "l" else [(-x, y) for x, y in WING_L]
    hi, lo = c["wing"]
    feather = smooth([(p[0] * 0.55, p[1] * 0.55 + 40) for p in pts], closed=False, k=0.2)
    return group(
        f"wing_{side}",
        [
            group("feather", [path(feather), stroke(c["line"], 4, 45)]),
            group("fill", [path(smooth(pts)), stroke(c["line"], 7), grad([(0, hi), (1, lo)], (0, -10), (0, 134))]),
        ],
        xform(pos=list(SHOULDER[side]), rot=rot),
    )


def build_tuft(c, ch):
    kind = c["tuft"]
    rot = ch.get("tuft")
    if kind == "bow":
        loops = []
        for sign in (-1, 1):
            pts = [(0, 0), (sign * 30, -26), (sign * 58, -18), (sign * 62, 8), (sign * 36, 20)]
            loops.append(path(smooth(pts)))
        tails = [path(smooth([(-6, 8), (-26, 44), (-12, 50), (2, 14)])), path(smooth([(6, 8), (26, 44), (12, 50), (-2, 14)]))]
        knot = group("knot", [ellipse(0, 0, 32, 30), stroke("#8E1B1B", 6), grad([(0, "#FF7A7A"), (1, "#E0302F")], (0, -15), (0, 15))])
        body = group("loops", [*loops, *tails, stroke("#8E1B1B", 6), grad([(0, "#FF7A7A"), (1, "#D42A2A")], (0, -26), (0, 50))])
        dots = group("dots", [ellipse(-40, -4, 9, 9), ellipse(42, -2, 9, 9), fill("#FFFFFF", 80)])
        return group("bow", [knot, dots, body], xform(pos=[CX + 20, 132], anchor=[0, 10], rot=rot))
    feathers = []
    if kind == "three":
        spec = [(-30, 60, 30, -4), (0, 80, 34, 0), (28, 58, 28, 4)]
    else:
        spec = [(-8, 86, 32, 10), (30, 52, 24, 6)]
    for ang, length, width, bend in spec:
        feathers.append(
            group(
                "feather",
                [path(smooth(leaf_pts(length, width, bend))), stroke(c["line"], 6), grad([(0, c["shade"]), (1, c["base"])], (0, 0), (0, -length))],
                xform(rot=ang),
            )
        )
    return group("tuft", feathers, xform(pos=[CX, 128], rot=rot))


def build_feet(c, ch):
    feet = []
    for side, fx in (("l", 206), ("r", 274)):
        toes = [ellipse(-15, 4, 22, 16), ellipse(0, 8, 22, 18), ellipse(15, 4, 22, 16)]
        feet.append(
            group(
                f"foot_{side}",
                [*toes, stroke(c["beak_line"], 5), grad([(0, c["beak"][0]), (1, c["beak"][1])], (0, -6), (0, 16))],
                xform(pos=[fx, 510], scale=None, rot=None) if f"foot_{side}" not in ch else
                xform(pos=remap(ch[f"foot_{side}"], lambda v, x=fx: [x + v[0], 510 + v[1]])),
            )
        )
    return group("feet", feet)


def build_bird(name: str, c: dict, action: str, ch: dict) -> dict:
    total = ch["total"]
    face_items = []
    if c.get("glasses"):
        face_items.append(build_glasses(c))
        face_items.append(build_lashes(c))
    face_items += build_eyes(c, ch)
    face_items.append(build_brows(c, ch))
    face_items.append(build_beak(c, ch))
    face_items.append(build_cheeks(c, ch))
    face = group("face", face_items, xform(pos=[c["facing"] * 10, 0]))

    body_path = path(smooth(BODY_PTS))
    body = group(
        "body",
        [
            group("rim", [path(smooth([(330, 190), (380, 290), (370, 400)], closed=False, k=0.25)), stroke("#FFFFFF", 8, 35)]),
            group("fill", [body_path, stroke(c["line"], 8), grad([(0, c["hi"]), (0.5, c["base"]), (1, c["shade"])], (180, 200), (430, 560), radial=True)]),
        ],
    )
    belly = group(
        "belly",
        [ellipse(CX, 420, 214, 166), grad([(0, c["belly"][0]), (1, c["belly"][1])], (CX, 350), (CX, 500))],
    )

    parts = [
        build_wing(c, "l", ch.get("wing_l", REST["l"])),
        build_wing(c, "r", ch.get("wing_r", REST["r"])),
        face,
    ]
    tuft = build_tuft(c, ch)
    if c["tuft"] == "bow":
        parts += [tuft, belly, body]
    else:
        parts += [belly, body, tuft]
    parts.append(build_feet(c, ch))

    root_pos = ch.get("root_pos")
    rig = group(
        "bird",
        parts,
        xform(
            pos=remap(root_pos, lambda v: [CX + v[0], FOOT_Y + v[1]]) if root_pos else [CX, FOOT_Y],
            anchor=[CX, FOOT_Y],
            scale=ch.get("root_scale"),
            rot=ch.get("root_rot"),
        ),
    )
    shadow = group(
        "shadow",
        [ellipse(0, 0, 250, 36), fill("#1F4A1A", 24)],
        xform(pos=[CX, 526], scale=ch.get("shadow")),
    )
    layer = shape_layer(f"{name}_{action}", [rig, shadow], total, ks={"p": prop([BIRD_PAD, 0, 0])})
    return comp(f"{name}_{action}", BIRD_W, BIRD_H, [layer], total)


# ---------------------------------------------------------------- tomato


def tomato_fruit(scale=1.0, colors=None):
    colors = colors or [(0, "#FF9480"), (0.45, "#F4402F"), (0.85, "#C42119"), (1, "#9C1612")]
    pts = []
    for i in range(16):
        a = 2 * math.pi * i / 16 - math.pi / 2
        rx, ry = 132 * scale, 118 * scale
        x, y = rx * math.cos(a), ry * math.sin(a)
        if i == 0:
            y += 14 * scale
        pts.append((x, y))
    body = path(smooth(pts))
    return body, colors


def build_tomato(action: str) -> dict:
    body, colors = tomato_fruit()
    lobes = [
        path(smooth([(-34, -100), (-66, -30), (-54, 64)], closed=False, k=0.25)),
        path(smooth([(34, -100), (66, -30), (54, 64)], closed=False, k=0.25)),
    ]
    calyx = []
    for ang in (-90, -30, 30, 150, 210):
        calyx.append(
            group(
                "sepal",
                [path(smooth(leaf_pts(58, 24, 6))), stroke("#2C6A22", 5), grad([(0, "#3E9A2F"), (1, "#86DB5A")], (0, 0), (0, -58))],
                xform(rot=ang + 90),
            )
        )
    stem = group("stem", [rect(0, -22, 14, 34, 7), stroke("#2C6A22", 5), fill("#5DB33E")], xform(rot=12))
    fruit = group(
        "fruit",
        [
            group("stem", [stem], xform(pos=[0, -104])),
            group("calyx", calyx, xform(pos=[0, -102], scale=[100, 62])),
            group("spec", [ellipse(0, 0, 58, 30), fill("#FFFFFF", 85)], xform(pos=[-56, -46], rot=-38)),
            group("spec2", [ellipse(-22, -80, 14, 10), fill("#FFFFFF", 70)]),
            group("rim", [path(smooth([(96, 10), (80, 64), (36, 100)], closed=False, k=0.25)), stroke("#FFFFFF", 7, 28)]),
            group("lobes", [*lobes, stroke("#A81A14", 5, 35)]),
            group("skin", [body, stroke("#7E1410", 7), grad(colors, (-50, -50), (150, 150), radial=True)]),
        ],
    )
    if action == "rest":
        total = 60
        tr = xform(pos=[180, 222 - 104], anchor=[0, -104], rot=osc(total, 60, 2.2))
        rig = group("tomato", [fruit], tr)
    elif action == "wobble":
        total = 60
        rot = [(0, 0), (6, 12), (14, -10), (22, 8), (30, -5), (38, 3), (46, 0), (total, 0)]
        scl = [(0, [100, 100]), (6, [105, 95]), (14, [96, 104]), (22, [103, 97]), (30, [100, 100]), (total, [100, 100])]
        rig = group("tomato", [fruit], xform(pos=[180, 222 + 118], anchor=[0, 118], rot=rot, scale=scl))
    elif action == "lifted":
        # Same centre as rest; the clip box carries the height.
        total = 600
        rot = osc(total, 40, 3)
        pos = remap(osc(total, 20, 3, 0), lambda v: [180, 222 + v])
        scl = osc2(total, 20, [1.5, -1.5], [100, 100])
        rig = group("tomato", [fruit], xform(pos=pos, rot=rot, scale=scl))
    elif action == "strain":
        # Stuck: a little lift and tilt on each heave of the birds (heaves start at frame 12, every 30).
        total = 600
        pos, rot, scl = [(0, [180, 340])], [(0, 0)], [(0, [100, 100])]
        c0, k = 12, 0
        while c0 + 30 <= total:
            tilt = 5 if k % 2 == 0 else -5
            pos += [(c0 + 4, [180, 340]), (c0 + 10, [180, 330], "out"), (c0 + 18, [180, 340], "in")]
            rot += [(c0 + 4, 0), (c0 + 10, tilt), (c0 + 22, 0)]
            scl += [(c0 + 4, [100, 100]), (c0 + 10, [97, 104]), (c0 + 18, [106, 94]), (c0 + 24, [100, 100])]
            c0 += 30
            k += 1
        rig = group("tomato", [fruit], xform(pos=pos + [(total, [180, 340])], anchor=[0, 118], rot=rot + [(total, 0)], scale=scl + [(total, [100, 100])]))
    elif action == "carry":
        # Rides the birds' hops: up on frames 7.5 + 15k, squash on each landing.
        total = 60
        pos, scl = [], []
        for h in range(4):
            t0 = h * 15
            pos += [(t0, [180, 222], "out"), (t0 + 7.5, [180, 196], "in")]
            scl += [(t0, [104, 96]), (t0 + 4, [98, 103]), (t0 + 10, [100, 100])]
        rig = group("tomato", [fruit], xform(pos=pos + [(total, [180, 222])], scale=scl + [(total, [104, 96])], rot=osc(total, 30, 3)))
    elif action == "ground":
        # Lands with a squash, then sits still.
        total = 300
        scl = [(0, [110, 90]), (6, [95, 105]), (12, [102, 98]), (18, [100, 100]), (total, [100, 100])]
        rig = group("tomato", [fruit], xform(pos=[180, 340], anchor=[0, 118], scale=scl))
    else:
        raise ValueError(action)
    layer = shape_layer(f"tomato_{action}", [rig], total)
    return comp(f"tomato_{action}", TOMATO_SIZE, TOMATO_SIZE, [layer], total)


# ---------------------------------------------------------------- garden


def cloud(x, y, s, drift, total):
    puffs = [(0, 0, 150), (-80, 22, 110), (82, 18, 120), (-150, 48, 74), (150, 46, 78), (-30, 44, 110), (40, 46, 110)]
    items = [ellipse(px * s, py * s, d * s, d * s) for px, py, d in puffs]
    shade = group("shade", [ellipse(0, 70 * s, 300 * s, 44 * s), fill("#CFE8FA", 70)])
    body = group("puffs", [*items, grad([(0, "#FFFFFF"), (1, "#E6F4FF")], (0, -70 * s), (0, 80 * s))])
    return group(
        "cloud",
        [body, shade],
        xform(pos=[(0, [x, y], "lin"), (total, [x + drift, y])]),
    )


def sun(total):
    rays = []
    for i in range(12):
        a = 360 * i / 12
        rays.append(
            group(
                "ray",
                [path(smooth([(0, -120), (18, -190), (0, -232), (-18, -190)])), fill("#FFE36B", 80)],
                xform(rot=a),
            )
        )
    ray_g = group("rays", rays, xform(rot=[(0, 0, "lin"), (total, 360)]))
    pulse = osc2(total, 90, [4, 4], [100, 100])
    glow = group(
        "glow",
        [ellipse(0, 0, 640, 640), grad([(0, "#FFF6C8"), (1, "#FFF6C8")], (0, 0), (320, 0), radial=True, alphas=[(0, 0.75), (1, 0)])],
        xform(scale=pulse),
    )
    core = group(
        "core",
        [
            group("shine", [ellipse(-30, -34, 60, 40), fill("#FFFFFF", 60)], xform(rot=-30)),
            group("disc", [ellipse(0, 0, 200, 200), stroke("#FFB52E", 8), grad([(0, "#FFFBD8"), (0.55, "#FFE14A"), (1, "#FFB82E")], (-30, -30), (110, 110), radial=True)]),
        ],
    )
    return group("sun", [core, ray_g, glow], xform(pos=[1700, 150]))


def hills_far():
    pts = [(-40, 1080), (-40, 520), (160, 470), (420, 510), (700, 455), (980, 500), (1260, 450), (1560, 505), (1800, 470), (1960, 500), (1960, 1080)]
    return group(
        "hills_far",
        [path(smooth(pts, k=0.12)), stroke("#7DB88A", 4, 60), grad([(0, "#B4E3B8"), (1, "#8FCF95")], (960, 450), (960, 640))],
    )


def tree(x, y, s):
    crown = [(0, -150, 150), (-60, -110, 110), (60, -112, 116), (-20, -190, 110), (40, -180, 96)]
    crowns = [ellipse(x + cx * s, y + cy * s, d * s, d * s) for cx, cy, d in crown]
    return group(
        "tree",
        [
            group("crown", [*crowns, stroke("#2F7A28", 4), grad([(0, "#8EDB63"), (1, "#3F9A35")], (x - 60 * s, y - 230 * s), (x + 40 * s, y - 60 * s))]),
            group("trunk", [rect(x, y - 40 * s, 30 * s, 110 * s, 10 * s), stroke("#5E3A20", 4), grad([(0, "#A8744A"), (1, "#7A4E2E")], (x - 15 * s, 0), (x + 15 * s, 0))]),
        ],
    )


def hills_near():
    pts = [(-40, 1080), (-40, 600), (240, 555), (560, 590), (900, 560), (1240, 585), (1560, 548), (1960, 590), (1960, 1080)]
    return group(
        "hills_near",
        [
            tree(180, 600, 0.9),
            tree(1480, 580, 0.75),
            tree(1790, 600, 1.0),
            tree(620, 600, 0.55),
            group("hill", [path(smooth(pts, k=0.12)), stroke("#4E9A45", 4, 70), grad([(0, "#9CDC7C"), (1, "#6FBF5A")], (960, 550), (960, 680))]),
        ],
    )


def fence():
    pickets = []
    x = -10
    while x < 1940:
        if not 730 < x < 1190:
            pickets.append(path(poly([(x - 17, 660), (x - 17, 566), (x, 540), (x + 17, 566), (x + 17, 660)])))
        x += 56
    rails = [rect(410, 588, 860, 14, 4), rect(410, 634, 860, 14, 4), rect(1560, 588, 760, 14, 4), rect(1560, 634, 760, 14, 4)]
    return group(
        "fence",
        [
            group("pickets", [*pickets, stroke("#B89B72", 4), grad([(0, "#FFFDF6"), (1, "#EAD9BD")], (0, 540), (0, 660))]),
            group("rails", [*rails, stroke("#B89B72", 4), fill("#E5D2B2")]),
        ],
    )


def lawn(rng):
    top = [(-40, 1120), (-40, 650), (300, 636), (640, 652), (960, 640), (1300, 654), (1640, 636), (1960, 650), (1960, 1120)]
    patches = []
    for _ in range(14):
        px, py = rng.uniform(60, 1860), rng.uniform(700, 1040)
        patches.append(ellipse(px, py, rng.uniform(120, 260), rng.uniform(26, 50)))
    tufts = []
    for _ in range(46):
        tx, ty = rng.uniform(30, 1890), rng.uniform(690, 1060)
        sc = 0.7 + (ty - 690) / 370 * 0.8
        for dx, lean in ((-8, -10), (0, 0), (8, 10)):
            tufts.append(path(smooth([(tx + dx * sc, ty), (tx + (dx + lean * 0.4) * sc, ty - 14 * sc), (tx + (dx + lean) * sc, ty - 26 * sc)], closed=False, k=0.25)))
    return group(
        "lawn",
        [
            group("tufts", [*tufts, stroke("#3F9A38", 4)]),
            group("patches", [*patches, fill("#A9EA86", 45)]),
            group("turf", [path(smooth(top, k=0.12)), stroke("#4E9A45", 5), grad([(0, "#9EE37C"), (0.5, "#6ECC58"), (1, "#4DAF45")], (960, 640), (960, 1080))]),
        ],
    )


def soil():
    pebbles = [ellipse(780, 668, 20, 12), ellipse(1140, 676, 24, 14), ellipse(1180, 660, 14, 9), ellipse(820, 690, 16, 10)]
    return group(
        "soil",
        [
            group("pebbles", [*pebbles, stroke("#8A8A8A", 3), fill("#D8D8D0")]),
            group("bed", [ellipse(960, 670, 520, 76), stroke("#5E3A20", 5), grad([(0, "#A8744A"), (1, "#6E4428")], (960, 640), (960, 710))]),
        ],
    )


def flower(kind, x, y, s, color, total, period, phase):
    stem = smooth([(0, 0), (4, -30 * s), (0, -60 * s)], closed=False, k=0.25)
    leaf = group("leaf", [path(smooth(leaf_pts(26 * s, 12 * s, 2))), stroke("#2F7A28", 3), fill("#5DBB45")], xform(pos=[1, -20 * s], rot=50))
    if kind == "daisy":
        petals = [group("p", [ellipse(0, -13 * s, 12 * s, 22 * s), stroke("#C9C2B0", 2.5), fill("#FFFFFF")], xform(rot=i * 45)) for i in range(8)]
        head = group("head", [group("c", [ellipse(0, 0, 16 * s, 16 * s), stroke("#C9780C", 2.5), fill("#FFC933")]), *petals], xform(pos=[0, -62 * s]))
    else:
        cup = smooth([(-14 * s, -8 * s), (-10 * s, -30 * s), (-5 * s, -22 * s), (0, -34 * s), (5 * s, -22 * s), (10 * s, -30 * s), (14 * s, -8 * s), (0, 4 * s)])
        head = group("head", [path(cup), stroke("#8E1B3A", 3), grad([(0, "#FFFFFF"), (1, color)], (0, -40 * s), (0, 4 * s))], xform(pos=[0, -58 * s]))
        head["it"].insert(0, group("shine", [ellipse(-5 * s, -20 * s, 5 * s, 12 * s), fill("#FFFFFF", 50)]))
    rot = osc(total, period, 4, 0, start=phase)
    stem_g = group("stem", [path(stem), stroke("#3E9A38", 4 * max(s, 0.8))])
    return group("flower", [head, leaf, stem_g], xform(pos=[x, y], rot=rot))


def scallop(x, y, r, bumps=9):
    pts = []
    for i in range(bumps * 2):
        a = math.pi * i / bumps
        rr = r if i % 2 == 0 else r * 0.86
        pts.append((x + rr * math.cos(a), y + rr * math.sin(a)))
    return pts


def plant():
    blobs = []
    centres = [(960, 480, 170), (850, 520, 130), (1070, 520, 130), (900, 400, 130), (1030, 400, 130),
               (960, 330, 120), (810, 440, 110), (1110, 440, 110), (960, 590, 140), (870, 610, 100), (1050, 610, 100)]
    for x, y, d in centres:
        blobs.append(
            group("blob", [path(smooth(scallop(x, y, d / 2))), stroke("#2E6B25", 5), grad([(0, "#8FDC5E"), (1, "#3F8F32")], (x - d * 0.3, y - d * 0.5), (x + d * 0.2, y + d * 0.5))])
        )
    leaves = []
    for x, y, ang in [(770, 360, -60), (1150, 360, 60), (740, 520, -95), (1180, 520, 95), (880, 270, -20), (1050, 270, 25)]:
        leaves.append(group("leaf", [path(smooth(leaf_pts(70, 38, 4))), stroke("#2E6B25", 4), grad([(0, "#3F8F32"), (1, "#8FDC5E")], (0, 0), (0, -70))], xform(pos=[x, y], rot=ang)))
    veins = [path(smooth([(x - 30, y + 10), (x, y - 12), (x + 30, y + 8)], closed=False, k=0.25)) for x, y, _ in centres[:8]]
    small = []
    for x, y, d, cols in [(812, 400, 46, [(0, "#FF9480"), (1, "#D42A1F")]), (1112, 540, 40, [(0, "#FFC070"), (1, "#F07A1A")]),
                          (1080, 360, 36, [(0, "#C8F07A"), (1, "#6FB53A")]), (870, 600, 34, [(0, "#C8F07A"), (1, "#6FB53A")])]:
        small.append(group("mini", [ellipse(x, y, d, d * 0.92), stroke("#7E1410" if cols[0][1] != "#C8F07A" else "#2E6B25", 4), grad(cols, (x - d * 0.3, y - d * 0.3), (x + d * 0.5, y + d * 0.5), radial=True)]))
        small.append(group("spec", [ellipse(x - d * 0.2, y - d * 0.2, d * 0.25, d * 0.15), fill("#FFFFFF", 75)]))
    blossoms = []
    for x, y in [(930, 300), (1150, 470), (780, 560)]:
        petals = [group("p", [ellipse(0, -8, 9, 14), fill("#FFE14A")], xform(rot=i * 72)) for i in range(5)]
        blossoms.append(group("blossom", [group("c", [ellipse(0, 0, 8, 8), fill("#F29A1A")]), *petals], xform(pos=[x, y])))
    stake = group("stake", [rect(960, 470, 20, 400, 6), stroke("#5E3A20", 4), grad([(0, "#C49166"), (1, "#8A5A34")], (950, 0), (970, 0))])
    ties = group("ties", [rect(960, 300, 30, 8, 3), rect(960, 480, 30, 8, 3), fill("#F2E2B8")])
    return group("plant", [*blossoms, *small, group("veins", [*veins, stroke("#2E6B25", 3, 40)]), *reversed(blobs), *leaves, ties, stake])


def butterfly(total, seed, colors):
    rng = random.Random(seed)
    wings = []
    for sign in (-1, 1):
        wings.append(group("upper", [ellipse(sign * 16, -8, 30, 36), stroke("#5A2A6A", 3), grad([(0, "#FFFFFF"), (1, colors[0])], (sign * 6, -20), (sign * 30, 10))], xform(rot=sign * 20)))
        wings.append(group("lower", [ellipse(sign * 12, 14, 20, 24), stroke("#5A2A6A", 3), fill(colors[1])], xform(rot=-sign * 20)))
    flap = []
    t = 0
    while t < total:
        flap += [(t, [100, 100]), (t + 3, [22, 100])]
        t += 6
    flap.append((total, [100, 100]))
    wing_g = group("wings", wings, xform(scale=flap))
    body = group("body", [ellipse(0, 2, 8, 34), fill("#3A2440")])
    pos = []
    x, y = rng.uniform(300, 1600), rng.uniform(180, 420)
    t = 0
    while t < total:
        pos.append((t, [x, y], "io"))
        x = min(max(x + rng.uniform(-260, 260), 120), 1800)
        y = min(max(y + rng.uniform(-90, 90), 150), 470)
        t += 60
    pos.append((total, [x, y]))
    tilt = osc(total, 50, 12)
    return group("butterfly", [body, wing_g], xform(pos=pos, rot=tilt, scale=[80, 80]))


def foreground(total):
    rng = random.Random(3)
    blades = []
    for x0, flip in ((0, 1), (1920, -1)):
        for i in range(9):
            bx = x0 + flip * rng.uniform(0, 170)
            h = rng.uniform(70, 150)
            lean = flip * rng.uniform(10, 50)
            blades.append(path(smooth([(bx - 9, 1090), (bx + lean * 0.4, 1090 - h * 0.55), (bx + lean, 1090 - h), (bx + lean * 0.4 + 6, 1090 - h * 0.5), (bx + 9, 1090)], k=0.15)))
    grass = group("blades", [*blades, stroke("#2F7A28", 4), grad([(0, "#8FDC5E"), (1, "#3F9A35")], (0, 940), (0, 1090))])
    flowers = [
        flower("tulip", 70, 1090, 2.0, "#FF5E8A", total, 110, 0),
        flower("daisy", 150, 1100, 1.8, "#FFFFFF", total, 130, 30),
        flower("tulip", 1860, 1090, 2.1, "#FFB23A", total, 120, 20),
        flower("daisy", 1770, 1100, 1.7, "#FFFFFF", total, 100, 50),
    ]
    return group("foreground", [*flowers, grass])


def build_garden() -> dict:
    total = GARDEN_FRAMES
    rng = random.Random(11)
    row = []
    for i, x in enumerate([60, 130, 330, 420, 560, 660, 1250, 1330, 1420, 1600, 1700, 1860]):
        kind = "daisy" if i % 2 else "tulip"
        color = ["#FF5E8A", "#FFB23A", "#B070FF", "#FF6A5A"][i % 4]
        row.append(flower(kind, x, 668 + (i % 3) * 8, 1.0 + (i % 3) * 0.12, color, total, 90 + i * 7, i * 9))
    layers = [
        shape_layer("foreground", [foreground(total)], total),
        shape_layer("butterflies", [butterfly(total, 1, ("#FF8FC8", "#C85AD8")), butterfly(total, 2, ("#8FD8FF", "#4A90E2"))], total),
        shape_layer("plant", [plant()], total),
        shape_layer("flowers", row, total),
        shape_layer("soil", [soil()], total),
        shape_layer("lawn", [lawn(rng)], total),
        shape_layer("fence", [fence()], total),
        shape_layer("hills_near", [hills_near()], total),
        shape_layer("hills_far", [hills_far()], total),
        shape_layer(
            "clouds",
            [cloud(300, 150, 0.9, 260, total), cloud(900, 95, 0.6, 180, total), cloud(1320, 250, 0.5, 140, total), cloud(-120, 330, 0.45, 220, total)],
            total,
        ),
        shape_layer("sun", [sun(total)], total),
        shape_layer(
            "sky",
            [group("sky", [rect(960, 540, 1920, 1080), grad([(0, "#46AEF5"), (0.6, "#8ED3FF"), (1, "#DDF4FF")], (960, 0), (960, 640))])],
            total,
        ),
    ]
    return comp("garden", W, H, layers, total)


# ---------------------------------------------------------------- title and end cards


def sparkle(x, y, size, start, total, color="#FFFFFF"):
    keys = [(0, [0, 0])]
    t = start
    while t + 30 <= total:
        keys += [(t, [0, 0], "out"), (t + 10, [100, 100], "in"), (t + 22, [0, 0])]
        t += 44
    keys.append((total, [0, 0]))
    return group(
        "sparkle",
        [path(smooth(star_pts(size, size * 0.22), k=0.05)), fill(color)],
        xform(pos=[x, y], scale=keys, rot=[(0, 0, "lin"), (total, 90)]),
    )


def build_title_card() -> dict:
    total = 150
    rays = []
    for i in range(18):
        a = math.radians(360 * i / 18)
        b = math.radians(360 * i / 18 + 10)
        rays.append(path(poly([(0, 0), (1400 * math.cos(a), 1400 * math.sin(a)), (1400 * math.cos(b), 1400 * math.sin(b))])))
    burst = group(
        "burst",
        [*rays, fill("#FFFFFF", 22)],
        xform(pos=[960, 400], rot=[(0, 0, "lin"), (total, 24)],
              scale=[(0, [0, 0], "back"), (16, [100, 100]), (total, [100, 100])]),
    )
    glow = group(
        "glow",
        [ellipse(960, 400, 1500, 900), grad([(0, "#FFFBE0"), (1, "#FFFBE0")], (960, 400), (1710, 400), radial=True, alphas=[(0, 0.7), (1, 0)])],
    )
    band = smooth([(-400, -58), (0, -70), (400, -58), (400, 58), (0, 46), (-400, 58)], k=0.08)
    tails = []
    for sign in (-1, 1):
        tails.append(path(poly([(sign * 360, -40), (sign * 500, -40), (sign * 460, 20), (sign * 500, 80), (sign * 360, 80)])))
    folds = [path(poly([(sign * 360, 80), (sign * 400, 58), (sign * 400, 80)])) for sign in (-1, 1)]
    ribbon = group(
        "ribbon",
        [
            group("band", [path(band), stroke("#8A1C14", 7), grad([(0, "#FF6B5A"), (1, "#D9302A")], (0, -70), (0, 60))]),
            group("folds", [*folds, fill("#7A1510")]),
            group("tails", [*tails, stroke("#8A1C14", 7), grad([(0, "#E0453A"), (1, "#A8231C")], (0, -40), (0, 80))]),
        ],
        xform(pos=[960, 712], scale=[(0, [0, 100]), (14, [0, 100], "back"), (28, [100, 100]), (total, [100, 100])]),
    )
    sparkles = [
        sparkle(330, 250, 34, 20, total, "#FFF6A0"),
        sparkle(1600, 230, 40, 34, total),
        sparkle(1500, 560, 26, 50, total, "#FFF6A0"),
        sparkle(420, 560, 30, 60, total),
        sparkle(960, 170, 24, 44, total, "#FFF6A0"),
        sparkle(1230, 150, 20, 70, total),
    ]
    out = {"o": anim([(0, 100), (136, 100), (150, 0)])}
    layers = [
        shape_layer("sparkles", sparkles, total, ks=out),
        shape_layer("ribbon", [ribbon], total, ks=out),
        shape_layer("burst", [burst, glow], total, ks=out),
    ]
    return comp("title_card", W, H, layers, total)


def build_end_card() -> dict:
    total = 120
    rng = random.Random(5)
    panel = group(
        "panel",
        [
            group("face", [rect(0, 0, 1260, 230, 115), stroke("#F2A516", 10), grad([(0, "#FFFFFF"), (1, "#FFF3D0")], (0, -115), (0, 115))]),
            group("drop", [rect(0, 14, 1260, 230, 115), fill("#2C3554", 22)]),
        ],
        xform(pos=[960, 520], scale=[(0, [0, 0], "back"), (14, [100, 100]), (total, [100, 100])]),
    )
    confetti = []
    palette = ["#FF5E8A", "#FFD93A", "#46AEF5", "#6ECC58", "#FF9446", "#B070FF"]
    for i in range(40):
        x = rng.uniform(40, 1880)
        y0 = rng.uniform(-300, -20)
        fall = rng.uniform(900, 1300)
        spin = rng.uniform(-540, 540)
        confetti.append(
            group(
                "bit",
                [rect(0, 0, rng.uniform(14, 22), rng.uniform(8, 12), 3), fill(palette[i % len(palette)])],
                xform(pos=[(0, [x, y0], "lin"), (total, [x + rng.uniform(-80, 80), y0 + fall])], rot=[(0, 0, "lin"), (total, spin)]),
            )
        )
    layers = [
        shape_layer("confetti", confetti, total),
        shape_layer("panel", [panel], total),
    ]
    return comp("end_card", W, H, layers, total)


# ---------------------------------------------------------------- write


def write_json(name: str, doc: dict) -> Path:
    path_ = OUT / f"{name}.json"
    path_.write_text(json.dumps(doc, separators=(",", ":")) + "\n", encoding="utf-8")
    return path_


def build_all() -> list[Path]:
    OUT.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, colors in BIRDS.items():
        for action, ch in bird_actions(colors).items():
            paths.append(write_json(f"{name}_{action}", build_bird(name, colors, action, ch)))
    for action in ("rest", "wobble", "lifted", "strain", "carry", "ground"):
        paths.append(write_json(f"tomato_{action}", build_tomato(action)))
    paths.append(write_json("garden", build_garden()))
    paths.append(write_json("title_card", build_title_card()))
    paths.append(write_json("end_card", build_end_card()))
    return paths


def box(w: float, h: float) -> None:
    """Print where a character lands inside a contain-fit clip box."""
    s = min(w / BIRD_W, h / BIRD_H)
    ox, oy = (w - BIRD_W * s) / 2, (h - BIRD_H * s) / 2
    rig = lambda x, y: (round(ox + (x + BIRD_PAD) * s, 1), round(oy + y * s, 1))
    print(f"scale {s:.4f}  (contain-fit of {BIRD_W}x{BIRD_H} into {w:g}x{h:g})")
    print(f"feet        box-relative {rig(CX, FOOT_Y)}")
    print(f"head top    box-relative {rig(CX, 116)}")
    print(f"body edges  x {rig(76, 0)[0]} .. {rig(404, 0)[0]}")
    print(f"shoulders   l {rig(*SHOULDER['l'])}  r {rig(*SHOULDER['r'])}")
    print(f"wing length {round(134 * s, 1)} px on screen")
    old = min(w / 480, h / 560)
    print(f"from a 480-wide box of the same scale: w' = {640 * old:.2f}, x' = x - {80 * old:.2f}")


def main() -> None:
    global OUT, GARDEN_FRAMES, BIRDS
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="write every Lottie file")
    b.add_argument("--out", default=".", help="output directory")
    b.add_argument("--cast", help="JSON file: {name: {character keys}}")
    b.add_argument("--seconds", type=float, default=101, help="garden length (the film length)")
    x = sub.add_parser("box", help="clip-box maths for a character")
    x.add_argument("--w", type=float, required=True)
    x.add_argument("--h", type=float, required=True)
    a = ap.parse_args()
    if a.cmd == "box":
        box(a.w, a.h)
        return
    OUT = Path(a.out).resolve()
    GARDEN_FRAMES = round(a.seconds * FPS)
    if a.cast:
        BIRDS = json.loads(Path(a.cast).read_text(encoding="utf-8"))
    for p in build_all():
        print(p.name, p.stat().st_size)


if __name__ == "__main__":
    sys.exit(main())
