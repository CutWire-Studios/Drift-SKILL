#!/usr/bin/env python3
"""Find, download and credit royalty-free footage and music.

Two sources, because they fail in opposite directions:
  mixkit  no key needed, license is blanket-free with no attribution, but free
          video tops out at 1080p -- fine for a 1080p canvas, never for 4K or
          for anything you will punch into.
  pexels  needs $PEXELS_API_KEY, has real 4K, attribution is appreciated not
          required. This is where footage for a reframe/zoom beat comes from.

Every download appends a row to <dir>/../credits.md, so the licence trail is
built as you go instead of being reconstructed later from shell history.

  fetch_stock.py mixkit neon --kind video
  fetch_stock.py mixkit electronic --kind music --download assets/music
  fetch_stock.py pexels "skateboard sunset" --min-width 3840 --min-fps 50 --download assets/video
  fetch_stock.py pexels "city night" --download assets/video --name b03-city
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request

UA = {"User-Agent": "Mozilla/5.0"}


def get(url: str, headers: dict | None = None) -> bytes:
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def json_objects(html: str, type_name: str) -> list[dict]:
    """Pull inline JSON-LD objects of one @type out of a page.

    Mixkit inlines them without a ld+json script wrapper, and the key order
    differs between video (@type first) and music (@id first), so this finds the
    type marker and brace-matches outward from it.
    """
    out, seen = [], set()
    for m in re.finditer(rf'"@type"\s*:\s*"{type_name}"', html):
        start, depth = m.start(), 0
        while start >= 0:
            if html[start] == "}":
                depth += 1
            elif html[start] == "{":
                if depth == 0:
                    break
                depth -= 1
            start -= 1
        if start < 0 or start in seen:
            continue
        seen.add(start)
        depth, j = 0, start
        while j < len(html):
            if html[j] == "{":
                depth += 1
            elif html[j] == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        try:
            out.append(json.loads(html[start:j + 1]))
        except json.JSONDecodeError:
            pass
    return out


def credits_row(dirpath: str, row: dict):
    path = os.path.join(os.path.dirname(os.path.abspath(dirpath)), "credits.md")
    new = not os.path.exists(path)
    with open(path, "a") as fh:
        if new:
            fh.write("# Credits\n\n| file | title | author | source | licence |\n|---|---|---|---|---|\n")
        fh.write(f"| {row['file']} | {row['title']} | {row.get('author', '-')} | "
                 f"{row['source']} | {row['licence']} |\n")
    return path


def download(url: str, dest: str) -> int:
    data = get(url)
    with open(dest, "wb") as fh:
        fh.write(data)
    return len(data)


def cmd_mixkit(a):
    term = urllib.parse.quote(a.query.strip().replace(" ", "-"))
    if a.query.startswith("http"):
        candidates = [a.query]
    elif a.kind == "music":
        # music browses by tag, video by category; try both spellings
        candidates = [f"https://mixkit.co/free-stock-music/tag/{term}/",
                      f"https://mixkit.co/free-stock-music/{term}/"]
    else:
        candidates = [f"https://mixkit.co/free-stock-video/{term}/",
                      f"https://mixkit.co/free-stock-video/tag/{term}/"]
    want = "MusicRecording" if a.kind == "music" else "VideoObject"
    items, url = [], candidates[0]
    for cand in candidates:
        try:
            html = get(cand).decode("utf-8", "replace")
        except Exception:
            continue
        items = json_objects(html, want)
        if items:
            url = cand
            break
    if not items:
        sys.exit("nothing parsed from " + " or ".join(candidates) +
                 " -- check the term exists as a Mixkit page")
    rows = []
    for it in items[: a.limit]:
        content = it.get("contentUrl") or it.get("url")
        page = it.get("@id", "")
        page = page.split("#")[0] if page.startswith("http") else ""
        rows.append({"title": it.get("name"), "url": content,
                     "page": page,
                     "author": it.get("byArtist") or "Mixkit",
                     "quality": (it.get("videoQuality") or [None])[0],
                     "dur": it.get("duration"), "licence": it.get("license")})
    if not a.download:
        print(json.dumps(rows, indent=2))
        note = "" if a.kind == "music" else " Mixkit free video is 1080p max."
        print(f"\n# {len(items)} item(s) on {url}.{note}", file=sys.stderr)
        return
    os.makedirs(a.download, exist_ok=True)
    for n, r in enumerate(rows):
        if not r["url"]:
            continue
        ext = ".mp3" if a.kind == "music" else ".mp4"
        base = a.name or re.sub(r"[^a-z0-9]+", "-", (r["title"] or "clip").lower()).strip("-")[:40]
        fn = f"{base}{'' if len(rows) == 1 else f'-{n:02d}'}{ext}"
        dest = os.path.join(a.download, fn)
        size = download(r["url"], dest)
        print(f"{dest}  {size / 1e6:.1f} MB  {r['title']}")
        credits_row(a.download, {"file": fn, "title": r["title"], "author": r["author"],
                                 "source": r["page"] or r["url"],
                                 "licence": "Mixkit Free License (commercial, no attribution)"})
    print("# verify before use: media_qc.py check --canvas <WxH> " + a.download + "/*")


def cmd_pexels(a):
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        sys.exit("PEXELS_API_KEY is not set. Get a free key at pexels.com/api and export it.")
    q = urllib.parse.urlencode({"query": a.query, "per_page": a.limit,
                                "orientation": a.orientation, "size": "large"})
    data = json.loads(get(f"https://api.pexels.com/videos/search?{q}", {"Authorization": key}))
    picks = []
    for v in data.get("videos", []):
        files = [f for f in v["video_files"]
                 if (f.get("width") or 0) >= a.min_width and (f.get("fps") or 0) >= a.min_fps]
        if not files:
            continue
        best = max(files, key=lambda f: (f["width"], f.get("fps") or 0))
        picks.append({"title": (v.get("url", "").rstrip("/").split("/")[-1] or "pexels").replace("-", " "),
                      "author": v["user"]["name"], "page": v["url"], "dur": v.get("duration"),
                      "w": best["width"], "h": best["height"], "fps": best.get("fps"),
                      "url": best["link"], "licence": "Pexels License (commercial, attribution appreciated)"})
    if not picks:
        sys.exit(f"no clip matched >= {a.min_width}px @ {a.min_fps}fps for '{a.query}' "
                 f"-- widen the query or lower the bar deliberately, and log it")
    if not a.download:
        print(json.dumps(picks, indent=2))
        return
    os.makedirs(a.download, exist_ok=True)
    for n, p in enumerate(picks[: a.take]):
        base = a.name or re.sub(r"[^a-z0-9]+", "-", p["title"].lower()).strip("-")[:40]
        fn = f"{base}{'' if a.take == 1 else f'-{n:02d}'}.mp4"
        dest = os.path.join(a.download, fn)
        size = download(p["url"], dest)
        print(f"{dest}  {size / 1e6:.1f} MB  {p['w']}x{p['h']}@{p['fps']}  {p['page']}")
        credits_row(a.download, {"file": fn, "title": p["title"], "author": p["author"],
                                 "source": p["page"], "licence": p["licence"]})
    print("# verify before use: media_qc.py check --canvas <WxH> " + a.download + "/*")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("mixkit")
    c.add_argument("query", help="tag term or a full mixkit.co page URL")
    c.add_argument("--kind", choices=["video", "music"], default="video")
    c.add_argument("--limit", type=int, default=12)
    c.add_argument("--download", metavar="DIR"); c.add_argument("--name")
    c.set_defaults(fn=cmd_mixkit)

    c = sub.add_parser("pexels")
    c.add_argument("query")
    c.add_argument("--min-width", type=int, default=1920)
    c.add_argument("--min-fps", type=float, default=0)
    c.add_argument("--orientation", default="landscape", choices=["landscape", "portrait", "square"])
    c.add_argument("--limit", type=int, default=15, help="candidates to fetch")
    c.add_argument("--take", type=int, default=1, help="how many to download")
    c.add_argument("--download", metavar="DIR"); c.add_argument("--name")
    c.set_defaults(fn=cmd_pexels)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
