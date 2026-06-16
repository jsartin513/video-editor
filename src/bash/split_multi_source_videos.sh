#!/bin/bash

# Multi-source video splitter for GoPro videos
# Usage: split_multi_source_videos.sh <video_directory> <games_jsonl> [--debug] [--tournament "name"] [--court "name"]

if [ $# -lt 2 ]; then
  echo "Usage: $0 <video_directory> <games_jsonl> [--debug] [--tournament \"name\"] [--court \"name\"]"
  exit 1
fi

video_directory="$1"
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

if [ ! -d "$video_directory" ]; then
  echo "Error: Directory '$video_directory' not found."
  exit 1
fi

if [ ! -f "$games_jsonl" ]; then
  echo "Error: File '$games_jsonl' not found."
  exit 1
fi

# Get list of merged videos in order
video_files=($(find "$video_directory/merged_videos" -name "PROCESSED*.MP4" | sort))
if [ ${#video_files[@]} -eq 0 ]; then
  echo "Error: No PROCESSED*.MP4 files found in $video_directory/merged_videos"
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

# Get video durations and create cumulative timeline
video_durations=()
cumulative_times=(0)
total_duration=0

for video_file in "${video_files[@]}"; do
  duration=$(ffprobe -v quiet -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$video_file")
  duration_int=$(printf "%.0f" "$duration")
  video_durations+=($duration_int)
  total_duration=$((total_duration + duration_int))
  cumulative_times+=($total_duration)
done

echo "Found ${#video_files[@]} video files with total duration: $total_duration seconds"

# Function to find which video file contains a given timestamp
find_video_for_timestamp() {
  local timestamp_seconds=$1
  
  for i in "${!cumulative_times[@]}"; do
    if [ $timestamp_seconds -lt ${cumulative_times[$i]} ]; then
      local video_index=$((i - 1))
      if [ $video_index -lt 0 ]; then
        video_index=0
      fi
      local video_file="${video_files[$video_index]}"
      local video_start_time=${cumulative_times[$video_index]}
      local offset_in_video=$((timestamp_seconds - video_start_time))
      
      echo "$video_file|$offset_in_video"
      return 0
    fi
  done
  
  # If not found, use last video
  local last_index=$((${#video_files[@]} - 1))
  local video_file="${video_files[$last_index]}"
  local video_start_time=${cumulative_times[$last_index]}
  local offset_in_video=$((timestamp_seconds - video_start_time))
  
  echo "$video_file|$offset_in_video"
}

# Create output directory
output_dir="$video_directory/split_videos"
mkdir -p "$output_dir"

# Check if we're using timestamp mode
first_start_time=$(head -n 1 "$games_jsonl" | jq -r '.start_time')
use_timestamp_mode=false
if [[ "$first_start_time" =~ ^[0-9]{2}:[0-9]{2}(:[0-9]{2})?$ ]]; then
  use_timestamp_mode=true
  echo "Using timestamp mode - games are timed from video start"
fi

# Process each game
while IFS= read -r line; do
  # Skip empty lines
  [ -z "$line" ] && continue
  
  # Extract game information
  home_team=$(echo "$line" | jq -r '.home_team')
  away_team=$(echo "$line" | jq -r '.away_team')
  start_time=$(echo "$line" | jq -r '.start_time')
  minutes=$(echo "$line" | jq -r '.minutes')
  round=$(echo "$line" | jq -r '.round // ""')
  game_type=$(echo "$line" | jq -r '.type // "round_robin"')
  video_file=$(echo "$line" | jq -r '.video_file // ""')
  
  # Skip if essential fields are missing
  if [ -z "$home_team" ] || [ -z "$away_team" ] || [ -z "$start_time" ] || [ -z "$minutes" ]; then
    continue
  fi
  
  # Convert start time to seconds
  start_seconds=$(time_to_seconds "$start_time")
  if [ $? -ne 0 ]; then
    echo "Error: Could not parse start time: $start_time"
    continue
  fi
  
  # Calculate duration in seconds
  duration_seconds=$((minutes * 60))
  
  # Determine source video
  if [ -n "$video_file" ]; then
    # Use specified video file
    source_video="$video_directory/merged_videos/$video_file"
    if [ ! -f "$source_video" ]; then
      echo "Error: Specified video file not found: $source_video"
      continue
    fi
    offset_in_video=$start_seconds
  else
    # Fall back to old multi-video timeline logic
    video_info=$(find_video_for_timestamp $start_seconds)
    source_video=$(echo "$video_info" | cut -d'|' -f1)
    offset_in_video=$(echo "$video_info" | cut -d'|' -f2)
  fi
  
  # Check if the game spans multiple videos (only relevant for old timeline logic)
  if [ -z "$video_file" ]; then
    end_seconds=$((start_seconds + duration_seconds))
    end_video_info=$(find_video_for_timestamp $end_seconds)
    end_source_video=$(echo "$end_video_info" | cut -d'|' -f1)
  else
    # With explicit video files, assume it fits within the specified video
    end_source_video="$source_video"
  fi
  
  # Format team names for filename (replace spaces with underscores)
  home_team_formatted=$(echo "$home_team" | sed 's/ /_/g')
  away_team_formatted=$(echo "$away_team" | sed 's/ /_/g')
  
  # Create output filename (match split_game_videos.sh naming)
  output_filename=""
  filename_parts=""
  if [ -n "$game_type" ] && [ -n "$round" ]; then
    formatted_type=$(echo "$game_type" | sed 's/_/ /g' | awk '{for(i=1;i<=NF;i++) $i=toupper(substr($i,1,1)) tolower(substr($i,2))}1')
    filename_parts="${formatted_type} ${round}"
  elif [ -n "$round" ]; then
    filename_parts="Round ${round}"
  fi

  if [ -n "$court_name" ]; then
    formatted_court=$(echo "$court_name" | sed 's/_/ /g')
    if [ -n "$filename_parts" ]; then
      filename_parts="${filename_parts}: ${formatted_court}"
    else
      filename_parts="${formatted_court}"
    fi
  fi

  team_names="${home_team} vs ${away_team}"
  if [ -n "$filename_parts" ]; then
    filename_parts="${filename_parts}: ${team_names}"
  else
    filename_parts="${team_names}"
  fi

  if [ -n "$tournament_name" ] && [ -n "$filename_parts" ]; then
    output_filename="${filename_parts}.mp4"
  elif [ -n "$court_name" ] && [ -n "$filename_parts" ]; then
    output_filename="${filename_parts}.mp4"
  else
    output_filename="${home_team_formatted}_vs_${away_team_formatted}.mp4"
  fi
  
  output_path="$output_dir/$output_filename"
  
  # Format time for display
  start_time_formatted=$(printf "%02d:%02d:%02d" $((start_seconds / 3600)) $(((start_seconds % 3600) / 60)) $((start_seconds % 60)))
  end_time_formatted=$(printf "%02d:%02d:%02d" $((end_seconds / 3600)) $(((end_seconds % 3600) / 60)) $((end_seconds % 60)))
  duration_formatted=$(printf "%02d:%02d" $((minutes)) $((duration_seconds % 60)))
  
  echo "Creating $output_filename from $start_time_formatted to $end_time_formatted (duration $duration_formatted)"
  
  if [ "$debug" -eq 1 ]; then
    echo "  [DEBUG] Would extract from: $(basename "$source_video")"
    echo "  [DEBUG] Start offset in video: $offset_in_video seconds"
    echo "  [DEBUG] Duration: $duration_seconds seconds"
    if [ -n "$video_file" ]; then
      echo "  [DEBUG] Using explicit video file: $video_file"
    fi
    if [ "$source_video" != "$end_source_video" ]; then
      echo "  [DEBUG] WARNING: Game spans multiple videos!"
    fi
    continue
  fi
  
  # Extract the video segment
  if [ "$source_video" = "$end_source_video" ]; then
    # Game is contained within a single video
    offset_formatted=$(printf "%02d:%02d:%02d" $((offset_in_video / 3600)) $(((offset_in_video % 3600) / 60)) $((offset_in_video % 60)))
    duration_formatted=$(printf "%02d:%02d:%02d" $((duration_seconds / 3600)) $(((duration_seconds % 3600) / 60)) $((duration_seconds % 60)))
    
    ffmpeg -hide_banner -loglevel error -i "$source_video" -ss "$offset_formatted" -t "$duration_formatted" -c copy "$output_path"
  else
    # Game spans multiple videos - need to concatenate
    echo "  [WARNING] Game spans multiple videos - this requires more complex handling"
    echo "  [INFO] Skipping for now - please adjust timing or implement multi-video extraction"
    continue
  fi
  
  if [ $? -eq 0 ]; then
    echo "Created!"
  else
    echo "Error creating video segment"
  fi
  
done < <(cat "$games_jsonl")

echo "Video splitting complete!"
