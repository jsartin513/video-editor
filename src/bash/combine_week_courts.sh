#!/bin/bash

# Combine GoPro clips in each court folder under a week/event directory.
# Usage: ./combine_week_courts.sh <week_directory> [output_directory] [title_prefix]
#
# Examples:
#   ./combine_week_courts.sh src/output/Spring2026Remix/Week2
#   ./combine_week_courts.sh src/output/Spring2026Remix/Week3 --title-prefix "BDL Season 7: Summer Remix"
#   ./combine_week_courts.sh src/output/Spring2026Remix/Week3 --dry-run
#
# Court folders may be named court1, Court1, etc. Clips are sorted GOPR -> GP -> GX
# (GoPro chapter order). Incomplete transfers (0-byte or missing moov atom) are skipped.

set -e

DRY_RUN=false
ALLOW_PARTIAL=false
TITLE_PREFIX=""
COURT_FILTER=""
week_dir=""
output_dir=""

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --allow-partial)
      ALLOW_PARTIAL=true
      shift
      ;;
    --court)
      COURT_FILTER="$2"
      shift 2
      ;;
    --title-prefix)
      TITLE_PREFIX="$2"
      shift 2
      ;;
    *)
      if [ -z "$week_dir" ]; then
        week_dir="$1"
      elif [ -z "$output_dir" ]; then
        output_dir="$1"
      else
        echo "Unexpected argument: $1"
        exit 1
      fi
      shift
      ;;
  esac
done

if [ -z "$week_dir" ]; then
  echo "Usage: $0 <week_directory> [output_directory] [--title-prefix \"...\"] [--dry-run]"
  echo ""
  echo "  <week_directory>: Directory containing court1/Court1, court2/Court2, ... subfolders"
  echo "  [output_directory]: Where merged videos are written (default: <week_directory>/merged_videos)"
  echo "  --title-prefix: Upload title prefix, e.g. \"BDL Season 7: Summer Remix\""
  echo "                  Output: \"<title_prefix>: Week 3 Court 1.MP4\""
  echo "  --dry-run: List clips and planned outputs without merging"
  echo ""
  echo "Expected structure:"
  echo "  week_directory/"
  echo "    Court1/"
  echo "      GX010554.MP4, GX020554.MP4, ..."
  echo "    Court2/"
  echo "      GX015323.MP4"
  exit 1
fi

week_dir="$(cd "$week_dir" && pwd)"

infer_title_prefix() {
  local parent
  parent="$(basename "$(dirname "$1")")"
  case "$parent" in
    Spring2026Remix) echo "BDL Season 7: Summer Remix" ;;
    *) echo "" ;;
  esac
}

if [ -z "$TITLE_PREFIX" ]; then
  TITLE_PREFIX="$(infer_title_prefix "$week_dir")"
fi

if [ -n "$output_dir" ]; then
  output_dir="$(mkdir -p "$output_dir" && cd "$output_dir" && pwd)"
else
  output_dir="$week_dir/merged_videos"
  mkdir -p "$output_dir"
fi

if echo "$week_dir" | grep -q ' '; then
  echo "Error: Week directory must not contain spaces: $week_dir"
  exit 1
fi

if echo "$output_dir" | grep -q ' '; then
  echo "Error: Output directory must not contain spaces: $output_dir"
  exit 1
fi

if [ ! -d "$week_dir" ]; then
  echo "Error: Week directory does not exist: $week_dir"
  exit 1
fi

if [ "$DRY_RUN" = false ] && ! command -v ffmpeg >/dev/null 2>&1; then
  echo "Error: ffmpeg is required but not found in PATH"
  exit 1
fi

week_label="$(basename "$week_dir")"

abs_path() {
  local dir base
  dir="$(dirname "$1")"
  base="$(basename "$1")"
  echo "$(cd "$dir" && pwd)/$base"
}

# GOPR, then GP segments, then GX segments (GoPro chapter order)
list_gopro_files() {
  local court_dir="$1"
  find "$court_dir" -maxdepth 1 -type f \( -iname 'GOPR*.MP4' -o -iname 'GOPR*.mp4' \) 2>/dev/null | sort
  find "$court_dir" -maxdepth 1 -type f \( -iname 'GP[0-9]*.MP4' -o -iname 'GP[0-9]*.mp4' \) ! -iname 'GOPR*' 2>/dev/null | sort
  find "$court_dir" -maxdepth 1 -type f \( -iname 'GX*.MP4' -o -iname 'GX*.mp4' \) 2>/dev/null | sort
}

is_valid_video() {
  local file="$1"
  local size

  size="$(stat -f%z "$file" 2>/dev/null || echo 0)"
  if [ "$size" -lt 1048576 ]; then
    return 1
  fi

  if ! command -v ffprobe >/dev/null 2>&1; then
    return 0
  fi

  ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$file" >/dev/null 2>&1
}

format_week_label() {
  local label="$1"
  local num

  if echo "$label" | grep -qiE '^week[_ ]*[0-9]+$'; then
    num="$(echo "$label" | sed -E 's/^[Ww]eek[_ ]*//')"
    echo "Week $num"
    return
  fi

  echo "$label"
}

format_court_label() {
  local court_name="$1"
  local num

  num="$(echo "$court_name" | sed -E 's/^[Cc]ourt[_ ]*//')"
  echo "Court $num"
}

