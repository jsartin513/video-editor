#!/bin/bash

# Check if a directory is provided
if [ -z "$1" ]; then
  echo "Usage: $0 <input_directory> [output_directory]"
  echo "  <input_directory>: Directory containing GoPro video files."
  echo "  [output_directory]: (Optional) Directory to save merged videos. Defaults to '<input_directory>/merged_videos'."
  exit 1
fi

input_dir="$1"
output_dir="${2:-$input_dir/merged_videos}"

# Check if output_dir contains spaces
if [[ "$input_dir" =~ \  ]]; then
  echo "Error: Input directory '$input_dir' contains spaces. Please use underscores instead."
  exit 1
fi

# Check if output_dir contains spaces
if [[ "$output_dir" =~ \  ]]; then
  echo "Error: Output directory '$output_dir' contains spaces. Please use underscores instead."
  exit 1
fi

# Create the output directory if it doesn't exist
mkdir -p "$output_dir"

# Find all unique video identifiers (last 4 digits of filenames)
video_ids=$(find "$input_dir" -type f -name "GX??????.MP4" | sed -E 's/.*GX[0-9]{2}([0-9]{4}).*/\1/' | sort | uniq)

# Process each video ID
for video_id in $video_ids; do
  # Find all files for the current video ID, sorted by the first two digits
  files=$(find "$input_dir" -type f -name "GX??${video_id}.MP4" | sort)

  # Create a temporary file for the list of input files
  temp_file=$(mktemp)
  for f in $files; do
    echo "file '$f'" >> "$temp_file"
  done

  # Concatenate files into a single processed video
  output_file="$output_dir/PROCESSED${video_id}.MP4"
  echo "Processing video ID $video_id into $output_file"
  ffmpeg -f concat -safe 0 -i "$temp_file" -c copy "$output_file"

  # Remove the temporary file
  rm "$temp_file"
done

echo "All videos have been processed and saved in '$output_dir'."
