#!/bin/bash

# Usage: split_game_videos.sh <video_file> <games_jsonl> [--debug] [--tournament "name"] [--court "name"]
if [ $# -lt 2 ]; then
  echo "Usage: $0 <video_file> <games_jsonl> [--debug] [--tournament \"name\"] [--court \"name\"]"
  exit 1
fi

video_file="$1"
games_jsonl="$2"
debug=0
tournament_name=""
court_name=""

# Parse additional arguments
shift 2
while [[ $# -gt 0 ]]; do
  case $1 in
    --debug)
      debug=1
      shift
      ;;
    --tournament)
      tournament_name="$2"
      shift 2
      ;;
    --court)
      court_name="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

if [ ! -f "$video_file" ]; then
  echo "Error: File '$video_file' not found."
  exit 1
fi

if [ ! -f "$games_jsonl" ]; then
  echo "Error: File '$games_jsonl' not found."
  exit 1
fi

# Try to extract video start time from stream timecode first
video_start_time=$(ffprobe -v error -select_streams v:0 -show_entries stream_tags=timecode -of default=noprint_wrappers=1:nokey=1 "$video_file" | head -n 1)

if [ -n "$video_start_time" ]; then
  # If timecode is in HH:MM:SS format, prepend a dummy date for parsing
  if [[ "$video_start_time" =~ ^[0-9]{2}:[0-9]{2}:[0-9]{2} ]]; then
    video_start_time="2000-01-01 $video_start_time"
  fi
else
  # Fallback to creation_time in format tags
  video_start_time=$(ffprobe -v error -show_entries format_tags=creation_time -of default=noprint_wrappers=1:nokey=1 "$video_file" | head -n 1 | sed 's/T/ /;s/\..*//')
fi

if [ -z "$video_start_time" ]; then
  echo "Error: Could not extract video start time from metadata."
  exit 1
fi

video_start_epoch=$(date -j -f "%Y-%m-%d %H:%M:%S" "$video_start_time" "+%s" 2>/dev/null)
if [ -z "$video_start_epoch" ]; then
  # Try GNU date fallback
  video_start_epoch=$(date -d "$video_start_time" "+%s" 2>/dev/null)
fi
if [ -z "$video_start_epoch" ]; then
  echo "Error: Could not parse video start time: $video_start_time"
  exit 1
fi

