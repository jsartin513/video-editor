#!/bin/bash

# Create per-team day folders for team GoPro SD card footage.
# Usage: setup_team_folders.sh [tournament_root] [--teams LIST]
#
# Example:
#   ./setup_team_folders.sh src/output/June2026Tournament
#   ./setup_team_folders.sh src/output/June2026Tournament --teams "Sister Sister,Fresh Prince"

set -e

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"
tournament_root="${1:-$repo_root/src/output/June2026Tournament}"
teams_filter=""

if [[ "$tournament_root" =~ \  ]]; then
  echo "Error: Tournament path contains spaces."
  exit 1
fi

shift || true
while [[ $# -gt 0 ]]; do
  case "$1" in
    --teams)
      teams_filter="$2"
      shift 2
      ;;
    -h|--help)
      echo "Usage: $0 [tournament_root] [--teams \"Team A,Team B\"]"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

schedule_xlsx="$tournament_root/schedule/master_schedule.xlsx"
if [ ! -f "$schedule_xlsx" ]; then
  echo "Error: Schedule not found at $schedule_xlsx"
  echo "Copy the Throw Down team schedules workbook there first."
  exit 1
fi

python_bin="$repo_root/.venv/bin/python"
if [ ! -x "$python_bin" ]; then
  python_bin="python3"
fi

list_args=("$python_bin" "$repo_root/src/scripts/excel_team_schedule_to_jsonl.py" "$schedule_xlsx" --list-teams)
if [ -n "$teams_filter" ]; then
  list_args+=(--teams "$teams_filter")
fi

echo "=== Team Folder Setup ==="
echo "Root: $tournament_root"
echo ""

mkdir -p "$tournament_root/teams"
mkdir -p "$tournament_root/schedule/generated_teams"

team_count=0
while IFS=$'\t' read -r team_name team_slug; do
  [ -n "$team_name" ] || continue
  for day in 2026-06-20 2026-06-21; do
    team_day_dir="$tournament_root/teams/$team_slug/$day"
    mkdir -p "$team_day_dir/merged_videos" "$team_day_dir/split_videos"
    notes_file="$team_day_dir/recording_notes.txt"
    if [ ! -f "$notes_file" ]; then
      cat > "$notes_file" << EOF
# Recording notes — ${team_name} — ${day}
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
  echo "  teams/${team_slug}/2026-06-20/"
  echo "  teams/${team_slug}/2026-06-21/"
  team_count=$((team_count + 1))
done < <("${list_args[@]}")

echo ""
echo "Created folders for $team_count team(s)."
echo ""
echo "Next steps:"
echo "  1. Generate team schedules:"
echo "     .venv/bin/python src/scripts/excel_team_schedule_to_jsonl.py \\"
echo "       $schedule_xlsx \\"
echo "       --output-dir $tournament_root/schedule/generated_teams \\"
echo "       --date 2026-06-20"
echo "     (Re-run with --date 2026-06-21 when Sunday sheets are filled in)"
echo "  2. Import team SD cards:"
echo "     $script_dir/import_team_sd.sh \\"
echo "       --dest $tournament_root/teams/sister_sister/2026-06-20 \\"
echo "       --card Team-Sister-Sister-Sat"
