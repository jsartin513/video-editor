#!/bin/bash

# Collect all split matchup videos into the tournament deliverables folder.
# Usage: collect_deliverables.sh <tournament_root> [--copy|--symlink]
#
# Default: symlink (no duplicate disk usage)

set -e

tournament_root=""
mode="symlink"

show_usage() {
  cat << EOF
Usage: $0 <tournament_root> [--copy|--symlink]

  <tournament_root>   e.g. src/output/June2026Tournament

Options:
  --copy              Copy files instead of symlinking
  --symlink           Symlink files (default)
  -h, --help          Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --copy)
      mode="copy"
      shift
      ;;
    --symlink)
      mode="symlink"
      shift
      ;;
    -h|--help)
      show_usage
      exit 0
      ;;
    -*)
      echo "Unknown option: $1"
      show_usage
      exit 1
      ;;
    *)
      if [ -z "$tournament_root" ]; then
        tournament_root="$1"
      else
        echo "Unexpected argument: $1"
        show_usage
        exit 1
      fi
      shift
      ;;
  esac
done

if [ -z "$tournament_root" ]; then
  show_usage
  exit 1
fi

if [ ! -d "$tournament_root" ]; then
  echo "Error: Tournament root not found: $tournament_root"
  exit 1
fi

tournament_root="$(cd "$tournament_root" && pwd)"
deliverables_dir="$tournament_root/deliverables"
mkdir -p "$deliverables_dir"

echo "=== Collect Deliverables ==="
echo "Source:  $tournament_root"
echo "Target:  $deliverables_dir"
echo "Mode:    $mode"
echo ""

count=0
while IFS= read -r -d '' video; do
  filename="$(basename "$video")"
  dest="$deliverables_dir/$filename"

  if [ -e "$dest" ] || [ -L "$dest" ]; then
    rm -f "$dest"
  fi

  if [ "$mode" = "copy" ]; then
    cp -p "$video" "$dest"
    echo "Copied: $filename"
  else
    ln -sf "$video" "$dest"
    echo "Linked: $filename"
  fi
  count=$((count + 1))
done < <(find "$tournament_root" -path '*/split_videos/*' \( -name '*.mp4' -o -name '*.MP4' \) -print0 2>/dev/null)

echo ""
echo "Collected $count matchup video(s) into deliverables/"
