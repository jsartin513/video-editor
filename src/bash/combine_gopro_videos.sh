#!/bin/bash

# Check if a directory is provided
if [ -z "$1" ]; then
  echo "Usage: $0 <directory>"
  exit 1
fi

input_dir="$1"
output_dir="$input_dir/merged videos"

# Create the output directory if it doesn't exist
mkdir -p "$output_dir"

# Find all unique video identifiers (last 4 digits of filenames)
video_ids=$(find "$input_dir" -type f -name "GX??????.MP4" | sed -E 's/.*GX[0-9]{2}([0-9]{4}).*/\1/' | sort | uniq)

# Process each video ID
for video_id in $video_ids; do
  # Find all files for the current video ID, sorted by the first two digits
  files=$(find "$input_dir" -type f -name "GX??${video_id}.MP4" | sort)

  # Concatenate files into a single processed video
  output_file="$output_dir/PROCESSED${video_id}.MP4"
  echo "Processing video ID $video_id into $output_file"
  ffmpeg -f concat -safe 0 -i <(for f in $files; do echo "file '$f'"; done) -c copy "$output_file"
done

echo "All videos have been processed and saved in '$output_dir'."
