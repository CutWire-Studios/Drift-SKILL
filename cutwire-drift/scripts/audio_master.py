#!/usr/bin/env python3
"""Measure and master audio with ffmpeg, because Drift's own meters lie.

Observed on the 2026-09 build: analyze_loudness always reports true_peak_db 0.0,
normalize_volume misreads mono WAVs by about 3 dB and clips them, and the
utility.limiter effect adds gain instead of limiting. Everything below is
measured on rendered audio with ebur128, which agrees with what YouTube will do.

  audio_master.py measure export.mp4
  audio_master.py windows export.mp4 --ranges 30:36,42:48 --label vo,music
  audio_master.py master v2.mp4 v2-master.mp4 --target -14 --tp -1.0

`master` re-encodes audio only (video is stream-copied), so it is the honest way
to hit a delivery target when the mix inside Drift is already peak-limited.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys


def ebur128(path: str, start: float | None = None, dur: float | None = None) -> dict:
    cmd = ["ffmpeg", "-hide_banner", "-nostats"]
    if start is not None:
        cmd += ["-ss", f"{start:.3f}"]
    if dur is not None:
        cmd += ["-t", f"{dur:.3f}"]
    cmd += ["-i", path, "-map", "a:0", "-af", "ebur128=peak=true", "-f", "null", "-"]
    p = subprocess.run(cmd, capture_output=True, text=True)
    err = p.stderr
    tail = err[err.rfind("Summary:"):] if "Summary:" in err else err

    def grab(label):
        m = re.search(rf"{label}:\s*(-?\d+\.?\d*)", tail)
        return float(m.group(1)) if m else None

    return {"file": path,
            "start": start, "dur": dur,
            "lufs": grab("I"), "lra": grab("LRA"),
            "true_peak_db": grab("Peak"),
            "threshold": grab("Threshold")}


def rms_db(path: str, start: float, end: float) -> float | None:
    p = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-ss", f"{start:.3f}", "-t", f"{end - start:.3f}",
         "-i", path, "-map", "a:0", "-af", "astats=measure_overall=RMS_level:measure_perchannel=0",
         "-f", "null", "-"], capture_output=True, text=True)
    m = re.search(r"RMS level dB:\s*(-?\d+\.?\d*)", p.stderr)
    return float(m.group(1)) if m else None


def cmd_measure(a):
    r = ebur128(a.path, a.start, a.dur)
    print(json.dumps(r, indent=2))
    if r["lufs"] is None:
        sys.exit("no audio measured -- is there an audio stream?")
    notes = []
    if a.target is not None and abs(r["lufs"] - a.target) > 1.0:
        notes.append(f"integrated {r['lufs']} LUFS is more than 1 LU from the {a.target} target")
    if r["true_peak_db"] is not None and r["true_peak_db"] > a.tp:
        notes.append(f"true peak {r['true_peak_db']} dBTP is above {a.tp}")
    for n in notes:
        print("! " + n)
    print("# 0.0 dBTP exactly usually means the meter, not the mix. This one is ffmpeg's.")


def cmd_windows(a):
    labels = a.label.split(",") if a.label else []
    print(f"{'range':>16s} {'label':<14s} {'LUFS':>8s} {'RMS dB':>8s} {'peak dBTP':>10s}")
    for i, rng in enumerate(a.ranges.split(",")):
        s, _, e = rng.partition(":")
        s, e = float(s), float(e)
        r = ebur128(a.path, s, e - s)
        rms = rms_db(a.path, s, e)
        label = labels[i] if i < len(labels) else ""
        print(f"{s:7.2f}-{e:<8.2f} {label:<14s} "
              f"{(r['lufs'] if r['lufs'] is not None else float('nan')):>8.1f} "
              f"{(rms if rms is not None else float('nan')):>8.1f} "
              f"{(r['true_peak_db'] if r['true_peak_db'] is not None else float('nan')):>10.1f}")
    print("\n# Voice should sit roughly 8-12 LU above the ducked music bed under it.")


def cmd_master(a):
    pre = ebur128(a.src)
    if pre["lufs"] is None:
        sys.exit("no audio to master")
    print("before: " + json.dumps(pre))
    # two-pass loudnorm: pass 1 measures, pass 2 corrects with those numbers
    p1 = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", a.src, "-map", "a:0", "-af",
         f"loudnorm=I={a.target}:TP={a.tp}:LRA=11:print_format=json", "-f", "null", "-"],
        capture_output=True, text=True)
    blob = p1.stderr[p1.stderr.rfind("{"):p1.stderr.rfind("}") + 1]
    m = json.loads(blob)
    af = (f"loudnorm=I={a.target}:TP={a.tp}:LRA=11"
          f":measured_I={m['input_i']}:measured_TP={m['input_tp']}"
          f":measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}"
          f":offset={m['target_offset']}:linear=true:print_format=summary")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", a.src, "-map", "0",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", f"{a.abr}k", "-af", af, a.dst],
                   check=True)
    post = ebur128(a.dst)
    print("after:  " + json.dumps(post))
    print(f"# video stream copied; only the audio was re-encoded ({a.abr} kbps AAC)")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("measure")
    c.add_argument("path"); c.add_argument("--start", type=float); c.add_argument("--dur", type=float)
    c.add_argument("--target", type=float, default=-14.0); c.add_argument("--tp", type=float, default=-1.0)
    c.set_defaults(fn=cmd_measure)

    c = sub.add_parser("windows", help="per-range loudness, e.g. voice vs music")
    c.add_argument("path"); c.add_argument("--ranges", required=True, help="30:36,42:48")
    c.add_argument("--label", help="comma-separated labels")
    c.set_defaults(fn=cmd_windows)

    c = sub.add_parser("master", help="two-pass loudnorm to a delivery target")
    c.add_argument("src"); c.add_argument("dst")
    c.add_argument("--target", type=float, default=-14.0); c.add_argument("--tp", type=float, default=-1.0)
    c.add_argument("--abr", type=int, default=192)
    c.set_defaults(fn=cmd_master)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
