#!/bin/bash

# League Night Video Processing Script
# Processes multiple courts for a league night event
# Usage: ./process_league_night.sh <base_directory> <date> [court_count]
#
# Example: ./process_league_night.sh "/Users/MrsHazmat/Movies/bdl_league_aug_13" "Aug_13_2025" 2

if [ -z "$1" ] || [ -z "$2" ]; then
  echo "Usage: $0 <base_directory> <date> [court_count]"
  echo ""
  echo "  <base_directory>: Directory containing court_X subdirectories"
  echo "  <date>: Date identifier for the league night (e.g., Aug_13_2025)"
  echo "  [court_count]: Number of courts to process (default: auto-detect)"
  echo ""
  echo "Expected directory structure:"
  echo "  base_directory/"
  echo "    court_1/"
  echo "      GX??????.MP4 files"
  echo "    court_2/"
  echo "      GX??????.MP4 files"
  echo "    ..."
  echo ""
  echo "Example:"
  echo "  $0 '/Users/MrsHazmat/Movies/bdl_league_aug_13' 'Aug_13_2025' 2"
  exit 1
fi

base_dir="$1"
date_identifier="$2"
court_count="$3"

# Get the directory of this script to find combine_gopro_videos.sh
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
combine_script="$script_dir/combine_gopro_videos.sh"

# Check if combine_gopro_videos.sh exists
if [ ! -f "$combine_script" ]; then
  echo "Error: combine_gopro_videos.sh not found at $combine_script"
  exit 1
fi

# Check if base directory exists
if [ ! -d "$base_dir" ]; then
  echo "Error: Base directory '$base_dir' does not exist."
  exit 1
fi

echo "=== BDL League Night Video Processing ==="
echo "Base directory: $base_dir"
echo "Date: $date_identifier"
echo ""

# Auto-detect courts if not specified
if [ -z "$court_count" ]; then
  courts=$(find "$base_dir" -maxdepth 1 -type d -name "court_*" | sort)
  court_count=$(echo "$courts" | wc -l | tr -d ' ')
  echo "Auto-detected $court_count courts"
else
  echo "Processing $court_count courts"
fi

# Process each court
for i in $(seq 1 $court_count); do
  court_dir="$base_dir/court_$i"
  
  if [ ! -d "$court_dir" ]; then
    echo "Warning: Court $i directory '$court_dir' not found, skipping..."
    continue
  fi
  
  echo ""
  echo "--- Processing Court $i ---"
  
  # Check if there are any GoPro files (multiple patterns)
  gx_files=$(find "$court_dir" -name "GX??????.MP4" 2>/dev/null | wc -l | tr -d ' ')
  gp_files=$(find "$court_dir" -name "GP??????.MP4" 2>/dev/null | wc -l | tr -d ' ')
  gopr_files=$(find "$court_dir" -name "GOPR????.MP4" 2>/dev/null | wc -l | tr -d ' ')
  gopro_files=$((gx_files + gp_files + gopr_files))
  
  if [ "$gopro_files" -eq 0 ]; then
    echo "No GoPro files found in $court_dir, skipping..."
    continue
  fi
  
  echo "Found $gopro_files GoPro video files (GX: $gx_files, GP: $gp_files, GOPR: $gopr_files)"
  
  # Run the combine script
  echo "Running: $combine_script '$court_dir'"
  if "$combine_script" "$court_dir"; then
    echo "✓ Successfully merged videos for Court $i"
    
    # Find the processed video and rename it
    merged_dir="$court_dir/merged_videos"
    if [ -d "$merged_dir" ]; then
      processed_video=$(find "$merged_dir" -name "PROCESSED*.MP4" | head -1)
      if [ -n "$processed_video" ]; then
        new_name="$merged_dir/BDL_League_Night_${date_identifier}_Court_${i}.MP4"
        echo "Renaming to: BDL_League_Night_${date_identifier}_Court_${i}.MP4"
        mv "$processed_video" "$new_name"
        
        # Show file size and duration info
        if command -v ffprobe >/dev/null 2>&1; then
          duration=$(ffprobe -v quiet -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$new_name" | awk '{printf "%02d:%02d:%02d", $1/3600, ($1%3600)/60, $1%60}')
          size=$(ls -lh "$new_name" | awk '{print $5}')
          echo "✓ Final video: $size, Duration: $duration"
        else
          size=$(ls -lh "$new_name" | awk '{print $5}')
          echo "✓ Final video: $size"
        fi
      else
        echo "Warning: No processed video found in $merged_dir"
      fi
    else
      echo "Warning: Merged videos directory not created"
    fi
  else
    echo "✗ Failed to merge videos for Court $i"
  fi
done

echo ""
echo "=== League Night Processing Complete ==="
echo "All processed videos are located in their respective court directories under merged_videos/"
echo ""

# Summary of all created videos
echo "--- Final Video Summary ---"
for i in $(seq 1 $court_count); do
  court_dir="$base_dir/court_$i"
  merged_dir="$court_dir/merged_videos"
  final_video="$merged_dir/BDL_League_Night_${date_identifier}_Court_${i}.MP4"
  
  if [ -f "$final_video" ]; then
    size=$(ls -lh "$final_video" | awk '{print $5}')
    echo "Court $i: BDL_League_Night_${date_identifier}_Court_${i}.MP4 ($size)"
  fi
done
