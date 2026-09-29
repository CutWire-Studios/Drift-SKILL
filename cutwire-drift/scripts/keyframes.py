#!/usr/bin/env python3
"""Turn a small motion spec into a correct Drift keyframe op batch.

Writes a multi-key animation: seek, keys, interpolation, bezier handles, seek
back. A constant move is `set_transform` alone — on a current build that moves
the clip's single birth key and holds. Seek matters here because
`set_keyframe_interpolation` moves the playhead, which would otherwise become
the time of the next write.

Spec (JSON, one object or a list of them):

  {
    "clip": "<uuid>",
    "seek": 23.0,                       // optional, default: first key time
    "props": [
      {"prop": "x",       "ease": "settle", "keys": [[22.3, 410], [24.0, 1004]]},
      {"prop": "opacity", "ease": "exit",   "keys": [[68.2, 1], [68.85, 0]]},
      {"prop": "fx.0.amount", "ease": "linear", "keys": [[26.0, 0], [26.5, 28]]}
    ]
  }

Keyframe property names are NOT the set_transform names: use width/height, not
w/h. Others: x, y, rotation, rotationX, rotationY, z, perspective, opacity,
volume, fx.<i>.<param>, mask.<key>, text.<key>, text.layer.<id>.<field>,
shape.<key>, model3d.<key>.

Easing tokens (segment from A(t0,v0) to B(t1,v1), T = t1-t0, D = v1-v0):

  settle  entrances, arrivals, materialising blur/exposure. ~80% of D by 25% T.
  glide   on-screen moves, write-ons, turntables, mask wipes. Symmetric.
  exit    opacity and position exits.
  linear  camera push-ins, light sweeps, hold-keyed jitter.
  hold    step: the value jumps at the next key.

Usage:
  keyframes.py emit spec.json | drift_cli.py apply -
  keyframes.py emit spec.json --dry-run      # human-readable summary
"""
from __future__ import annotations

import argparse
import json
import sys

# out-handle of the earlier key, in-handle of the later key, as fractions of T and D
TOKENS = {
    "settle": {"mode": "ease", "out": (0.23, 1.0), "in": (-0.68, 0.0)},
    "glide":  {"mode": "ease", "out": (0.45, 0.0), "in": (-0.45, 0.0)},
    "exit":   {"mode": "ease", "out": (0.55, 0.0), "in": (0.0, -0.55)},
    "linear": {"mode": "linear"},
    "hold":   {"mode": "hold"},
}


def r3(x: float) -> float:
    return round(x + 0.0, 6)


def ops_for_clip(spec: dict) -> list[dict]:
    clip = spec["clip"]
    props = spec["props"]
    all_times = [k[0] for p in props for k in p["keys"]]
    if not all_times:
        return []
    seek_at = spec.get("seek", min(all_times))

    ops: list[dict] = [{"tool": "seek", "args": {"at": r3(seek_at)}}]

    # 1. values first, so every key exists before we shape it
    for p in props:
        for t, v in p["keys"]:
            ops.append({"tool": "set_keyframe",
                        "args": {"clip": clip, "prop": p["prop"], "at": r3(t), "value": v}})

    # 2. interpolation mode per key (this op moves the playhead; we seek back at the end)
    for p in props:
        eases = p.get("eases") or [p.get("ease", "settle")] * max(len(p["keys"]) - 1, 1)
        for i, (t, _v) in enumerate(p["keys"]):
            token = eases[min(i, len(eases) - 1)]
            mode = TOKENS[token]["mode"]
            ops.append({"tool": "set_keyframe_interpolation",
                        "args": {"clip": clip, "prop": p["prop"], "at": r3(t), "mode": mode}})

    # 3. bezier handles, one op per key carrying all four fields
    for p in props:
        keys = p["keys"]
        eases = p.get("eases") or [p.get("ease", "settle")] * max(len(keys) - 1, 1)
        handles = {t: {"inDx": 0.0, "inDy": 0.0, "outDx": 0.0, "outDy": 0.0} for t, _ in keys}
        shaped = False
        for i in range(len(keys) - 1):
            token = eases[min(i, len(eases) - 1)]
            tok = TOKENS[token]
            if "out" not in tok:
                continue
            (t0, v0), (t1, v1) = keys[i], keys[i + 1]
            T, D = t1 - t0, v1 - v0
            if not isinstance(v0, (int, float)) or not isinstance(v1, (int, float)):
                sys.exit(f"{p['prop']}: bezier handles need numeric values")
            ox, oy = tok["out"]
            ix, iy = tok["in"]
            handles[t0]["outDx"], handles[t0]["outDy"] = ox * T, oy * D
            handles[t1]["inDx"], handles[t1]["inDy"] = ix * T, iy * D
            shaped = True
        if not shaped:
            continue
        for t, h in handles.items():
            ops.append({"tool": "set_keyframe_tangents",
                        "args": {"clip": clip, "prop": p["prop"], "at": r3(t), "corner": False,
                                 "inDx": r3(h["inDx"]), "inDy": r3(h["inDy"]),
                                 "outDx": r3(h["outDx"]), "outDy": r3(h["outDy"])}})

    ops.append({"tool": "seek", "args": {"at": r3(seek_at)}})
    return ops


def cmd_emit(a):
    spec = json.load(sys.stdin if a.spec == "-" else open(a.spec))
    specs = spec if isinstance(spec, list) else [spec]
    ops: list[dict] = []
    for s in specs:
        ops += ops_for_clip(s)
    if a.dry_run:
        for s in specs:
            print(f"clip {s['clip']}  seek {s.get('seek', 'auto')}")
            for p in s["props"]:
                ks = ", ".join(f"{t}s={v}" for t, v in p["keys"])
                print(f"  {p['prop']:28s} {p.get('ease', 'settle'):7s} {ks}")
        print(f"\n{len(ops)} ops "
              f"({sum(1 for o in ops if o['tool'] == 'set_keyframe')} keys)", file=sys.stderr)
        return
    json.dump(ops, sys.stdout, indent=None if a.compact else 2)
    print()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("emit", help="spec -> ops array on stdout")
    c.add_argument("spec", help="spec file, or - for stdin")
    c.add_argument("--dry-run", action="store_true")
    c.add_argument("--compact", action="store_true")
    c.set_defaults(fn=cmd_emit)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
