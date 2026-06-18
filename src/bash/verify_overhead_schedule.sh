#!/bin/bash

# Verify venue-wide overhead .wav announcements against schedule JSONL files.
# Usage: verify_overhead_schedule.sh --wav PATH --schedule-dir DIR --date YYYY-MM-DD [options...]

set -e

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"
python_script="$repo_root/src/scripts/verify_overhead_schedule.py"

if [ ! -f "$python_script" ]; then
  echo "Error: verify_overhead_schedule.py not found at $python_script"
  exit 1
fi

for cmd in ffprobe python3; do
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

timeline_only=false
for arg in "$@"; do
  if [ "$arg" = "--timeline-only" ]; then
    timeline_only=true
    break
  fi
done

if [ "$timeline_only" = false ]; then
  if ! "$PYTHON" -c "import rapidfuzz" 2>/dev/null; then
    echo "Error: rapidfuzz not installed."
    echo "Run: pip install -r $repo_root/requirements-transcribe.txt"
    exit 1
  fi
  if ! "$PYTHON" -c "import faster_whisper" 2>/dev/null; then
    echo "Error: faster-whisper not installed."
    echo "Run: pip install -r $repo_root/requirements-transcribe.txt"
    exit 1
  fi
fi

exec "$PYTHON" "$python_script" "$@"
