#!/bin/bash

# Validate tournament merge/split pipeline using Spring2026Remix sample footage.
# Usage: validate_tournament_setup.sh [--dry-run] [--full]

set -e

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"
sample_week="$repo_root/src/output/Spring2026Remix/Week2"
test_root="$repo_root/src/output/June2026Tournament/_validation_test"

dry_run_only=false
full_run=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      dry_run_only=true
      shift
      ;;
    --full)
      full_run=true
      shift
      ;;
    -h|--help)
      echo "Usage: $0 [--dry-run] [--full]"
      echo "  --dry-run   Merge + split debug only (no ffmpeg segment writes)"
      echo "  --full      Also extract one short test segment with ffmpeg"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

if [ ! -d "$sample_week/court2" ]; then
  echo "Error: Sample footage not found at $sample_week/court2"
  exit 1
fi

for cmd in ffmpeg ffprobe jq; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Error: $cmd not installed. Run $script_dir/install.sh"
    exit 1
  fi
done

echo "=== Tournament Pipeline Validation ==="
echo "Sample: Week2/court2"
echo ""

rm -rf "$test_root"
mkdir -p "$test_root/court2"

for f in "$sample_week/court2"/GX*.MP4; do
  [ -e "$f" ] || continue
  cp -p "$f" "$test_root/court2/"
done

linked=$(find "$test_root/court2" -name 'GX*.MP4' | wc -l | tr -d ' ')
if [ "$linked" -eq 0 ]; then
  echo "Error: No sample GX files to link"
  exit 1
fi
echo "Copied $linked sample clip(s)"

echo ""
echo "--- Step 1: combine_gopro_videos.sh ---"
"$script_dir/combine_gopro_videos.sh" "$test_root/court2"

merged=$(find "$test_root/court2/merged_videos" -name 'PROCESSED*.MP4' | wc -l | tr -d ' ')
if [ "$merged" -eq 0 ]; then
  echo "Error: No PROCESSED*.MP4 files created"
  exit 1
fi
echo "Created $merged merged session file(s)"

cat > "$test_root/test_games.jsonl" << 'EOF'
{"type":"round_robin","round":"Round 1","home_team":"Test Home","away_team":"Test Away","start_time":"00:00:30","minutes":1,"court":"Court 2"}
{"type":"bracket","round":"Quarters","home_team":"Bracket Home","away_team":"Bracket Away","start_time":"00:02:00","minutes":1,"court":"Court 2"}
EOF

echo ""
echo "--- Step 2: split_multi_source_videos.sh (debug) ---"
"$script_dir/split_multi_source_videos.sh" \
  "$test_root/court2" \
  "$test_root/test_games.jsonl" \
  --tournament "June2026Tournament" \
  --court "Court 2" \
  --debug

if [ "$dry_run_only" = true ] && [ "$full_run" = false ]; then
  echo ""
  echo "Validation passed (dry-run)."
  exit 0
fi

echo ""
echo "--- Step 3: split_multi_source_videos.sh (extract) ---"
"$script_dir/split_multi_source_videos.sh" \
  "$test_root/court2" \
  "$test_root/test_games.jsonl" \
  --tournament "June2026Tournament" \
  --court "Court 2"

split_count=$(find "$test_root/court2/split_videos" -name '*.mp4' | wc -l | tr -d ' ')
if [ "$split_count" -lt 1 ]; then
  echo "Error: No split videos created"
  exit 1
fi

echo ""
echo "Split files:"
ls -lh "$test_root/court2/split_videos/"

rr_file="$test_root/court2/split_videos/Round Robin Round 1: Court 2: Test Home vs Test Away.mp4"
br_file="$test_root/court2/split_videos/Bracket Quarters: Court 2: Bracket Home vs Bracket Away.mp4"

if [ ! -f "$rr_file" ]; then
  echo "Warning: Expected round robin filename not found"
fi
if [ ! -f "$br_file" ]; then
  echo "Warning: Expected bracket filename not found"
fi

echo ""
echo "Validation passed."