# Helper to convert HH:MM or HH:MM:SS to seconds
time_to_seconds() {
  local time_str="$1"
  local h=0 m=0 s=0
  
  # Handle HH:MM:SS format
  if [[ "$time_str" =~ ^([0-9]{1,2}):([0-9]{2}):([0-9]{2})$ ]]; then
    h=${BASH_REMATCH[1]}
    m=${BASH_REMATCH[2]}
    s=${BASH_REMATCH[3]}
  # Handle HH:MM format
  elif [[ "$time_str" =~ ^([0-9]{1,2}):([0-9]{2})$ ]]; then
    h=${BASH_REMATCH[1]}
    m=${BASH_REMATCH[2]}
    s=0
  else
    echo "Error: Invalid time format: $time_str" >&2
    return 1
  fi
  
  echo $((10#$h * 3600 + 10#$m * 60 + 10#$s))
}

# Check if we're using timestamp mode (start_time is in HH:MM:SS format)
use_timestamp_mode() {
  local first_game_start=$(head -n1 "$games_jsonl" | jq -r '.start_time' 2>/dev/null || echo "")
  # Check if format is HH:MM:SS (with optional leading zero)
  [[ "$first_game_start" =~ ^[0-9]{1,2}:[0-9]{2}:[0-9]{2}$ ]]
}

# For timestamp mode, we don't need video start time - just use video start as 0
if use_timestamp_mode; then
  video_start_seconds=0
  echo "Using timestamp mode - games are timed from video start"
else
  # Original clock-based timing
  video_start_hms=$(echo "$video_start_time" | awk '{print $2}' | cut -c1-5)
  video_start_seconds=$(time_to_seconds "$video_start_hms")
  echo "Using clock-based timing - video starts at $video_start_hms"
fi

# Helper to format seconds as HH:MM:SS
format_seconds() {
  local total_seconds=$1
  local h=$((total_seconds / 3600))
  local m=$(( (total_seconds % 3600) / 60 ))
  local s=$((total_seconds % 60))
  if [ $h -gt 0 ]; then
    printf "%02d:%02d:%02d" $h $m $s
  else
    printf "%02d:%02d" $m $s
  fi
}

# Determine output directory for split videos
# Use the parent directory of the merged_videos directory
video_parent_dir="$(dirname "$(dirname "$video_file")")"
split_dir="$video_parent_dir/split_videos"
mkdir -p "$split_dir"

# --- First, read all games into an array ---
games=()
while IFS= read -r line || [ -n "$line" ]; do
  # Remove carriage returns
  line=$(echo "$line" | tr -d '\r')
  [[ "$line" =~ ^\{ ]] || continue
  # Validate JSON
  if ! echo "$line" | jq empty >/dev/null 2>&1; then
    echo "Skipping invalid JSON line: $line"
    continue
  fi
  games+=("$line")
done < "$games_jsonl"

# --- Now, process each game from the array ---
for line in "${games[@]}"; do
  home_team=$(echo "$line" | jq -r '.home_team')
  away_team=$(echo "$line" | jq -r '.away_team')
  minutes=$(echo "$line" | jq -r '.minutes')
  start_time=$(echo "$line" | jq -r '.start_time')

  # Calculate offset based on timing mode
  if use_timestamp_mode; then
    # In timestamp mode, start_time is the offset from video start
    offset_seconds=$(time_to_seconds "$start_time")
  else
    # In clock mode, calculate offset from video start time
    game_start_seconds=$(time_to_seconds "$start_time")
    offset_seconds=$((game_start_seconds - video_start_seconds))
    
    if [ $offset_seconds -lt 0 ]; then
      echo "Skipping ${home_team} vs ${away_team}: game start time ($start_time) is before video start."
      continue
    fi
  fi

  duration_seconds=$((minutes * 60))
  
  # Generate proper filename based on tournament/round/court info
  round_num=$(echo "$line" | jq -r '.round // empty')
  game_type=$(echo "$line" | jq -r '.type // empty')
  
  # Build filename components
  filename_parts=""
  
  # Add formatted type and round
  if [ -n "$game_type" ] && [ -n "$round_num" ]; then
    formatted_type=$(echo "$game_type" | sed 's/_/ /g' | awk '{for(i=1;i<=NF;i++) $i=toupper(substr($i,1,1)) tolower(substr($i,2))}1')
    filename_parts="${formatted_type} ${round_num}"
  elif [ -n "$round_num" ]; then
    filename_parts="Round ${round_num}"
  fi
  
  # Add court name
  if [ -n "$court_name" ]; then
    formatted_court=$(echo "$court_name" | sed 's/_/ /g')
    if [ -n "$filename_parts" ]; then
      filename_parts="${filename_parts}: ${formatted_court}"
    else
      filename_parts="${formatted_court}"
    fi
  fi
  
  # Add team names
  team_names="${home_team} vs ${away_team}"
  if [[ "$home_team" =~ ^[Tt][Bb][Dd]$ ]] || [[ "$away_team" =~ ^[Tt][Bb][Dd]$ ]]; then
    if [ -n "$filename_parts" ]; then
      filename_parts="${filename_parts}: ${start_time}"
    fi
  fi
  if [ -n "$filename_parts" ]; then
    filename_parts="${filename_parts}: ${team_names}"
  else
    filename_parts="${team_names}"
  fi
  
  # Create final filename
  if [ -n "$tournament_name" ] && [ -n "$filename_parts" ]; then
    out_file="$split_dir/${filename_parts}.mp4"
  else
    # Fallback to original format if no tournament/court info provided
    out_file="$split_dir/${home_team// /_}_vs_${away_team// /_}.mp4"
  fi

  offset_fmt=$(format_seconds $offset_seconds)
  duration_fmt=$(format_seconds $duration_seconds)
  end_fmt=$(format_seconds $((offset_seconds + duration_seconds)))

  if [ $debug -eq 1 ]; then
    echo "Would create $out_file from $offset_fmt to $end_fmt (duration $duration_fmt)"
  else
    echo "Creating $out_file from $offset_fmt to $end_fmt (duration $duration_fmt)"
    ffmpeg -hide_banner -loglevel error -ss $offset_seconds -i "$video_file" -t $duration_seconds -c copy "$out_file"
    echo "Created!"
  fi
done