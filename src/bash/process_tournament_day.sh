#!/bin/bash

# Process all courts for one tournament day: merge GoPro clips + split into matchups.
# Usage: process_tournament_day.sh <day_directory> [options]
#
# Example:
#   ./process_tournament_day.sh src/output/June2026Tournament/2026-06-20 \
#     --schedule-dir src/output/June2026Tournament/schedule/generated \
#     --courts 2,3,4

set -e

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
combine_script="$script_dir/combine_gopro_videos.sh"
split_script="$script_dir/split_multi_source_videos.sh"

day_dir=""
schedule_dir=""
courts=""
tournament_name="June2026Tournament"
dry_run=false

show_usage() {
  cat << EOF
Usage: $0 <day_directory> [options]

  <day_directory>   Day folder containing court2/, court3/, etc.

Options:
  --schedule-dir DIR   Directory with {date}_courtN.jsonl files
  --courts LIST        Comma-separated court numbers (default: auto-detect)
  --tournament NAME    Tournament name for split output (default: June2026Tournament)
  --dry-run            Preview split only; skip merge and ffmpeg writes
  -h, --help           Show this help

Examples:
  $0 src/output/June2026Tournament/2026-06-20 --courts 2,3,4
  $0 src/output/June2026Tournament/2026-06-21 --courts 2,3 --dry-run
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --schedule-dir)
      schedule_dir="$2"
      shift 2
      ;;
    --courts)
      courts="$2"
      shift 2
      ;;
    --tournament)
      tournament_name="$2"
      shift 2
      ;;
    --dry-run)
      dry_run=true
      shift
      ;;
    -h|--help)
      show_usage
      exit 0
      ;;
    -*)
      echo "Unknown option: $1"
      show_usage
      exit 1
      ;;
    *)
      if [ -z "$day_dir" ]; then
        day_dir="$1"
      else
        echo "Unexpected argument: $1"
        show_usage
        exit 1
      fi
      shift
      ;;
  esac
done

if [ -z "$day_dir" ]; then
  show_usage
  exit 1
fi

if [[ "$day_dir" =~ \  ]]; then
  echo "Error: Day directory path contains spaces."
  exit 1
fi

if [ ! -d "$day_dir" ]; then
  echo "Error: Day directory not found: $day_dir"
  exit 1
fi

day_dir="$(cd "$day_dir" && pwd)"
day_name="$(basename "$day_dir")"

if [ -z "$schedule_dir" ]; then
  parent_dir="$(dirname "$day_dir")"
  if [ -d "$parent_dir/schedule/generated" ]; then
    schedule_dir="$parent_dir/schedule/generated"
  fi
fi

if [ -n "$schedule_dir" ] && [ ! -d "$schedule_dir" ]; then
  echo "Error: Schedule directory not found: $schedule_dir"
  exit 1
fi

if [ -z "$courts" ]; then
  courts=$(find "$day_dir" -maxdepth 1 -type d -name 'court[0-9]*' -exec basename {} \; | sed 's/court//' | sort -n | paste -sd, -)
fi

if [ -z "$courts" ]; then
  echo "Error: No court folders found under $day_dir"
  exit 1
fi

IFS=',' read -ra court_list <<< "$courts"

echo "=== Tournament Day Processing ==="
echo "Day:           $day_name"
echo "Directory:     $day_dir"
echo "Courts:        ${court_list[*]}"
echo "Schedule dir:  ${schedule_dir:-none}"
echo "Tournament:    $tournament_name"
echo "Dry run:       $dry_run"
echo ""

for court_num in "${court_list[@]}"; do
  court_num="$(echo "$court_num" | tr -d ' ')"
  court_dir="$day_dir/court${court_num}"
  court_label="Court ${court_num}"

  echo "--- Processing $court_label ---"

  if [ ! -d "$court_dir" ]; then
    echo "Warning: $court_dir not found, skipping."
    continue
  fi

  gx_count=$(find "$court_dir" -maxdepth 1 -name 'GX??????.MP4' 2>/dev/null | wc -l | tr -d ' ')
  gp_count=$(find "$court_dir" -maxdepth 1 -name 'GP??????.MP4' 2>/dev/null | wc -l | tr -d ' ')
  gopr_count=$(find "$court_dir" -maxdepth 1 -name 'GOPR????.MP4' 2>/dev/null | wc -l | tr -d ' ')
  gopro_count=$((gx_count + gp_count + gopr_count))

  if [ "$gopro_count" -eq 0 ] && [ "$dry_run" = false ]; then
    echo "No GoPro files in $court_dir, skipping."
    continue
  fi

  echo "Found $gopro_count GoPro files (GX: $gx_count, GP: $gp_count, GOPR: $gopr_count)"

  if [ "$dry_run" = false ]; then
    echo "Merging clips..."
    if ! "$combine_script" "$court_dir"; then
      echo "Error: merge failed for $court_label"
      continue
    fi
    echo "Merge complete."
  else
    echo "[DRY RUN] Would run: $combine_script $court_dir"
  fi

  merged_count=$(find "$court_dir/merged_videos" -name 'PROCESSED*.MP4' 2>/dev/null | wc -l | tr -d ' ')
  if [ "$merged_count" -eq 0 ]; then
    if [ "$dry_run" = true ]; then
      echo "[DRY RUN] No merged videos yet — split will run after SD import and merge."
    else
      echo "No merged videos in $court_dir/merged_videos, skipping split."
    fi
    echo ""
    continue
  fi

  games_jsonl=""
  if [ -n "$schedule_dir" ]; then
    games_jsonl="$schedule_dir/${day_name}_court${court_num}.jsonl"
  fi

  if [ -z "$games_jsonl" ] || [ ! -f "$games_jsonl" ]; then
    echo "Warning: No schedule file for $court_label (expected ${day_name}_court${court_num}.jsonl)"
    continue
  fi

  split_args=("$court_dir" "$games_jsonl" --tournament "$tournament_name" --court "$court_label")
  if [ "$dry_run" = true ]; then
    split_args+=(--debug)
  fi

  echo "Splitting matchups using $games_jsonl..."
  if ! "$split_script" "${split_args[@]}"; then
    echo "Error: split failed for $court_label"
    continue
  fi

  split_count=$(find "$court_dir/split_videos" -name '*.mp4' -o -name '*.MP4' 2>/dev/null | wc -l | tr -d ' ')
  echo "Done: $court_label ($split_count matchup files in split_videos/)"
  echo ""
done

echo "=== Day Processing Complete ==="
