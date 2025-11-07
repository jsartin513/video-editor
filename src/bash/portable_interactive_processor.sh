#!/bin/bash

# Portable Interactive GoPro Video Processor
# Enhanced version that supports portable SD card processing
# Handles dual SD card setup: processing hub + source micro SD card

set -e  # Exit on any error

# Default configuration (can be overridden by portable setup)
MOVIES_DIR="${MOVIES_DIR:-/Users/MrsHazmat/Movies}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMBINE_SCRIPT="$SCRIPT_DIR/combine_gopro_videos.sh"

# Portable mode detection
PORTABLE_MODE=false
if [[ "$SCRIPT_DIR" == *"/processing_scripts" ]]; then
    PORTABLE_MODE=true
    SD_ROOT="$(dirname "$SCRIPT_DIR")"
    MOVIES_DIR="$SD_ROOT/workspace"
    print_info "Running in portable mode from SD card: $(basename "$SD_ROOT")"
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Function to print colored messages
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

print_header() {
    echo -e "${BLUE}=== $1 ===${NC}"
}

# Parse command line arguments for portable mode
SOURCE_CARD=""
OUTPUT_DIR=""
EVENT_NAME=""
DATE_ID=""
COURT_NUM=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --source-card)
            SOURCE_CARD="$2"
            shift 2
            ;;
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --event-name)
            EVENT_NAME="$2"
            shift 2
            ;;
        --date-id)
            DATE_ID="$2"
            shift 2
            ;;
        --court-num)
            COURT_NUM="$2"
            shift 2
            ;;
        --help)
            cat << EOF
Portable Interactive GoPro Video Processor

Usage: $0 [OPTIONS]

Options:
    --source-card PATH    Path to GoPro micro SD card
    --output-dir PATH     Directory for processed videos
    --event-name NAME     Event name for the videos
    --date-id ID          Date identifier (e.g., sept_17_2025)
    --court-num NUM       Court number
    --help               Show this help

