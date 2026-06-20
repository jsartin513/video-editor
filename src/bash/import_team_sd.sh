#!/bin/bash

# Import a team GoPro SD card into a tournament team/day folder.
# Usage: import_team_sd.sh --dest <team_day_directory> [--source <volume_path>] [--dry-run]
#
# Example:
#   ./import_team_sd.sh \
#     --dest src/output/June2026Tournament/teams/sister_sister/2026-06-20 \
#     --card Team-Sister-Sister-Sat

set -e

GOPRO_DCIM="DCIM/100GOPRO"
GOPRO_PATTERNS=("GX??????.MP4" "GP??????.MP4" "GOPR????.MP4")

dest_dir=""
source_volume=""
dry_run=false
card_label=""

show_usage() {
  cat << EOF
Usage: $0 --dest <team_day_directory> [options]

Required:
  --dest DIR       Team day folder (e.g. .../teams/sister_sister/2026-06-20)

Options:
  --source PATH    SD card mount path (default: auto-detect GoPro volume)
  --card LABEL     Card label for logging (e.g. Team-Sister-Sister-Sat)
  --dry-run        Show what would be copied without copying
  -h, --help       Show this help

Examples:
  $0 --dest src/output/June2026Tournament/teams/sister_sister/2026-06-20 --card Team-Sister-Sister-Sat
  $0 --dest src/output/June2026Tournament/teams/fresh_prince/2026-06-21 --source /Volumes/Untitled --dry-run
EOF
}

detect_gopro_volumes() {
  local volumes=()
  for volume in /Volumes/*; do
    [ -d "$volume" ] || continue
    volume_name="$(basename "$volume")"
    if [[ "$volume_name" == "Macintosh HD"* ]] || [[ "$volume_name" == "System"* ]]; then
      continue
    fi
    if [ -d "$volume/$GOPRO_DCIM" ]; then
      local count=0
      for pattern in "${GOPRO_PATTERNS[@]}"; do
        count=$((count + $(find "$volume/$GOPRO_DCIM" -maxdepth 1 -name "$pattern" 2>/dev/null | wc -l | tr -d ' ')))
      done
      if [ "$count" -gt 0 ]; then
        volumes+=("$volume")
        echo "Found GoPro card: $volume_name ($count files)" >&2
      fi
    fi
  done
  printf '%s\n' "${volumes[@]}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dest)
      dest_dir="$2"
      shift 2
      ;;
    --source)
      source_volume="$2"
      shift 2
      ;;
    --card)
      card_label="$2"
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
    *)
      echo "Unknown option: $1"
      show_usage
      exit 1
      ;;
  esac
done

if [ -z "$dest_dir" ]; then
  show_usage
  exit 1
fi

if [[ "$dest_dir" =~ \  ]]; then
  echo "Error: Destination path contains spaces."
  exit 1
fi

mkdir -p "$dest_dir/merged_videos" "$dest_dir/split_videos"

if [ -z "$source_volume" ]; then
  volumes=()
  while IFS= read -r vol; do
    [ -n "$vol" ] && volumes+=("$vol")
  done < <(detect_gopro_volumes)
  if [ ${#volumes[@]} -eq 0 ]; then
    echo "Error: No GoPro SD cards detected. Insert card or pass --source."
    exit 1
  elif [ ${#volumes[@]} -eq 1 ]; then
    source_volume="${volumes[0]}"
  else
    echo "Multiple GoPro SD cards detected:"
    for i in "${!volumes[@]}"; do
      echo "  $((i + 1))) ${volumes[$i]}"
    done
    while true; do
      echo -n "Select card number (1-${#volumes[@]}): "
      read -r selection
      if [[ "$selection" =~ ^[0-9]+$ ]] && [ "$selection" -ge 1 ] && [ "$selection" -le ${#volumes[@]} ]; then
        source_volume="${volumes[$((selection - 1))]}"
        break
      fi
      echo "Invalid selection. Enter a number between 1 and ${#volumes[@]}."
    done
  fi
fi

gopro_dir="$source_volume/$GOPRO_DCIM"
if [ ! -d "$gopro_dir" ]; then
  echo "Error: GoPro directory not found: $gopro_dir"
  exit 1
fi

label="${card_label:-$(basename "$source_volume")}"
echo "=== Team SD Import ==="
echo "Card:        $label"
echo "Source:      $gopro_dir"
echo "Destination: $dest_dir"
echo "Dry run:     $dry_run"
echo ""

copied=0
skipped=0
would_copy=0

for pattern in "${GOPRO_PATTERNS[@]}"; do
  while IFS= read -r -d '' file; do
    filename="$(basename "$file")"
    dest_file="$dest_dir/$filename"
    if [ -f "$dest_file" ]; then
      echo "Skip (exists): $filename"
      skipped=$((skipped + 1))
      continue
    fi
    if [ "$dry_run" = true ]; then
      echo "Would copy: $filename"
      would_copy=$((would_copy + 1))
    else
      cp -p "$file" "$dest_file"
      echo "Copied: $filename"
      copied=$((copied + 1))
    fi
  done < <(find "$gopro_dir" -maxdepth 1 -name "$pattern" -print0 2>/dev/null)
done

echo ""
if [ "$dry_run" = true ]; then
  echo "Dry run complete: $would_copy file(s) would be copied, $skipped already present."
else
  echo "Import complete: $copied new file(s), $skipped already present."
fi
