#!/usr/bin/env python3
"""Generate voiceover lines with Fish Audio that actually fit their slot.

A voiceover line is not free text: it has to land inside a beat. Measured on
Fish Audio s2-pro, delivery runs about 220-260 wpm, not the ~150 wpm most
scripts are written for, so lines drafted by eye come out long and the fix gets
made blind. This synthesises, trims, normalises, measures, and retries with a
brisker read or your own shorter wording until the line fits -- and tells you
plainly when no retry can save it.

Line file (JSON):
  [{"id": "B05", "text": "[confident] Loud room behind you?", "max_sec": 1.4,
    "alt": "[confident] Loud room?"}]

  tts_fish.py estimate lines.json                 # no API calls, catches doomed lines
  tts_fish.py speak lines.json --out vo/ --reference-id <voice-id>

The key comes from $FISH_API_KEY and is never written to disk, logged or put in
a manifest. If a key has ever been pasted into a chat, rotate it.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request

API = "https://api.fish.audio/v1/tts"
WPM = 240.0  # measured, not the 150 wpm a script is usually written for


def words(text: str) -> int:
    return len(re.sub(r"\[[^\]]*\]", " ", text).split())


def duration(path: str) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", path], capture_output=True, text=True)
    return float(out.stdout.strip() or 0)


def loudness(path: str) -> float | None:
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af",
                        "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True)
    m = re.search(r"I:\s*(-?\d+\.?\d*) LUFS", p.stderr[p.stderr.rfind("Summary:"):])
    return float(m.group(1)) if m else None


def post(src: str, dst: str, lufs: float, tp: float):
    """Trim the silence Fish leaves at both ends, then normalise to the mix target."""
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", src, "-af",
         "silenceremove=start_periods=1:start_silence=0.05:start_threshold=-50dB:"
         "detection=peak,areverse,"
         "silenceremove=start_periods=1:start_silence=0.05:start_threshold=-50dB:"
         "detection=peak,areverse,"
         f"loudnorm=I={lufs}:TP={tp}:LRA=7",
         "-ar", "48000", "-ac", "1", dst], check=True)


def synth(text: str, ref: str | None, model: str, dst: str):
    key = os.environ.get("FISH_API_KEY")
    if not key:
        sys.exit("FISH_API_KEY is not set. export it in this shell; do not put it in a file.")
    body = {"text": text, "format": "mp3"}
    if ref:
        body["reference_id"] = ref
    req = urllib.request.Request(
        API, data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "model": model})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    with open(dst, "wb") as fh:
        fh.write(data)


def briskify(text: str) -> str:
    """Same words, faster read: the cheapest retry, and it kept meaning intact in practice."""
    m = re.match(r"^\s*\[([^\]]*)\]\s*(.*)$", text, re.S)
    if m:
        tags = [t.strip() for t in m.group(1).split(",")]
        if "brisk" not in tags:
            tags.append("brisk")
        return f"[{', '.join(tags)}] {m.group(2)}"
    return f"[brisk] {text}"


def cmd_estimate(a):
    lines = json.load(open(a.lines))
    bad = 0
    print(f"{'id':8s} {'words':>5s} {'est s':>7s} {'max s':>7s}  verdict")
    for ln in lines:
        w = words(ln["text"])
        est = w / (a.wpm / 60.0)
        mx = ln.get("max_sec")
        verdict = "-"
        if mx:
            if est > mx:
                verdict = f"TOO LONG by {est - mx:.2f}s -- cut {max(1, round((est - mx) * a.wpm / 60))} word(s)"
                bad += 1
            elif est > mx * 0.85:
                verdict = "tight"
            else:
                verdict = "fits"
        print(f"{ln['id']:8s} {w:>5d} {est:>7.2f} {(mx or 0):>7.2f}  {verdict}")
    print(f"\n# {a.wpm} wpm is the measured Fish s2-pro rate. Rewrite the long lines before spending API calls.")
    sys.exit(1 if bad and a.strict else 0)


def cmd_speak(a):
    lines = json.load(open(a.lines))
    os.makedirs(a.out, exist_ok=True)
    manifest = []
    for ln in lines:
        attempts, final = [], None
        candidates = [ln["text"], briskify(ln["text"])]
        if ln.get("alt"):
            candidates.append(ln["alt"])
        for n, text in enumerate(candidates):
            raw = os.path.join(a.out, f".{ln['id']}-raw.mp3")
            wav = os.path.join(a.out, f"{ln['id']}.wav")
            synth(text, a.reference_id, a.model, raw)
            post(raw, wav, a.lufs, a.tp)
            os.remove(raw)
            d = duration(wav)
            attempts.append({"try": n + 1, "text": text, "dur": round(d, 3)})
            print(f"{ln['id']} try {n + 1}: {d:.2f}s "
                  f"(limit {ln.get('max_sec', '-')}) :: {text[:60]}")
            final = {"id": ln["id"], "file": wav, "text": text, "dur": round(d, 3),
                     "lufs": loudness(wav), "attempts": attempts}
            if not ln.get("max_sec") or d <= ln["max_sec"]:
                break
        if ln.get("max_sec") and final["dur"] > ln["max_sec"]:
            final["over_by"] = round(final["dur"] - ln["max_sec"], 3)
            print(f"  ! {ln['id']} is still {final['over_by']}s over. "
                  f"Shorten the words -- do not just speed up the read again.")
        manifest.append(final)
    path = os.path.join(a.out, "vo-manifest.json")
    with open(path, "w") as fh:
        json.dump(manifest, fh, indent=2)
    print(f"\n{path}")
    over = [m for m in manifest if "over_by" in m]
    if over:
        print(f"# {len(over)} line(s) do not fit: " + ", ".join(m["id"] for m in over))
    sys.exit(1 if over and a.strict else 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("estimate", help="predict line lengths without calling the API")
    c.add_argument("lines"); c.add_argument("--wpm", type=float, default=WPM)
    c.add_argument("--strict", action="store_true")
    c.set_defaults(fn=cmd_estimate)

    c = sub.add_parser("speak")
    c.add_argument("lines"); c.add_argument("--out", required=True)
    c.add_argument("--reference-id"); c.add_argument("--model", default="s2-pro")
    c.add_argument("--lufs", type=float, default=-16.0); c.add_argument("--tp", type=float, default=-2.0)
    c.add_argument("--strict", action="store_true")
    c.set_defaults(fn=cmd_speak)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
