#!/bin/bash

# Interactive GoPro Video Processor
# Handles SD card detection, file import, and video processing
# Supports multiple GoPro file naming patterns: GX??????.MP4, GOPR????.MP4, GP??????.MP4

set -e  # Exit on any error

# Configuration
MOVIES_DIR="/Users/MrsHazmat/Movies"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMBINE_SCRIPT="$SCRIPT_DIR/combine_gopro_videos.sh"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Function to detect SD cards
detect_sd_cards() {
    print_info "Scanning for SD cards..."
    print_info "Checking /Volumes/ directory..."
    
    local sd_cards=()
    local sd_names=()
    
    for volume in /Volumes/*; do
        print_info "Checking volume: $volume"
        if [ -d "$volume" ]; then
            print_info "  Volume exists, checking for DCIM/100GOPRO..."
            if [ -d "$volume/DCIM/100GOPRO" ]; then
                print_info "  Found GoPro structure, counting MP4 files..."
                local volume_name=$(basename "$volume")
                local gopro_count=$(find "$volume/DCIM/100GOPRO" -name "*.MP4" 2>/dev/null | wc -l | tr -d ' ')
                print_info "  Found $gopro_count MP4 files in $volume_name"
                if [ "$gopro_count" -gt 0 ]; then
                    sd_cards+=("$volume")
                    sd_names+=("$volume_name")
                    echo "  ✓ Added: $volume_name ($gopro_count MP4 files)"
                fi
            else
                print_info "  No DCIM/100GOPRO structure found"
            fi
        else
            print_info "  Volume does not exist or not accessible"
        fi
    done
    
    print_info "SD card detection complete. Found ${#sd_cards[@]} cards with MP4 files."
    
    if [ ${#sd_cards[@]} -eq 0 ]; then
        print_error "No GoPro SD cards found"
        return 1
    elif [ ${#sd_cards[@]} -eq 1 ]; then
        print_status "Using single SD card: $(basename "${sd_cards[0]}")"
        echo "${sd_cards[0]}"
        return 0
    else
        echo ""
        print_header "Multiple SD Cards Found"
        for i in "${!sd_names[@]}"; do
            local count=$(find "${sd_cards[$i]}/DCIM/100GOPRO" -name "*.MP4" 2>/dev/null | wc -l | tr -d ' ')
            echo "$((i+1)). ${sd_names[$i]} ($count files)"
        done
        echo ""
        
        while true; do
            read -p "Select SD card (1-${#sd_cards[@]}): " choice
            if [[ "$choice" =~ ^[0-9]+$ ]] && [ "$choice" -ge 1 ] && [ "$choice" -le "${#sd_cards[@]}" ]; then
                print_status "Selected: ${sd_names[$((choice-1))]}"
                echo "${sd_cards[$((choice-1))]}"
                return 0
            else
                print_error "Invalid choice. Please enter a number between 1 and ${#sd_cards[@]}."
            fi
        done
    fi
}

# Function to analyze files on SD card (simplified approach)
analyze_sd_card_files() {
    local gopro_dir="$1"
    
    print_info "Analyzing files on SD card at: $gopro_dir"
    
    # Find all MP4 files and categorize by pattern
    print_info "Searching for GX files..."
    local gx_files=($(find "$gopro_dir" -name "GX??????.MP4" 2>/dev/null | sort))
    print_info "Found ${#gx_files[@]} GX files"
    
    print_info "Searching for GOPR files..."
    local gopr_files=($(find "$gopro_dir" -name "GOPR????.MP4" 2>/dev/null | sort))
    print_info "Found ${#gopr_files[@]} GOPR files"
    
    print_info "Searching for GP files..."
    local gp_files=($(find "$gopro_dir" -name "GP??????.MP4" 2>/dev/null | sort))
    print_info "Found ${#gp_files[@]} GP files"
    
    local total_files=$((${#gx_files[@]} + ${#gopr_files[@]} + ${#gp_files[@]}))
    print_info "Total MP4 files found: $total_files"
    
    echo ""
    echo "File Analysis:"
    echo "  GX?????? pattern: ${#gx_files[@]} files"
    echo "  GOPR???? pattern: ${#gopr_files[@]} files"
    echo "  GP?????? pattern: ${#gp_files[@]} files"
    echo "  Total MP4 files: $total_files"
    echo ""
    
    if [ "$total_files" -eq 0 ]; then
        print_error "No GoPro MP4 files found!"
        return 1
    fi
    
    # Group files by the last 4 digits (video session ID)
    print_info "Analyzing recording sessions..."
    local session_ids=$(printf '%s\n' "${gx_files[@]}" "${gopr_files[@]}" "${gp_files[@]}" | \
                       sed -E 's/.*[A-Z]{2,4}[0-9]*([0-9]{4})\.MP4/\1/' | sort | uniq)
    
    local session_count=$(echo "$session_ids" | wc -w | tr -d ' ')
    echo "Recording sessions found: $session_count"
    echo ""
    
    local session_num=1
    for session_id in $session_ids; do
        local files_in_session=$(printf '%s\n' "${gx_files[@]}" "${gopr_files[@]}" "${gp_files[@]}" | \
                                grep "$session_id\.MP4" | wc -l | tr -d ' ')
        echo "  $session_num. Session $session_id ($files_in_session files)"
        ((session_num++))
    done
    echo ""
    
    # Show first few files as preview
    echo "File preview (first 5):"
    local count=0
    for file in "${gx_files[@]}" "${gopr_files[@]}" "${gp_files[@]}"; do
        if [ $count -lt 5 ]; then
            echo "  - $(basename "$file")"
            ((count++))
        else
            break
        fi
    done
    
    if [ "$total_files" -gt 5 ]; then
        echo "  ... and $((total_files - 5)) more files"
    fi
    
    echo ""
    return 0
}

# Function to get user input for event details
get_event_details() {
    echo ""
    echo "=== Event Details ==="
    
    # Get date
    local today=$(date "+%m.%d.%y")
    echo -n "Enter date (default: $today): "
    read date_input
    local event_date="${date_input:-$today}"
    
    # Get event type
    echo ""
    echo "Event types:"
    echo "  1. League Night"
    echo "  2. Open Gym"
    echo "  3. Tournament"
    echo "  4. Custom"
    echo -n "Select event type (1-4): "
    read event_type
    
    local event_name=""
    case $event_type in
        1) event_name="League Night" ;;
        2) event_name="Open Gym" ;;
        3) event_name="Tournament" ;;
        4) echo -n "Enter custom event name: "; read event_name ;;
        *) event_name="Open Gym" ;;
    esac
    
    # Get court number (optional)
    echo -n "Court number (leave empty if single court or combined): "
    read court_num
    
    echo "$event_date|$event_name|$court_num"
}

# Function to create destination directory and copy files
import_files() {
    local gopro_dir="$1"
    local event_date="$2"
    local event_name="$3"
    local court_num="$4"
    local selected_date="$5"  # Optional: specific date to filter by
    local temp_dates="$6"     # Optional: temp file with date mappings
    
    # Create safe directory name
    local date_safe=$(echo "$event_date" | tr '.' '_')
    local event_safe=$(echo "$event_name" | tr ' ' '_' | tr '[:upper:]' '[:lower:]')
    local dest_base="$MOVIES_DIR/bdl_${event_safe}_${date_safe}"
    
    if [ -n "$court_num" ]; then
        local dest_dir="$dest_base/court_$court_num"
    else
        local dest_dir="$dest_base/court_1"
    fi
    
    print_info "Creating directory: $dest_dir"
    mkdir -p "$dest_dir"
    
    # Copy files (all or filtered by date)
    print_info "Copying files from SD card..."
    local copied_count=0
    
    if [ "$selected_date" = "all" ] || [ -z "$selected_date" ]; then
        # Copy all MP4 files
        for file in "$gopro_dir"/*.MP4; do
            if [ -f "$file" ]; then
                local filename=$(basename "$file")
                echo "  Copying $filename..."
                cp "$file" "$dest_dir/"
                ((copied_count++))
            fi
        done
    else
        # Copy only files from selected date
        print_info "Filtering files for date: $selected_date"
        while IFS='|' read -r file_date file_path; do
            if [ "$file_date" = "$selected_date" ] && [ -f "$file_path" ]; then
                local filename=$(basename "$file_path")
                echo "  Copying $filename (recorded $file_date)..."
                cp "$file_path" "$dest_dir/"
                ((copied_count++))
            fi
        done < "$temp_dates"
    fi
    
    if [ "$copied_count" -eq 0 ]; then
        print_error "No files were copied!"
        return 1
    fi
    
    print_status "Copied $copied_count files to $dest_dir"
    echo "$dest_dir"
}

# Function to process videos
process_videos() {
    local source_dir="$1"
    local event_date="$2"
    local event_name="$3"
    local court_num="$4"
    
    print_info "Processing videos..."
    
    # Check if we have files to process
    local mp4_count=$(find "$source_dir" -name "*.MP4" 2>/dev/null | wc -l | tr -d ' ')
    if [ "$mp4_count" -eq 0 ]; then
        print_error "No MP4 files found in $source_dir"
        return 1
    fi
    
    # Create merged videos directory
    local merged_dir="$source_dir/merged_videos"
    mkdir -p "$merged_dir"
    
    # Create file list for ffmpeg (sorted)
    local filelist="$source_dir/filelist.txt"
    cd "$source_dir"
    
    # Sort files properly (GOPR first, then GP files in order)
    {
        ls GOPR*.MP4 2>/dev/null || true
        ls GP0*.MP4 2>/dev/null || true
        ls GX*.MP4 2>/dev/null || true
    } | while read -r file; do
        if [ -f "$file" ]; then
            echo "file '$file'"
        fi
    done > "$filelist"
    
    # Create output filename
    local output_name=""
    if [ -n "$court_num" ]; then
        output_name="$event_date $event_name Court $court_num.MP4"
    else
        output_name="$event_date $event_name.MP4"
    fi
    
    local output_file="$merged_dir/$output_name"
    
    print_info "Combining videos into: $output_name"
    
    # Use ffmpeg to combine videos
    if ffmpeg -f concat -safe 0 -i "$filelist" -c copy "$output_file" 2>/dev/null; then
        # Get file info
        local file_size=$(ls -lh "$output_file" | awk '{print $5}')
        
        if command -v ffprobe >/dev/null 2>&1; then
            local duration=$(ffprobe -v quiet -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$output_file" 2>/dev/null | awk '{printf "%02d:%02d:%02d", $1/3600, ($1%3600)/60, $1%60}')
            print_status "Video created: $file_size, Duration: $duration"
        else
            print_status "Video created: $file_size"
        fi
        
        # Clean up
        rm -f "$filelist"
        
        echo "$output_file"
        return 0
    else
        print_error "Failed to combine videos"
        rm -f "$filelist"
        return 1
    fi
}

# Function to concatenate GoPro files using direct ffmpeg (fallback method)
concatenate_gopro_files_direct() {
    local input_dir="$1"
    local output_file="$2"
    
    print_info "Using direct ffmpeg concatenation..."
    
    # Create temporary file list
    local temp_list="/tmp/gopro_filelist_$$"
    
    # Find all MP4 files and sort them
    find "$input_dir" -name "*.MP4" | sort | while read file; do
        echo "file '$(basename "$file")'" >> "$temp_list"
    done
    
    if [ ! -s "$temp_list" ]; then
        print_error "No MP4 files found in $input_dir"
        rm -f "$temp_list"
        return 1
    fi
    
    # Run ffmpeg concatenation
    cd "$input_dir"
    if ffmpeg -f concat -safe 0 -i "$temp_list" -c copy "$output_file"; then
        print_status "Successfully created: $output_file"
        rm -f "$temp_list"
        return 0
    else
        print_error "FFmpeg concatenation failed"
        rm -f "$temp_list"
        return 1
    fi
}

# Function to get import mode choice (simplified)
get_import_mode() {
    echo ""
    print_header "Import Options"
    echo "1. Import all files - Process all videos together into one combined video"
    echo "2. Import by session - Choose specific recording sessions to process"
    echo ""
    
    while true; do
        read -p "Choose import mode (1-2): " import_choice
        case $import_choice in
            1)
                echo "all"
                return 0
                ;;
            2)
                echo "session"
                return 0
                ;;
            *)
                print_error "Invalid choice. Please enter 1 or 2."
                ;;
        esac
    done
}

# Main interactive menu
main() {
    echo ""
    echo "================================================"
    echo "    Interactive GoPro Video Processor"
    echo "================================================"
    echo ""
    
    print_info "Starting GoPro processor..."
    
    # Check for required tools
    print_info "Checking for required tools..."
    if ! command -v ffmpeg >/dev/null 2>&1; then
        print_error "ffmpeg is required but not installed"
        exit 1
    fi
    print_status "ffmpeg found"
    
    # Detect SD cards
    print_info "Starting SD card detection..."
    local sd_cards=()
    while IFS= read -r card; do
        [ -n "$card" ] && sd_cards+=("$card")
    done < <(detect_sd_cards | grep "^/Volumes")
    
    print_info "SD card detection completed. Found ${#sd_cards[@]} cards."
    
    if [ ${#sd_cards[@]} -eq 0 ]; then
        print_error "No SD cards with GoPro files detected"
        echo ""
        echo "Make sure your SD card is:"
        echo "  1. Properly inserted"
        echo "  2. Mounted (visible in /Volumes/)"
        echo "  3. Contains DCIM/100GOPRO directory with MP4 files"
        exit 1
    fi
    
    # Select SD card if multiple found
    local selected_sd=""
    if [ ${#sd_cards[@]} -gt 1 ]; then
        echo ""
        echo "Multiple SD cards detected:"
        for i in "${!sd_cards[@]}"; do
            local volume_name=$(basename "${sd_cards[$i]}")
            local gopro_count=$(find "${sd_cards[$i]}/DCIM/100GOPRO" -name "*.MP4" 2>/dev/null | wc -l | tr -d ' ')
            echo "  $((i+1)). $volume_name ($gopro_count files)"
        done
        echo -n "Select SD card (1-${#sd_cards[@]}): "
        read choice
        selected_sd="${sd_cards[$((choice-1))]}"
    else
        selected_sd="${sd_cards[0]}"
    fi
    
    local volume_name=$(basename "$selected_sd")
    local gopro_dir="$selected_sd/DCIM/100GOPRO"
    
    print_status "Selected SD card: $volume_name"
    
    # Analyze files and get date information
    local temp_dates=$(analyze_sd_card_files "$gopro_dir")
    if [ $? -ne 0 ] || [ -z "$temp_dates" ]; then
        exit 1
    fi
    
    # Get import mode choice
    local import_mode=$(get_import_mode "$temp_dates")
    
    # Get event details
    local event_details=$(get_event_details)
    IFS='|' read -r event_date event_name court_num <<< "$event_details"
    
    echo ""
    echo "=== Processing Summary ==="
    echo "  Date: $event_date"
    echo "  Event: $event_name"
    if [ -n "$court_num" ]; then
        echo "  Court: $court_num"
    fi
    echo "  Import mode: $import_mode"
    echo ""
    
    # Confirm processing
    echo -n "Proceed with import and processing? (Y/n): "
    read confirm
    if [[ "$confirm" == "n" ]] || [[ "$confirm" == "N" ]]; then
        echo "Processing cancelled."
        rm -f "$temp_dates"
        exit 0
    fi
    
    # Import files with date filtering
    local dest_dir=$(import_files "$gopro_dir" "$event_date" "$event_name" "$court_num" "$import_mode" "$temp_dates")
    if [ $? -ne 0 ]; then
        print_error "File import failed!"
        rm -f "$temp_dates"
        exit 1
    fi
    
    # Process videos
    local output_file=$(process_videos "$dest_dir" "$event_date" "$event_name" "$court_num")
    if [ $? -ne 0 ]; then
        print_error "Video processing failed!"
        rm -f "$temp_dates"
        exit 1
    fi
    
    # Clean up temporary files
    rm -f "$temp_dates"
    
    echo ""
    echo "=== Complete! ==="
    print_status "Video saved to: $output_file"
    echo ""
    
    # Ask if user wants to open the folder
    echo -n "Open the output folder? (Y/n): "
    read open_folder
    if [[ "$open_folder" != "n" ]] && [[ "$open_folder" != "N" ]]; then
        open "$(dirname "$output_file")"
    fi
}

# Run the script
print_info "Initializing interactive GoPro processor..."
main "$@"
print_info "Script execution completed."
