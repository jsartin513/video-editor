#!/bin/bash

# GoPro Test File Generator
# Creates test video chunks that simulate GoPro footage for testing the portable processing system
# Takes a source video and splits it into multiple chunks with GoPro-style naming

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

# Configuration
CHUNK_DURATION=60  # seconds per chunk
MAX_CHUNKS=8       # maximum number of chunks to create
TEST_DURATION=300  # 5 minutes total

show_usage() {
    cat << EOF
GoPro Test File Generator

Creates test video chunks that simulate GoPro footage for testing the portable 
processing system.

Usage: $0 SOURCE_VIDEO OUTPUT_DIR [OPTIONS]

Arguments:
    SOURCE_VIDEO    Path to source video file (MP4, MOV, etc.)
    OUTPUT_DIR      Directory to create test files in

Options:
    --duration SECS     Duration to extract from source (default: $TEST_DURATION seconds)
    --chunk-size SECS   Size of each chunk (default: $CHUNK_DURATION seconds)
    --max-chunks NUM    Maximum chunks to create (default: $MAX_CHUNKS)
    --start-time SECS   Start time in source video (default: 0)
    --gopro-id ID       4-digit ID for GoPro files (default: random)
    --create-structure  Create full DCIM/100GOPRO structure
    --help             Show this help

Examples:
    # Basic usage - create test files from a video
    $0 ~/Movies/sample.mp4 ~/Desktop/test_gopro

    # Create 3 minutes of test files starting at 1 minute mark
    $0 ~/Movies/sample.mp4 ~/Desktop/test_gopro --start-time 60 --duration 180

    # Create full GoPro directory structure
    $0 ~/Movies/sample.mp4 ~/Desktop/test_sd_card --create-structure

    # Custom chunk size and GoPro ID
    $0 ~/Movies/sample.mp4 ~/Desktop/test --chunk-size 90 --gopro-id 4163

The script will create files like:
    GX014163.MP4, GX024163.MP4, GX034163.MP4, etc.

EOF
}

# Parse command line arguments
SOURCE_VIDEO=""
OUTPUT_DIR=""
START_TIME=0
CREATE_STRUCTURE=false
GOPRO_ID=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --duration)
            TEST_DURATION="$2"
            shift 2
            ;;
        --chunk-size)
            CHUNK_DURATION="$2"
            shift 2
            ;;
        --max-chunks)
            MAX_CHUNKS="$2"
            shift 2
            ;;
        --start-time)
            START_TIME="$2"
            shift 2
            ;;
        --gopro-id)
            GOPRO_ID="$2"
            shift 2
            ;;
        --create-structure)
            CREATE_STRUCTURE=true
            shift
            ;;
        --help)
            show_usage
            exit 0
            ;;
        --*)
            log_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
        *)
            if [[ -z "$SOURCE_VIDEO" ]]; then
                SOURCE_VIDEO="$1"
            elif [[ -z "$OUTPUT_DIR" ]]; then
                OUTPUT_DIR="$1"
            else
                log_error "Too many arguments"
                show_usage
                exit 1
            fi
            shift
            ;;
    esac
done

# Validate arguments
if [[ -z "$SOURCE_VIDEO" || -z "$OUTPUT_DIR" ]]; then
    log_error "Missing required arguments"
    show_usage
    exit 1
fi

if [[ ! -f "$SOURCE_VIDEO" ]]; then
    log_error "Source video not found: $SOURCE_VIDEO"
    exit 1
fi

# Check dependencies
if ! command -v ffmpeg >/dev/null 2>&1; then
    log_error "ffmpeg is required but not installed"
    log_info "Install with: brew install ffmpeg (macOS) or sudo apt install ffmpeg (Linux)"
    exit 1
fi

# Generate GoPro ID if not provided
if [[ -z "$GOPRO_ID" ]]; then
    GOPRO_ID=$(printf "%04d" $((RANDOM % 10000)))
    log_info "Generated GoPro ID: $GOPRO_ID"
fi

# Validate GoPro ID format
if [[ ! "$GOPRO_ID" =~ ^[0-9]{4}$ ]]; then
    log_error "GoPro ID must be 4 digits: $GOPRO_ID"
    exit 1
fi

# Create output directory structure
if [[ "$CREATE_STRUCTURE" == "true" ]]; then
    OUTPUT_PATH="$OUTPUT_DIR/DCIM/100GOPRO"
    log_info "Creating full GoPro directory structure"
else
    OUTPUT_PATH="$OUTPUT_DIR"
fi

mkdir -p "$OUTPUT_PATH"

