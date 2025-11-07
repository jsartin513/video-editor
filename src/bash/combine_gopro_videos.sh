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

# Find all unique video identifiers for different GoPro patterns
echo "Scanning for GoPro video files..."

# Find GX pattern files (GX??????.MP4)
gx_video_ids=$(find "$input_dir" -type f -name "GX??????.MP4" | sed -E 's/.*GX[0-9]{2}([0-9]{4}).*/\1/' | sort | uniq)

# Find GP pattern files (GP??????.MP4) 
gp_video_ids=$(find "$input_dir" -type f -name "GP??????.MP4" | sed -E 's/.*GP[0-9]{2}([0-9]{4}).*/\1/' | sort | uniq)

# Find GOPR pattern files (GOPR????.MP4)
gopr_video_ids=$(find "$input_dir" -type f -name "GOPR????.MP4" | sed -E 's/.*GOPR([0-9]{4}).*/\1/' | sort | uniq)

# Combine all video IDs
all_video_ids=$(echo -e "$gx_video_ids\n$gp_video_ids\n$gopr_video_ids" | grep -v '^$' | sort | uniq)

echo "Found video sessions: $(echo "$all_video_ids" | wc -w | tr -d ' ')"

# Process each video ID
for video_id in $all_video_ids; do
  # Find all files for the current video ID from all patterns, sorted
  gx_files=$(find "$input_dir" -type f -name "GX??${video_id}.MP4" | sort)
  gp_files=$(find "$input_dir" -type f -name "GP??${video_id}.MP4" | sort)  
  gopr_files=$(find "$input_dir" -type f -name "GOPR${video_id}.MP4" | sort)
  
  # Combine all files for this video ID
  files=$(echo -e "$gx_files\n$gp_files\n$gopr_files" | grep -v '^$' | sort)

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
