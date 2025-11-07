#!/bin/bash

# Test script for renaming only
video_dir="$1"
split_dir="$video_dir/split_videos"
jsonl_file="$video_dir/games.jsonl"

echo "Testing rename function..."
echo "Video dir: $video_dir"
echo "Split dir: $split_dir"
echo "JSONL file: $jsonl_file"

# Source the functions from the main script
source /Users/MrsHazmat/github/video-editor/src/bash/gopro_workflow.sh

# Call rename function
rename_video_files "$split_dir" "BDL Throwdown 4" "Court 1" "$jsonl_file" "1"