output_filename() {
  local court_name="$1"
  local court_label
  local formatted_week

  court_label="$(format_court_label "$court_name")"
  if [ -n "$TITLE_PREFIX" ]; then
    formatted_week="$(format_week_label "$week_label")"
    echo "${TITLE_PREFIX}: ${formatted_week} ${court_label}.MP4"
  else
    echo "${week_label}_${court_name}.MP4"
  fi
}

court_matches_filter() {
  local court_name="$1"
  local court_num filter_num

  [ -z "$COURT_FILTER" ] && return 0

  court_num="$(echo "$court_name" | sed -E 's/^[Cc]ourt[_ ]*//')"
  filter_num="$(echo "$COURT_FILTER" | sed -E 's/^[Cc]ourt[_ ]*//')"

  [ "$court_num" = "$filter_num" ] && return 0
  [ "$COURT_FILTER" = "$court_name" ] && return 0
  return 1
}

find_court_dirs() {
  local dir name
  for dir in "$week_dir"/*; do
    [ -d "$dir" ] || continue
    name="$(basename "$dir")"
    case "$name" in
      [Cc]ourt*)
        if court_matches_filter "$name"; then
          echo "$dir"
        fi
        ;;
    esac
  done | sort -f
}

echo "=== Combine week courts ==="
echo "Week directory: $week_dir"
echo "Output directory: $output_dir"
if [ -n "$TITLE_PREFIX" ]; then
  echo "Title prefix: $TITLE_PREFIX"
fi
if [ "$DRY_RUN" = true ]; then
  echo "Mode: dry-run (no files will be written)"
fi
echo ""

court_count=0
for court_dir in $(find_court_dirs); do
  [ -d "$court_dir" ] || continue
  court_count=$((court_count + 1))

  court_name="$(basename "$court_dir")"
  temp_file="$(mktemp)"
  file_count=0
  skipped_count=0

  echo "--- $court_name ---"
  : > "$temp_file"
  while IFS= read -r f; do
    [ -z "$f" ] && continue
    if ! is_valid_video "$f"; then
      echo "  SKIP (incomplete): $(basename "$f")"
      skipped_count=$((skipped_count + 1))
      continue
    fi
    echo "  $(basename "$f")"
    printf "file '%s'\n" "$(abs_path "$f")" >> "$temp_file"
    file_count=$((file_count + 1))
  done < <(list_gopro_files "$court_dir" | awk '!seen[$0]++')

  output_file="$output_dir/$(output_filename "$court_name")"

  if [ "$file_count" -eq 0 ]; then
    echo "Warning: No complete GoPro clips in $court_dir"
    if [ "$skipped_count" -gt 0 ]; then
      echo "  ($skipped_count file(s) still transferring or invalid)"
    fi
    rm -f "$temp_file"
    echo ""
    continue
  fi

  if [ "$skipped_count" -gt 0 ] && [ "$ALLOW_PARTIAL" = false ]; then
    echo "Skipping merge — $skipped_count file(s) still transferring"
    echo "  Re-run after copy completes, or pass --allow-partial"
    rm -f "$temp_file"
    echo ""
    continue
  fi

  if [ "$DRY_RUN" = true ]; then
    echo "Would write: $output_file ($file_count clip(s))"
    if [ "$skipped_count" -gt 0 ]; then
      echo "  Waiting on $skipped_count more file(s) (use --allow-partial to merge anyway)"
    fi
    rm -f "$temp_file"
    echo ""
    continue
  fi

  if [ "$file_count" -eq 1 ]; then
    single_file="$(head -1 "$temp_file" | sed "s/^file '//; s/'$//")"
    echo "Copying 1 clip -> $output_file"
    cp "$single_file" "$output_file"
  else
    echo "Combining $file_count clips -> $output_file"
    ffmpeg -y -f concat -safe 0 -i "$temp_file" -c copy "$output_file"
  fi
  rm -f "$temp_file"

  if command -v ffprobe >/dev/null 2>&1; then
    duration="$(ffprobe -v quiet -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$output_file" | awk '{printf "%02d:%02d:%02d", $1/3600, ($1%3600)/60, $1%60}')"
    size="$(ls -lh "$output_file" | awk '{print $5}')"
    echo "Done: $size, duration $duration"
  else
    size="$(ls -lh "$output_file" | awk '{print $5}')"
    echo "Done: $size"
  fi
  if [ "$skipped_count" -gt 0 ]; then
    echo "Note: $skipped_count file(s) skipped — re-run after transfer completes"
  fi
  echo ""
done

if [ "$court_count" -eq 0 ]; then
  echo "Error: No court folders found in $week_dir (expected court1, Court1, etc.)"
  exit 1
fi

if [ "$DRY_RUN" = true ]; then
  echo "=== Dry-run complete ==="
  exit 0
fi

echo "=== Complete ==="
echo "Merged videos:"
for court_dir in $(find_court_dirs); do
  court_name="$(basename "$court_dir")"
  output_file="$output_dir/$(output_filename "$court_name")"
  if [ -f "$output_file" ]; then
    size="$(ls -lh "$output_file" | awk '{print $5}')"
    echo "  $output_file ($size)"
  fi
done
