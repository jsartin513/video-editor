#!/bin/bash

# Usage: split_game_videos.sh <video_file> <games_jsonl> [--debug]
if [ $# -lt 2 ] || [ $# -gt 3 ]; then
  echo "Usage: $0 <video_file> <games_jsonl> [--debug]"
  exit 1
fi

video_file="$1"
games_jsonl="$2"
debug=0
if [ "$3" == "--debug" ]; then
  debug=1
fi

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

# Helper to convert HH:MM to seconds since midnight
hm_to_seconds() {
  IFS=: read h m <<< "$1"
  echo $((10#$h * 3600 + 10#$m * 60))
}

# Helper to get seconds since midnight for video start
video_start_hms=$(echo "$video_start_time" | awk '{print $2}' | cut -c1-5)
video_start_seconds=$(hm_to_seconds "$video_start_hms")

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
split_dir="$(dirname "$video_file")/split_videos"
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

  game_start_seconds=$(hm_to_seconds "$start_time")
  offset_seconds=$((game_start_seconds - video_start_seconds))

  if [ $offset_seconds -lt 0 ]; then
    echo "Skipping ${home_team} vs ${away_team}: game start time ($start_time) is before video start."
    continue
  fi

  duration_seconds=$((minutes * 60))
  out_file="$split_dir/${home_team// /_}_vs_${away_team// /_}.mp4"

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