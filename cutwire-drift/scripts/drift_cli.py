#!/usr/bin/env python3
"""Talk to a running CutWire Drift editor over its MCP HTTP endpoint.

Why this exists alongside the mcp__drift__* tools:
  - Mechanical batches (hundreds of keyframe ops) flood the agent context with
    reply JSON. Piping them through here keeps the transcript small.
  - When the MCP client connection drops mid-session the tools disappear and do
    not come back on their own. This keeps working.
  - `audit` catches what silently ruins a build: keyframes written outside the
    clip they belong to, one-key animations, and implausible transitions.

Endpoint discovery, in order:
  $DRIFT_MCP_URL + $DRIFT_MCP_TOKEN
  $XDG_RUNTIME_DIR/drift/mcp-session.json   (written by the editor; token rotates per launch)
  $DRIFT_MCP_SESSION_PATH
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request

TIMEOUT = 300


def endpoint() -> tuple[str, str]:
    url, token = os.environ.get("DRIFT_MCP_URL"), os.environ.get("DRIFT_MCP_TOKEN")
    if url and token:
        return url, token
    path = os.environ.get("DRIFT_MCP_SESSION_PATH") or os.path.join(
        os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"), "drift", "mcp-session.json"
    )
    try:
        with open(path) as fh:
            s = json.load(fh)
        return s["url"], s["token"]
    except FileNotFoundError:
        sys.exit(
            f"No Drift session file at {path}.\n"
            "Open Drift and turn on Settings -> Agent access, or run "
            "`drift --headless --mcp-port 4731 --mcp-token <T>` and export DRIFT_MCP_URL/DRIFT_MCP_TOKEN."
        )


def rpc(name: str, arguments: dict) -> list:
    url, token = endpoint()
    body = json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
         "params": {"name": name, "arguments": arguments}}
    ).encode()
    req = urllib.request.Request(
        url, data=body,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            reply = json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code} from Drift: {e.read()[:300].decode(errors='replace')}")
    except urllib.error.URLError as e:
        sys.exit(f"Cannot reach Drift at {url}: {e.reason}")
    if "error" in reply:
        sys.exit(f"JSON-RPC error: {json.dumps(reply['error'])[:400]}")
    return reply["result"]["content"]


def text_of(content: list) -> dict | str:
    for block in content:
        if block.get("type") == "text":
            try:
                return json.loads(block["text"])
            except json.JSONDecodeError:
                return block["text"]
    return {}


def save_image(content: list, out: str | None) -> str | None:
    for block in content:
        if block.get("type") == "image":
            path = out or "/tmp/drift-frame.jpg"
            with open(path, "wb") as fh:
                fh.write(base64.b64decode(block["data"]))
            return path
    return None


def dump(obj, compact=False):
    print(json.dumps(obj, indent=None if compact else 2, sort_keys=True))


# ---------------------------------------------------------------- commands


def cmd_call(a):
    args = json.loads(a.args) if a.args else {}
    content = rpc(a.name, args)
    img = save_image(content, a.out)
    dump(text_of(content))
    if img:
        print(f"# image saved to {img}", file=sys.stderr)


def cmd_inspect(a):
    args = {}
    for key in ("clips", "detail", "cues", "verbose"):
        if getattr(a, key):
            args[key] = True
    if a.track is not None:
        args["track"] = a.track
    if a.clip:
        args["clip"] = a.clip
    if a.since is not None:
        args["since"] = a.since
    dump(text_of(rpc("inspect", args)))


def cmd_apply(a):
    raw = sys.stdin.read() if a.file == "-" else open(a.file).read()
    parsed = json.loads(raw)
    ops = parsed["ops"] if isinstance(parsed, dict) else parsed
    if a.chunk:
        chunks = [ops[i:i + a.chunk] for i in range(0, len(ops), a.chunk)]
    else:
        chunks = [ops]
    done_total = 0
    for n, chunk in enumerate(chunks):
        res = text_of(rpc("apply", {"ops": chunk}))
        done = res.get("done", [])
        done_total += len(done)
        if not res.get("ok"):
            idx = res.get("stopped", len(done))
            print(json.dumps({
                "ok": False, "chunk": n, "ran": done_total,
                "stopped_at_op": idx, "tool": res.get("tool"),
                "failed": res.get("failed"),
                "op": chunk[idx] if idx < len(chunk) else None,
            }, indent=2))
            print("# apply is not atomic: the ops before this one are applied.", file=sys.stderr)
            sys.exit(1)
    print(json.dumps({"ok": True, "ops_applied": done_total, "batches": len(chunks)}))
    if a.verbose:
        dump(done)


def cmd_capture(a):
    content = rpc("capture", {"at": a.at})
    print(json.dumps(text_of(content)))
    print(save_image(content, a.out or f"/tmp/drift-{a.at}.jpg"))


def cmd_frames(a):
    args = {"cols": a.cols} if a.cols else {}
    if a.at:
        args["at"] = [float(x) for x in a.at.split(",")]
    else:
        args["n"] = a.n
        if a.start is not None:
            args["start"] = a.start
        if a.end is not None:
            args["end"] = a.end
    content = rpc("frames", args)
    print(json.dumps(text_of(content)))
    print(save_image(content, a.out or "/tmp/drift-sheet.jpg"))


def cmd_schema(a):
    res = text_of(rpc("toolbox", {"ops": a.ops}))
    for tool in res.get("tools", []):
        print(f"### {tool['name']}\n{tool['description']}\n{json.dumps(tool['inputSchema'], indent=2)}\n")


def cmd_audit(a):
    p = text_of(rpc("inspect", {"clips": True, "detail": True}))
    dur = p.get("dur", 0)
    problems: list[str] = []
    notes: list[str] = []
    fixes: list[dict] = []

    print(f"project  {p.get('w')}x{p.get('h')} @ {p.get('fps')}fps  dur={dur}s  "
          f"overlap={p.get('overlap')}  dirty={p.get('dirty')}  rev={p.get('revision')}")
    print(f"path     {p.get('path') or '<never saved>'}")

    for track in p.get("tracks", []):
        ti, items = track.get("i"), track.get("items") or []
        if not items and track.get("clips", 0) == 0:
            notes.append(f"track {ti} ({track.get('type')}) is empty")

        trs = track.get("transitions") or []
        spans = []
        for tr in trs:
            start = tr.get("start", tr.get("at", 0))
            length = tr.get("duration", tr.get("dur", 0))
            spans.append((start, start + length, tr.get("id")))
            if start < 0:
                problems.append(f"track {ti} transition {tr.get('id')} starts at {start}s (negative)")
            if length > 2:
                problems.append(f"track {ti} transition {tr.get('id')} is {length}s long (phantom crossfades are usually long)")
            if start + length > dur + 0.001:
                problems.append(f"track {ti} transition {tr.get('id')} ends at {start + length}s, past the timeline end")
        spans.sort()
        for (s1, e1, i1), (s2, e2, i2) in zip(spans, spans[1:]):
            if s2 < e1 - 0.001:
                problems.append(f"track {ti} transitions {i1} and {i2} overlap ({s1}-{e1} / {s2}-{e2})")
        if trs:
            notes.append(f"track {ti}: {len(trs)} transition(s) " +
                         ", ".join(f"{i}@{s:.2f}-{e:.2f}" for s, e, i in spans))

        for it in items:
            start = it.get("start", 0)
            end = start + it.get("duration", 0)
            label = f"{it.get('kind')} '{it.get('name', '')[:28]}' {it.get('id')}"
            for prop, anim in (it.get("keyframes") or {}).items():
                pts = anim.get("points") or []
                outside = [k["seconds"] for k in pts if k["seconds"] < start - 0.001 or k["seconds"] > end + 0.001]
                if outside:
                    problems.append(
                        f"track {ti} {label}: {prop} has {len(outside)} key(s) outside the clip "
                        f"[{start:.2f}-{end:.2f}] at {['%.2f' % t for t in outside]} "
                        f"-- written with the playhead outside the clip; remove_keyframe them")
                    for t in outside:
                        fixes.append({"tool": "remove_keyframe",
                                      "args": {"clip": it.get("id"), "prop": prop, "at": t}})
                if len(pts) == 1 and not outside:
                    notes.append(
                        f"track {ti} {label}: {prop} has a single key at {pts[0]['seconds']:.2f} "
                        f"-- holds; set_transform moves that key instead of adding a second one")

    print()
    if problems:
        print(f"PROBLEMS ({len(problems)})")
        for x in problems:
            print("  ! " + x)
    else:
        print("PROBLEMS  none")
    if notes and a.verbose:
        print("\nNOTES")
        for x in notes:
            print("  - " + x)
    if a.emit_fix and fixes:
        with open(a.emit_fix, "w") as fh:
            json.dump(fixes, fh, indent=2)
        print(f"\n{len(fixes)} remove_keyframe op(s) written to {a.emit_fix}")
        print("# read it, then: drift_cli.py apply " + a.emit_fix)
        print("# remove_keyframe deletes the NEAREST key with no distance limit -- "
              "these times came straight from inspect, so they are exact.")
    sys.exit(1 if problems and a.strict else 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("call", help="call any tool: call inspect '{\"clips\":true}'")
    c.add_argument("name"); c.add_argument("args", nargs="?"); c.add_argument("--out")
    c.set_defaults(fn=cmd_call)

    c = sub.add_parser("inspect")
    c.add_argument("--clips", action="store_true"); c.add_argument("--detail", action="store_true")
    c.add_argument("--cues", action="store_true"); c.add_argument("--verbose", action="store_true")
    c.add_argument("--track", type=int); c.add_argument("--clip"); c.add_argument("--since", type=int)
    c.set_defaults(fn=cmd_inspect)

    c = sub.add_parser("apply", help="run an ops array (file or - for stdin)")
    c.add_argument("file"); c.add_argument("--chunk", type=int, default=0,
                                           help="split into batches of N ops (each its own undo step)")
    c.add_argument("--verbose", action="store_true")
    c.set_defaults(fn=cmd_apply)

    c = sub.add_parser("capture"); c.add_argument("--at", type=float, required=True)
    c.add_argument("--out"); c.set_defaults(fn=cmd_capture)

    c = sub.add_parser("frames")
    c.add_argument("--at", help="comma-separated times"); c.add_argument("--n", type=int, default=12)
    c.add_argument("--start", type=float); c.add_argument("--end", type=float)
    c.add_argument("--cols", type=int); c.add_argument("--out")
    c.set_defaults(fn=cmd_frames)

    c = sub.add_parser("schema", help="full JSON schema for named ops")
    c.add_argument("ops", nargs="+"); c.set_defaults(fn=cmd_schema)

    c = sub.add_parser("audit", help="stray keyframes, phantom transitions, empty lanes")
    c.add_argument("--verbose", action="store_true"); c.add_argument("--strict", action="store_true")
    c.add_argument("--emit-fix", metavar="FILE",
                   help="write an ops array that removes the stray keys (review before applying)")
    c.set_defaults(fn=cmd_audit)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