If run without options, will use interactive mode.
EOF
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Enhanced SD card detection that separates processing hub from source cards
detect_sd_cards() {
    print_info "Scanning for SD cards..."
    
    local source_cards=()
    local source_names=()
    
    # In portable mode, exclude the processing hub SD card
    local exclude_path=""
    if [[ "$PORTABLE_MODE" == "true" ]]; then
        exclude_path="$SD_ROOT"
        print_info "Excluding processing hub: $(basename "$SD_ROOT")"
    fi
    
    for volume in /Volumes/*; do
        if [[ -d "$volume" && "$volume" != "$exclude_path" ]]; then
            print_info "Checking volume: $(basename "$volume")"
            
            # Check for GoPro structure
            if [[ -d "$volume/DCIM/100GOPRO" ]]; then
                local volume_name=$(basename "$volume")
                local gopro_count=$(find "$volume/DCIM/100GOPRO" -name "*.MP4" 2>/dev/null | wc -l | tr -d ' ')
                print_info "  Found $gopro_count MP4 files in $volume_name"
                
                if [[ "$gopro_count" -gt 0 ]]; then
                    source_cards+=("$volume")
                    source_names+=("$volume_name")
                    print_status "  ✓ Added: $volume_name ($gopro_count MP4 files)"
                fi
            else
                print_info "  No GoPro structure in $(basename "$volume")"
            fi
        fi
    done
    
    print_info "Found ${#source_cards[@]} GoPro source cards"
    
    if [[ ${#source_cards[@]} -eq 0 ]]; then
        print_error "No GoPro source cards found"
        if [[ "$PORTABLE_MODE" == "true" ]]; then
            print_info "Please insert a micro SD card with GoPro footage"
        fi
        return 1
    elif [[ ${#source_cards[@]} -eq 1 ]]; then
        print_status "Using source card: $(basename "${source_cards[0]}")"
        echo "${source_cards[0]}"
        return 0
    else
        echo ""
        print_header "Multiple GoPro Source Cards Found"
        for i in "${!source_names[@]}"; do
            local count=$(find "${source_cards[$i]}/DCIM/100GOPRO" -name "*.MP4" 2>/dev/null | wc -l | tr -d ' ')
            echo "$((i+1)). ${source_names[$i]} ($count files)"
        done
        echo ""
        
        while true; do
            read -p "Select source card (1-${#source_cards[@]}): " choice
            if [[ "$choice" =~ ^[0-9]+$ ]] && [[ "$choice" -ge 1 ]] && [[ "$choice" -le "${#source_cards[@]}" ]]; then
                print_status "Selected: ${source_names[$((choice-1))]}"
                echo "${source_cards[$((choice-1))]}"
                return 0
            else
                print_error "Invalid choice. Please enter a number between 1 and ${#source_cards[@]}."
            fi
        done
    fi
}

# Enhanced file analysis for portable mode
analyze_files() {
    local gopro_dir="$1"
    
    print_info "Analyzing GoPro files..."
    
    # Create temporary file for dates
    local temp_dates=$(mktemp)
    
    # Find all GoPro files and extract their creation dates
    local file_count=0
    local date_range_start=""
    local date_range_end=""
    
    # Check for multiple GoPro naming patterns
    for pattern in "GX??????.MP4" "GOPR????.MP4" "GP??????.MP4"; do
        while IFS= read -r -d '' file; do
            if [[ -f "$file" ]]; then
                local filename=$(basename "$file")
                local file_date=""
                
                # Try to get creation date from file metadata
                if command -v mediainfo >/dev/null 2>&1; then
                    file_date=$(mediainfo --Output="General;%Encoded_Date%" "$file" 2>/dev/null)
                fi
                
                # Fallback to file modification date if metadata unavailable
                if [[ -z "$file_date" ]]; then
                    if [[ "$OSTYPE" == "darwin"* ]]; then
                        file_date=$(stat -f "%Sm" -t "%Y-%m-%d %H:%M:%S" "$file")
                    else
                        file_date=$(stat -c "%y" "$file" | cut -d'.' -f1)
                    fi
                fi
                
                echo "$file_date|$filename|$file" >> "$temp_dates"
                ((file_count++))
                
                # Track date range
                if [[ -z "$date_range_start" ]] || [[ "$file_date" < "$date_range_start" ]]; then
                    date_range_start="$file_date"
                fi
                if [[ -z "$date_range_end" ]] || [[ "$file_date" > "$date_range_end" ]]; then
                    date_range_end="$file_date"
                fi
            fi
        done < <(find "$gopro_dir/DCIM/100GOPRO" -name "$pattern" -print0 2>/dev/null)
    done
    
    if [[ $file_count -eq 0 ]]; then
        print_error "No GoPro files found!"
        rm -f "$temp_dates"
        return 1
    fi
    
    # Sort by date
    sort "$temp_dates" > "${temp_dates}.sorted"
    mv "${temp_dates}.sorted" "$temp_dates"
    
    # Display summary
    print_info "Found $file_count GoPro files"
    if [[ -n "$date_range_start" && -n "$date_range_end" ]]; then
        print_info "Date range: $date_range_start to $date_range_end"
    fi
    
    # Show first and last few files
    echo ""
    print_info "First 3 files:"
    head -3 "$temp_dates" | while IFS='|' read -r date filename filepath; do
        echo "  $filename ($date)"
    done
    
    if [[ $file_count -gt 6 ]]; then
        echo "  ..."
    fi
    
    if [[ $file_count -gt 3 ]]; then
        echo ""
        print_info "Last 3 files:"
        tail -3 "$temp_dates" | while IFS='|' read -r date filename filepath; do
            echo "  $filename ($date)"
        done
    fi
    
    echo "$temp_dates"
}

# Import files with portable mode support
import_files() {
    local gopro_dir="$1"
    local event_date="$2"
    local event_name="$3"
    local court_num="$4"
    local import_mode="$5"
    local temp_dates="$6"
    
    # Create destination directory
    local dest_dir="$MOVIES_DIR/${event_date}_court_${court_num}"
    if [[ "$PORTABLE_MODE" == "true" && -n "$OUTPUT_DIR" ]]; then
        dest_dir="$OUTPUT_DIR"
    fi
    
    print_info "Creating destination: $dest_dir"
    mkdir -p "$dest_dir"
    
    # Copy files
    local copied_count=0
    
    if [[ "$import_mode" == "all" ]]; then
        print_info "Copying all files..."
        while IFS='|' read -r file_date filename filepath; do
            if [[ -f "$filepath" ]]; then
                print_info "  Copying $filename (recorded $file_date)..."
                cp "$filepath" "$dest_dir/"
                ((copied_count++))
            fi
        done < "$temp_dates"
    else
        # Filter by today's date (existing logic)
        local today=$(date "+%Y-%m-%d")
        print_info "Copying files from $today..."
        
        while IFS='|' read -r file_date filename filepath; do
            if [[ "$file_date" == "$today"* ]]; then
                if [[ -f "$filepath" ]]; then
                    print_info "  Copying $filename (recorded $file_date)..."
                    cp "$filepath" "$dest_dir/"
                    ((copied_count++))
                fi
            fi
        done < "$temp_dates"
    fi
    
    if [[ "$copied_count" -eq 0 ]]; then
        print_error "No files were copied!"
        return 1
    fi
    
    print_status "Copied $copied_count files to $dest_dir"
    echo "$dest_dir"
}

# Enhanced processing for portable mode
process_videos() {
    local source_dir="$1"
    local event_date="$2"
    local event_name="$3"
    local court_num="$4"
    
    print_info "Processing videos..."
    
    # Check if we have files to process
    local mp4_count=$(find "$source_dir" -name "*.MP4" 2>/dev/null | wc -l | tr -d ' ')
    if [[ "$mp4_count" -eq 0 ]]; then
        print_error "No MP4 files found in $source_dir"
        return 1
    fi
    
    # Create merged videos directory
    local merged_dir="$source_dir/merged_videos"
    mkdir -p "$merged_dir"
    
    # Run the combine script
    print_info "Combining videos..."
    "$COMBINE_SCRIPT" "$source_dir"
    
    if [[ $? -ne 0 ]]; then
        print_error "Failed to combine videos"
        return 1
    fi
    
    # Find the merged video
    local merged_video=$(find "$merged_dir" -name "*.MP4" | head -1)
    if [[ ! -f "$merged_video" ]]; then
        print_error "No merged video found"
        return 1
    fi
    
    print_status "Video processing complete"
    echo "$merged_video"
}

# Main function with portable mode support
main() {
    echo ""
    if [[ "$PORTABLE_MODE" == "true" ]]; then
        print_header "Portable GoPro Video Processor"
        print_info "Processing hub: $(basename "$SD_ROOT")"
    else
        print_header "Interactive GoPro Video Processor"
    fi
    echo ""
    
    # Get source SD card
    local gopro_dir=""
    if [[ -n "$SOURCE_CARD" ]]; then
        gopro_dir="$SOURCE_CARD"
        print_info "Using specified source card: $(basename "$gopro_dir")"
    else
        gopro_dir=$(detect_sd_cards)
        if [[ $? -ne 0 ]]; then
            exit 1
        fi
    fi
    
    # Analyze files on source card
    local temp_dates=$(analyze_files "$gopro_dir")
    if [[ $? -ne 0 ]]; then
        exit 1
    fi
    
    # Get event details if not provided
    local event_date="$DATE_ID"
    local event_name="$EVENT_NAME"
    local court_num="$COURT_NUM"
    
    if [[ -z "$event_date" ]]; then
        echo ""
        print_info "Event details needed:"
        read -p "Enter date identifier (e.g., sept_17_2025): " event_date
    fi
    
    if [[ -z "$event_name" ]]; then
        read -p "Enter event name (e.g., league_night): " event_name
    fi
    
    if [[ -z "$court_num" ]]; then
        read -p "Enter court number (e.g., 2): " court_num
    fi
    
    # Choose import mode
    echo ""
    print_info "Import options:"
    echo "1. Today's files only"
    echo "2. All files"
    
    local import_mode="today"
    if [[ -z "$DATE_ID" ]]; then  # Only ask if not in portable mode with pre-set options
        read -p "Choose import mode (1-2) [1]: " mode_choice
        case $mode_choice in
            2) import_mode="all" ;;
            *) import_mode="today" ;;
        esac
    else
        import_mode="all"  # In portable mode, import all files
    fi
    
    # Confirm processing
    echo ""
    print_info "Processing summary:"
    print_info "  Source: $(basename "$gopro_dir")"
    print_info "  Event: $event_name"
    print_info "  Date: $event_date"
    print_info "  Court: $court_num"
    print_info "  Mode: $import_mode"
    
    if [[ "$PORTABLE_MODE" == "true" ]]; then
        print_info "  Output: $OUTPUT_DIR"
    else
        print_info "  Output: $MOVIES_DIR/${event_date}_court_${court_num}"
    fi
    
    echo ""
    if [[ -z "$DATE_ID" ]]; then  # Only ask for confirmation in interactive mode
        echo -n "Proceed with import and processing? (Y/n): "
        read confirm
        if [[ "$confirm" == "n" ]] || [[ "$confirm" == "N" ]]; then
            print_info "Processing cancelled."
            rm -f "$temp_dates"
            exit 0
        fi
    fi
    
    # Import files
    local dest_dir=$(import_files "$gopro_dir" "$event_date" "$event_name" "$court_num" "$import_mode" "$temp_dates")
    if [[ $? -ne 0 ]]; then
        print_error "File import failed!"
        rm -f "$temp_dates"
        exit 1
    fi
    
    # Process videos
    local output_file=$(process_videos "$dest_dir" "$event_date" "$event_name" "$court_num")
    if [[ $? -ne 0 ]]; then
        print_error "Video processing failed!"
        rm -f "$temp_dates"
        exit 1
    fi
    
    # Clean up temporary files
    rm -f "$temp_dates"
    
    echo ""
    print_header "Processing Complete!"
    print_status "Merged video: $output_file"
    
    if [[ "$PORTABLE_MODE" == "true" ]]; then
        print_status "Output directory: $dest_dir"
        print_info "Videos are ready for upload!"
        print_info "You can now safely eject both SD cards."
    else
        print_status "Output directory: $dest_dir"
        
        # Ask if user wants to open the folder
        echo ""
        read -p "Open output folder? (Y/n): " open_folder
        if [[ "$open_folder" != "n" && "$open_folder" != "N" ]]; then
            if [[ "$OSTYPE" == "darwin"* ]]; then
                open "$dest_dir"
            elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
                xdg-open "$dest_dir" 2>/dev/null || echo "Output directory: $dest_dir"
            fi
        fi
    fi
    
    echo ""
}

# Run main function
main "$@"
