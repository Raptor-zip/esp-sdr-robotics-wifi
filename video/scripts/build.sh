#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -x .venv/bin/python ]; then
  uv venv .venv --python 3.12
  uv pip install --python .venv/bin/python -r requirements.txt
fi
if [ ! -d node_modules ]; then npm ci --no-audit --no-fund; fi
.venv/bin/python scripts/prepare.py
.venv/bin/manim -r 1080,900 --fps 30 --media_dir out/manim --disable_caching scripts/diagrams.py \
  RadioField ChannelOverlap Bandwidth QueueSplit RadioProtocols Sampling
.venv/bin/python scripts/copy_clips.py
npm run check
npm run stills
if [ "${1:-}" = "--stills" ]; then exit 0; fi
npm run render
.venv/bin/python scripts/deliver.py
.venv/bin/python scripts/verify.py
