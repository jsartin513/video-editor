#!/bin/bash

# One-time tournament folder setup and dependency check.
# Usage: setup_tournament.sh [tournament_root]

set -e

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"
tournament_root="${1:-$repo_root/src/output/June2026Tournament}"

if [[ "$tournament_root" =~ \  ]]; then
  echo "Error: Tournament path contains spaces."
  exit 1
fi

echo "=== June 2026 Tournament Setup ==="
echo "Root: $tournament_root"
echo ""

mkdir -p "$tournament_root/schedule/generated"
mkdir -p "$tournament_root/deliverables"

for day_courts in "2026-06-20:2,3,4" "2026-06-21:2,3"; do
  day="${day_courts%%:*}"
  courts="${day_courts##*:}"
  IFS=',' read -ra court_list <<< "$courts"
  for court in "${court_list[@]}"; do
    court_dir="$tournament_root/$day/court${court}"
    mkdir -p "$court_dir/merged_videos" "$court_dir/split_videos"
    notes_file="$court_dir/recording_notes.txt"
    if [ ! -f "$notes_file" ]; then
      cat > "$notes_file" << EOF
# Recording notes — Court ${court} — ${day}
# Log any camera stop/start events (battery swaps, angle adjustments, etc.)
# Format: HH:MM — event description
#
# Example:
# 09:00 — Round robin recording started
# 12:05 — Stopped for lunch
# 13:30 — Bracket play recording started
# 14:15 — Battery swap (~2 min gap)
EOF
    fi
  done
done

echo "Folder tree ready."
echo ""
echo "--- Court checklist ---"
echo "Sat Jun 20: court2, court3, court4 (court1 streams — skip)"
echo "Sun Jun 21: court2, court3 (court1 streams — skip)"
echo ""

missing=()
for cmd in ffmpeg ffprobe jq; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    missing+=("$cmd")
  fi
done

if [ ${#missing[@]} -gt 0 ]; then
  echo "Missing CLI tools: ${missing[*]}"
  echo "Run: $script_dir/install.sh"
else
  echo "CLI tools OK (ffmpeg, ffprobe, jq)"
fi

if [ -f "$repo_root/.venv/bin/python" ]; then
  if "$repo_root/.venv/bin/python" -c "import openpyxl" 2>/dev/null; then
    echo "Python venv OK (openpyxl)"
  else
    echo "Python venv found but openpyxl missing. Run: pip install -r requirements.txt"
  fi
else
  echo "Python venv not found. Run: python3 -m venv .venv && pip install -r requirements.txt"
fi

echo ""
echo "Next steps:"
echo "  1. Place schedule at $tournament_root/schedule/master_schedule.xlsx"
echo "  2. python src/scripts/excel_schedule_to_jsonl.py <excel> --output-dir $tournament_root/schedule/generated"
echo "  3. $script_dir/validate_tournament_setup.sh --dry-run"
