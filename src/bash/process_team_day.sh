#!/bin/bash

# Process team GoPro footage for one tournament day: merge clips + split into matchups.
# Usage: process_team_day.sh <tournament_root> --date YYYY-MM-DD [options]
#
# Example:
#   ./process_team_day.sh src/output/June2026Tournament \
#     --date 2026-06-20 --teams sister_sister,fresh_prince

set -e

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
combine_script="$script_dir/combine_gopro_videos.sh"
split_script="$script_dir/split_multi_source_videos.sh"

tournament_root=""
day=""
schedule_dir=""
teams=""
tournament_name=""
dry_run=false

show_usage() {
  cat << EOF
Usage: $0 <tournament_root> --date YYYY-MM-DD [options]

  <tournament_root>   Tournament folder containing teams/ and schedule/

Options:
  --date DATE          Tournament day (required), e.g. 2026-06-20
  --schedule-dir DIR   Directory with {date}_{team_slug}.jsonl files
  --teams LIST         Comma-separated team slugs (default: all teams with footage)
  --tournament NAME    Tournament name for split output (default: parent folder name)
  --dry-run            Preview split only; skip merge and ffmpeg writes
  -h, --help           Show this help

Examples:
  $0 src/output/June2026Tournament --date 2026-06-20 --teams sister_sister
  $0 src/output/June2026Tournament --date 2026-06-21 --dry-run
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --date)
      day="$2"
      shift 2
      ;;
    --schedule-dir)
      schedule_dir="$2"
      shift 2
      ;;
    --teams)
      teams="$2"
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
      if [ -z "$tournament_root" ]; then
        tournament_root="$1"
      else
        echo "Unexpected argument: $1"
        show_usage
        exit 1
      fi
      shift
      ;;
  esac
done

if [ -z "$tournament_root" ] || [ -z "$day" ]; then
  show_usage
  exit 1
fi

if [[ "$tournament_root" =~ \  ]]; then
  echo "Error: Tournament root path contains spaces."
  exit 1
fi

if [ ! -d "$tournament_root" ]; then
  echo "Error: Tournament root not found: $tournament_root"
  exit 1
fi

tournament_root="$(cd "$tournament_root" && pwd)"

if [ -z "$tournament_name" ]; then
  tournament_name="$(basename "$tournament_root")"
fi

teams_dir="$tournament_root/teams"
if [ ! -d "$teams_dir" ]; then
  echo "Error: No teams/ directory under $tournament_root"
  echo "Run: $script_dir/setup_team_folders.sh $tournament_root"
  exit 1
fi

if [ -z "$schedule_dir" ]; then
  if [ -d "$tournament_root/schedule/generated_teams" ]; then
    schedule_dir="$tournament_root/schedule/generated_teams"
  fi
fi

if [ -n "$schedule_dir" ] && [ ! -d "$schedule_dir" ]; then
  echo "Error: Schedule directory not found: $schedule_dir"
  exit 1
fi

team_list=()
if [ -n "$teams" ]; then
  IFS=',' read -ra team_list <<< "$teams"
else
  while IFS= read -r team_slug; do
    [ -n "$team_slug" ] || continue
    team_day_dir="$teams_dir/$team_slug/$day"
    if [ -d "$team_day_dir" ]; then
      team_list+=("$team_slug")
    fi
  done < <(find "$teams_dir" -mindepth 1 -maxdepth 1 -type d -exec basename {} \; | sort)
fi

if [ ${#team_list[@]} -eq 0 ]; then
  echo "Error: No team folders found for $day under $teams_dir"
  exit 1
fi

echo "=== Team Day Processing ==="
echo "Day:           $day"
echo "Tournament:    $tournament_name"
echo "Teams:         ${team_list[*]}"
echo "Schedule dir:  ${schedule_dir:-none}"
echo "Dry run:       $dry_run"
echo ""

for team_slug in "${team_list[@]}"; do
  team_slug="$(echo "$team_slug" | tr -d ' ')"
  team_day_dir="$teams_dir/$team_slug/$day"
  team_label="$team_slug"

  echo "--- Processing team: $team_label ($day) ---"

  if [ ! -d "$team_day_dir" ]; then
    echo "Warning: $team_day_dir not found, skipping."
    continue
  fi

  gx_count=$(find "$team_day_dir" -maxdepth 1 -name 'GX??????.MP4' 2>/dev/null | wc -l | tr -d ' ')
  gp_count=$(find "$team_day_dir" -maxdepth 1 -name 'GP??????.MP4' 2>/dev/null | wc -l | tr -d ' ')
  gopr_count=$(find "$team_day_dir" -maxdepth 1 -name 'GOPR????.MP4' 2>/dev/null | wc -l | tr -d ' ')
  gopro_count=$((gx_count + gp_count + gopr_count))

  if [ "$gopro_count" -eq 0 ] && [ "$dry_run" = false ]; then
    echo "No GoPro files in $team_day_dir, skipping."
    continue
  fi

  echo "Found $gopro_count GoPro files (GX: $gx_count, GP: $gp_count, GOPR: $gopr_count)"

  if [ "$dry_run" = false ]; then
    echo "Merging clips..."
    if ! "$combine_script" "$team_day_dir"; then
      echo "Error: merge failed for $team_label"
      continue
    fi
    echo "Merge complete."
  else
    echo "[DRY RUN] Would run: $combine_script $team_day_dir"
  fi

  merged_count=$(find "$team_day_dir/merged_videos" -name 'PROCESSED*.MP4' 2>/dev/null | wc -l | tr -d ' ')
  if [ "$merged_count" -eq 0 ]; then
    if [ "$dry_run" = true ]; then
      echo "[DRY RUN] No merged videos yet — split will run after SD import and merge."
    else
      echo "No merged videos in $team_day_dir/merged_videos, skipping split."
    fi
    echo ""
    continue
  fi

  games_jsonl=""
  if [ -n "$schedule_dir" ]; then
    games_jsonl="$schedule_dir/${day}_${team_slug}.jsonl"
  fi

  if [ -z "$games_jsonl" ] || [ ! -f "$games_jsonl" ]; then
    echo "Warning: No schedule file for $team_label (expected ${day}_${team_slug}.jsonl)"
    continue
  fi

  split_args=("$team_day_dir" "$games_jsonl" --tournament "$tournament_name")
  if [ "$dry_run" = true ]; then
    split_args+=(--debug)
  fi

  echo "Splitting matchups using $games_jsonl..."
  if ! "$split_script" "${split_args[@]}"; then
    echo "Error: split failed for $team_label"
    continue
  fi

  split_count=$(find "$team_day_dir/split_videos" \( -name '*.mp4' -o -name '*.MP4' \) 2>/dev/null | wc -l | tr -d ' ')
  echo "Done: $team_label ($split_count matchup files in split_videos/)"
  echo ""
done

echo "=== Team Day Processing Complete ==="
