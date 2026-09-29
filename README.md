# cutwire-drift skill

A Claude Code skill for driving the CutWire Drift video editor through its MCP
interface, distilled from a real production run.

```
cutwire-drift/
├── SKILL.md                              operating loop, broken ops, verification
├── references/
│   ├── field-notes.md                    what a real build costs and where it leaks
│   ├── production-pipeline.md            brief → design → source → VO → build → review
│   ├── longform-build.md                 scripted rebuild: Lottie, window cards, lanes, VO
│   └── design-system-template.md         craft notes plus a worked design system that passed review
└── scripts/
    ├── drift_cli.py                      HTTP client + `audit` for stray keys/transitions
    ├── keyframes.py                      motion spec → correct keyframe op batch
    ├── media_qc.py                       resolution/fps/bitrate gate + contact sheets
    ├── audio_master.py                   ebur128 measurement + loudnorm master
    ├── fetch_stock.py                    Mixkit/Pexels download with licence rows
    └── tts_fish.py                       Fish Audio VO that fits its slot
```

## Install

```bash
ln -s /home/suhasdissa/Projects/Drift-SKILL/cutwire-drift ~/.claude/skills/cutwire-drift
```

Then `/cutwire-drift` invokes it, or it triggers on its own when a task touches Drift.

## Requirements

- Drift running with **Settings → Agent access** on (the scripts read the url and token from `$XDG_RUNTIME_DIR/drift/mcp-session.json`), or `drift --headless --mcp-port 4731`.
- Python 3.9+, `ffmpeg`/`ffprobe` on PATH. No third-party Python packages.
- Optional: `PEXELS_API_KEY` for 4K stock, `FISH_API_KEY` for voiceover.

## Scripts outside the skill

Each script runs standalone with `--help`; nothing in `scripts/` needs Claude. The two
worth knowing about even when editing by hand:

```bash
scripts/drift_cli.py audit --verbose --emit-fix /tmp/keys.json
scripts/media_qc.py check --canvas 1920x1080 --crop-headroom 1.6 footage/*.mp4
```
