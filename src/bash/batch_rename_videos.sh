#!/bin/bash

# Batch rename utility for video files
# Adds round names, court names, and other metadata to filenames

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

show_usage() {
    cat << EOF
Usage: $0 [OPTIONS] <video_directory>

Batch rename video files with tournament/round/court information

OPTIONS:
    -t, --tournament    Tournament name
    -r, --round        Round name (e.g., "Quarterfinals", "Semifinals")
    -c, --court        Court name/number
    -p, --prefix       Add prefix to filenames
    -s, --suffix       Add suffix to filenames
    --dry-run          Show what would be renamed without actually doing it
    -h, --help         Show this help

EXAMPLES:
    $0 -t "Summer_Tournament" -r "Semifinals" -c "Court_1" /path/to/videos
    $0 --prefix "2025_" --suffix "_HD" /path/to/videos
    $0 --dry-run -t "Tournament" /path/to/videos

EOF
}

# Parse arguments
TOURNAMENT=""
ROUND=""
COURT=""
PREFIX=""
SUFFIX=""
DRY_RUN=false
VIDEO_DIR=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -t|--tournament)
            TOURNAMENT="$2"
            shift 2
            ;;
        -r|--round)
            ROUND="$2"
            shift 2
            ;;
        -c|--court)
            COURT="$2"
            shift 2
            ;;
        -p|--prefix)
            PREFIX="$2"
            shift 2
            ;;
        -s|--suffix)
            SUFFIX="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        -*)
            log_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
        *)
            VIDEO_DIR="$1"
            shift
            ;;
    esac
done

if [[ -z "$VIDEO_DIR" ]]; then
    log_error "Video directory is required"
    show_usage
    exit 1
fi

if [[ ! -d "$VIDEO_DIR" ]]; then
    log_error "Directory not found: $VIDEO_DIR"
    exit 1
fi

# Build the naming pattern
build_new_name() {
    local original_name="$1"
    local base_name="${original_name%.*}"
    local extension="${original_name##*.}"
    local new_name=""
    
    # Add prefix
    [[ -n "$PREFIX" ]] && new_name="${PREFIX}"
    
    # Add tournament info
    if [[ -n "$TOURNAMENT" ]]; then
        [[ -n "$new_name" ]] && new_name="${new_name}_"
        new_name="${new_name}${TOURNAMENT}"
    fi
    
    # Add round info
    if [[ -n "$ROUND" ]]; then
        [[ -n "$new_name" ]] && new_name="${new_name}_"
        new_name="${new_name}${ROUND}"
    fi
    
    # Add court info
    if [[ -n "$COURT" ]]; then
        [[ -n "$new_name" ]] && new_name="${new_name}_"
        new_name="${new_name}${COURT}"
    fi
    
    # Add original name
    [[ -n "$new_name" ]] && new_name="${new_name}_"
    new_name="${new_name}${base_name}"
    
    # Add suffix
    [[ -n "$SUFFIX" ]] && new_name="${new_name}${SUFFIX}"
    
    # Add extension
    new_name="${new_name}.${extension}"
    
    echo "$new_name"
}

# Process video files
log_info "Processing videos in: $VIDEO_DIR"
[[ "$DRY_RUN" == "true" ]] && log_warning "DRY RUN MODE - No files will be renamed"

count=0
for video_file in "$VIDEO_DIR"/*.{mp4,MP4,mov,MOV,avi,AVI} 2>/dev/null; do
    [[ -f "$video_file" ]] || continue
    
    original_name=$(basename "$video_file")
    new_name=$(build_new_name "$original_name")
    
    if [[ "$original_name" == "$new_name" ]]; then
        log_info "No change needed: $original_name"
        continue
    fi
    
    new_path="$(dirname "$video_file")/$new_name"
    
    if [[ -f "$new_path" ]]; then
        log_warning "Target file already exists: $new_name"
        continue
    fi
    
    log_info "Renaming: $original_name -> $new_name"
    
    if [[ "$DRY_RUN" == "false" ]]; then
        mv "$video_file" "$new_path"
        ((count++))
    fi
done

if [[ "$DRY_RUN" == "true" ]]; then
    log_info "Dry run completed. Use without --dry-run to actually rename files."
else
    log_success "Renamed $count video files"
fi
