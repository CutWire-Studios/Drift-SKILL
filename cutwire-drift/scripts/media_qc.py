#!/usr/bin/env python3
"""Gate footage before it reaches the timeline, and look at it.

The first pilot of a video series was rejected because 1080p 16:9 clips had been
cover-cropped into a 1080x1920 canvas, roughly a 3x upscale. Resolution is the
one defect you cannot fix later in the edit, so check it at download time.

  media_qc.py check --canvas 1080x1920 assets/video/*.mp4
  media_qc.py check --canvas 1920x1080 --crop-headroom 1.6 --min-fps 50 clip.mp4
  media_qc.py sheet clip.mp4 --n 9 --out /tmp/clip.jpg      # then Read the jpg

--crop-headroom is the factor you plan to zoom or reframe by: a 4K source that
will be punched in 1.6x must still be >= canvas after the punch.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile


def probe(path: str) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height,r_frame_rate,bit_rate,codec_name,pix_fmt:format=duration,bit_rate",
         "-of", "json", path],
        capture_output=True, text=True)
    if out.returncode != 0:
        return {"error": out.stderr.strip()[:200]}
    d = json.loads(out.stdout)
    if not d.get("streams"):
        return {"error": "no video stream"}
    s, f = d["streams"][0], d.get("format", {})
    num, _, den = s.get("r_frame_rate", "0/1").partition("/")
    fps = float(num) / float(den or 1) if float(den or 1) else 0.0
    br = int(s.get("bit_rate") or f.get("bit_rate") or 0) / 1e6
    return {"w": s["width"], "h": s["height"], "fps": round(fps, 3),
            "dur": round(float(f.get("duration", 0)), 3), "mbps": round(br, 1),
            "codec": s.get("codec_name"), "pix": s.get("pix_fmt")}


def cmd_check(a):
    cw, _, ch = a.canvas.lower().partition("x")
    cw, ch = int(cw), int(ch)
    need_w, need_h = cw * a.crop_headroom, ch * a.crop_headroom
    failed = 0
    print(f"{'file':44s} {'WxH':>11s} {'fps':>6s} {'dur':>7s} {'Mbps':>6s}  verdict")
    for path in a.files:
        m = probe(path)
        name = os.path.basename(path)[:44]
        if "error" in m:
            print(f"{name:44s} {'-':>11s} {'-':>6s} {'-':>7s} {'-':>6s}  UNREADABLE ({m['error']})")
            failed += 1
            continue
        bad = []
        # aspect-aware: the source must cover the canvas box after the planned punch-in
        scale = max(need_w / m["w"], need_h / m["h"])
        if scale > 1.0001:
            bad.append(f"UPSCALE {scale:.2f}x")
        if a.min_fps and m["fps"] + 0.01 < a.min_fps:
            bad.append(f"FPS {m['fps']}")
        if a.min_bitrate and m["mbps"] and m["mbps"] < a.min_bitrate:
            bad.append(f"BITRATE {m['mbps']}")
        if a.min_dur and m["dur"] < a.min_dur:
            bad.append(f"SHORT {m['dur']}s")
        verdict = "PASS" if not bad else " ".join(bad)
        failed += bool(bad)
        print(f"{name:44s} {m['w']}x{m['h']:<5d} {m['fps']:>6.2f} {m['dur']:>7.2f} {m['mbps']:>6.1f}  {verdict}")
    if failed:
        print(f"\n{failed} file(s) failed. Re-source them; an upscaled clip cannot be fixed in the edit.")
    sys.exit(1 if failed and a.strict else 0)


def cmd_sheet(a):
    m = probe(a.path)
    if "error" in m:
        sys.exit(m["error"])
    dur = m["dur"]
    times = [dur * (i + 0.5) / a.n for i in range(a.n)]
    cols = a.cols or min(a.n, 4)
    rows = (a.n + cols - 1) // cols
    with tempfile.TemporaryDirectory() as tmp:
        for i, t in enumerate(times):
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", a.path,
                            "-frames:v", "1", "-vf", f"scale={a.tile}:-1",
                            os.path.join(tmp, f"f{i:03d}.jpg")], check=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", os.path.join(tmp, "f%03d.jpg"),
                        "-filter_complex", f"tile={cols}x{rows}", a.out], check=True)
    print(json.dumps({"sheet": a.out, "grid": f"{cols}x{rows}", "source": m,
                      "tiles": [{"i": i, "t": round(t, 2)} for i, t in enumerate(times)]}, indent=2))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check")
    c.add_argument("files", nargs="+")
    c.add_argument("--canvas", required=True, help="e.g. 1920x1080")
    c.add_argument("--crop-headroom", type=float, default=1.0)
    c.add_argument("--min-fps", type=float, default=0)
    c.add_argument("--min-bitrate", type=float, default=0, help="Mbps")
    c.add_argument("--min-dur", type=float, default=0, help="seconds")
    c.add_argument("--strict", action="store_true", help="exit 1 on any failure")
    c.set_defaults(fn=cmd_check)

    c = sub.add_parser("sheet", help="contact sheet you can Read as an image")
    c.add_argument("path"); c.add_argument("--n", type=int, default=9)
    c.add_argument("--cols", type=int); c.add_argument("--tile", type=int, default=480)
    c.add_argument("--out", default="/tmp/sheet.jpg")
    c.set_defaults(fn=cmd_sheet)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