# Get source video info
log_info "Analyzing source video: $(basename "$SOURCE_VIDEO")"
SOURCE_DURATION=$(ffprobe -v quiet -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$SOURCE_VIDEO")
SOURCE_DURATION_INT=${SOURCE_DURATION%.*}  # Remove decimal part

log_info "Source duration: ${SOURCE_DURATION_INT} seconds"
log_info "Requested test duration: $TEST_DURATION seconds"
log_info "Start time: $START_TIME seconds"

# Check if we have enough source material
AVAILABLE_DURATION=$((SOURCE_DURATION_INT - START_TIME))
if [[ $AVAILABLE_DURATION -lt $TEST_DURATION ]]; then
    log_warning "Not enough source material for full test duration"
    log_warning "Available: ${AVAILABLE_DURATION}s, Requested: ${TEST_DURATION}s"
    TEST_DURATION=$AVAILABLE_DURATION
fi

# Calculate number of chunks needed
CHUNKS_NEEDED=$(((TEST_DURATION + CHUNK_DURATION - 1) / CHUNK_DURATION))  # Ceiling division
if [[ $CHUNKS_NEEDED -gt $MAX_CHUNKS ]]; then
    CHUNKS_NEEDED=$MAX_CHUNKS
    log_warning "Limiting to $MAX_CHUNKS chunks"
fi

log_info "Creating $CHUNKS_NEEDED chunks of ${CHUNK_DURATION}s each"
echo ""

# Create chunks
CURRENT_START=$START_TIME
CHUNK_NUM=1

for ((i=1; i<=CHUNKS_NEEDED; i++)); do
    # Generate filename with GoPro pattern: GX01XXXX.MP4, GX02XXXX.MP4, etc.
    FILENAME=$(printf "GX%02d%s.MP4" $i "$GOPRO_ID")
    OUTPUT_FILE="$OUTPUT_PATH/$FILENAME"
    
    # Calculate duration for this chunk
    REMAINING_DURATION=$((TEST_DURATION - (i - 1) * CHUNK_DURATION))
    if [[ $REMAINING_DURATION -lt $CHUNK_DURATION ]]; then
        CURRENT_DURATION=$REMAINING_DURATION
    else
        CURRENT_DURATION=$CHUNK_DURATION
    fi
    
    log_info "Creating chunk $i/$CHUNKS_NEEDED: $FILENAME (${CURRENT_DURATION}s)"
    
    # Extract chunk using ffmpeg
    ffmpeg -y -v quiet -stats \
        -i "$SOURCE_VIDEO" \
        -ss "$CURRENT_START" \
        -t "$CURRENT_DURATION" \
        -c copy \
        -avoid_negative_ts make_zero \
        "$OUTPUT_FILE"
    
    if [[ $? -eq 0 ]]; then
        # Get file size for confirmation
        if [[ "$OSTYPE" == "darwin"* ]]; then
            FILE_SIZE=$(stat -f%z "$OUTPUT_FILE")
        else
            FILE_SIZE=$(stat -c%s "$OUTPUT_FILE")
        fi
        FILE_SIZE_MB=$((FILE_SIZE / 1024 / 1024))
        log_success "  ✓ Created $FILENAME (${FILE_SIZE_MB}MB)"
    else
        log_error "  ✗ Failed to create $FILENAME"
        exit 1
    fi
    
    CURRENT_START=$((CURRENT_START + CURRENT_DURATION))
done

echo ""
log_success "Test file creation complete!"
echo ""
log_info "Created files:"
for file in "$OUTPUT_PATH"/GX*"$GOPRO_ID".MP4; do
    if [[ -f "$file" ]]; then
        if [[ "$OSTYPE" == "darwin"* ]]; then
            FILE_SIZE=$(stat -f%z "$file")
        else
            FILE_SIZE=$(stat -c%s "$file")
        fi
        FILE_SIZE_MB=$((FILE_SIZE / 1024 / 1024))
        echo "  $(basename "$file") (${FILE_SIZE_MB}MB)"
    fi
done

echo ""
log_info "Test directory: $OUTPUT_PATH"

if [[ "$CREATE_STRUCTURE" == "true" ]]; then
    echo ""
    log_info "Full directory structure created:"
    echo "  $OUTPUT_DIR/"
    echo "  └── DCIM/"
    echo "      └── 100GOPRO/"
    find "$OUTPUT_PATH" -name "*.MP4" | while read file; do
        echo "          ├── $(basename "$file")"
    done
    echo ""
    log_info "You can now test with this directory as a mock GoPro SD card"
    log_info "Mount point simulation: $OUTPUT_DIR"
fi

echo ""
log_info "To test the portable processing system:"
log_info "  1. Use this directory as your test GoPro card source"
log_info "  2. Set up a processing hub: ./portable_helper.sh setup"
log_info "  3. Test processing: ./portable_helper.sh test"
echo ""
