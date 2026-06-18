#!/bin/bash

# Insert no-blocking PA clips into a venue-wide overhead .wav after play-end countdowns.
# Usage: inject_no_blocking.sh --wav PATH --report PATH [options...]

set -e

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"
python_script="$repo_root/src/scripts/inject_no_blocking.py"

if [ ! -f "$python_script" ]; then
  echo "Error: inject_no_blocking.py not found at $python_script"
  exit 1
fi

for cmd in ffprobe ffmpeg python3; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Error: $cmd not installed."
    exit 1
  fi
done

PYTHON=""
if [ -x "$repo_root/.venv/bin/python" ]; then
  PYTHON="$repo_root/.venv/bin/python"
else
  PYTHON="python3"
fi

exec "$PYTHON" "$python_script" "$@"
