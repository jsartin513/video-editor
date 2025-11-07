#!/bin/bash

# GoPro SD Card Import Script
# Automatically detects SD cards and imports GoPro videos to organized folders
# Usage: ./import_gopro_videos.sh [date_identifier] [event_name] [--dry-run]
#
# Example: ./import_gopro_videos.sh "sept_17_2025" "league_night"
# Debug: ./import_gopro_videos.sh --dry-run

# Configuration
MOVIES_DIR="/Users/MrsHazmat/Movies"
GOPRO_PATTERN="GX??????.MP4"

# Check for dry-run mode
DRY_RUN=false
for arg in "$@"; do
    if [[ "$arg" == "--dry-run" ]] || [[ "$arg" == "--debug" ]]; then
        DRY_RUN=true
        echo "=== DRY RUN MODE - No files will be copied ==="
        echo ""
        break
    fi
done

# Remove dry-run flags from arguments
args=()
for arg in "$@"; do
    if [[ "$arg" != "--dry-run" ]] && [[ "$arg" != "--debug" ]]; then
        args+=("$arg")
    fi
done
set -- "${args[@]}"

# Function to show usage
show_usage() {
    echo "Usage: $0 [date_identifier] [event_name] [--dry-run]"
    echo ""
    echo "  [date_identifier]: Date for the folder (e.g., sept_17_2025)"
    echo "  [event_name]: Event type (e.g., league_night, tournament, etc.)"
    echo "  [--dry-run]: Show what would happen without copying files"
    echo ""
    echo "Examples:"
    echo "  $0 sept_17_2025 league_night"
    echo "  $0 oct_05_2025 tournament"
    echo "  $0 --dry-run"
    echo ""
    echo "If no parameters provided, will prompt for input."
}

# Function to detect SD cards on macOS
detect_sd_cards() {
    # Look for mounted volumes that might be SD cards
    # Check for GoPro directory structure: DCIM/100GOPRO
    local sd_cards=()
    
    # Check /Volumes for potential SD cards
    for volume in /Volumes/*; do
        if [ -d "$volume" ]; then
            volume_name=$(basename "$volume")
            
            # Skip system volumes
            if [[ "$volume_name" == "Macintosh HD"* ]] || [[ "$volume_name" == "System"* ]]; then
                continue
            fi
            
            # Check for GoPro directory structure
            gopro_dir="$volume/DCIM/100GOPRO"
            if [ -d "$gopro_dir" ]; then
                # Look for GoPro files in the correct directory
                gopro_count=$(find "$gopro_dir" -name "$GOPRO_PATTERN" 2>/dev/null | wc -l | tr -d ' ')
                if [ "$gopro_count" -gt 0 ]; then
                    sd_cards+=("$volume")
                    echo "Found GoPro SD card: $volume_name ($gopro_count GoPro files in DCIM/100GOPRO)" >&2
                fi
            fi
        fi
    done
    
    # Return only the paths, not the debug messages
    printf '%s\n' "${sd_cards[@]}"
}

# Function to get suggested date from selected files
get_suggested_date() {
    local session_files=("$@")
    
    if [ ${#session_files[@]} -gt 0 ]; then
        # Get date from first file in the selected session
        local first_file="${session_files[0]}"
        local file_date=$(stat -f "%Sm" -t "%b_%d_%Y" "$first_file" 2>/dev/null | tr 'A-Z' 'a-z')
        if [ -n "$file_date" ]; then
            echo "$file_date"
            return
        fi
    fi
    
    # Fallback to current date
    date +"%b_%d_%Y" | tr 'A-Z' 'a-z'
}

# Function to get user input if not provided
get_user_input() {
    local suggested_date="$3"  # Third parameter is suggested date
    
    if [ -z "$1" ]; then
        if [ -n "$suggested_date" ]; then
            echo ""
            echo "Latest files on SD card are from: $suggested_date"
            echo -n "Use this date? (Y/n): "
            read use_suggested
            if [[ "$use_suggested" == "n" ]] || [[ "$use_suggested" == "N" ]]; then
                echo -n "Enter date identifier (e.g., sept_17_2025): "
                read date_id
            else
                date_id="$suggested_date"
            fi
        else
            echo -n "Enter date identifier (e.g., sept_17_2025): "
            read date_id
        fi
    else
        date_id="$1"
    fi
    
    if [ -z "$2" ]; then
        echo -n "Enter event name (e.g., league_night): "
        read event_name
    else
        event_name="$2"
    fi
    
    echo "$date_id" "$event_name"
}

# Function to test if SD card is responsive
test_sd_card_access() {
    local gopro_dir="$1"
    echo "Testing SD card responsiveness..."
    
    # Try a simple test first
    if ! cd "$gopro_dir" 2>/dev/null; then
        echo "ERROR: Cannot access SD card directory: $gopro_dir"
        return 1
    fi
    
    # Try to list the directory without hanging
    if ! ls . >/dev/null 2>&1; then
        echo "ERROR: SD card directory listing failed"
        return 1
    fi
    
    echo "SD card appears responsive."
    return 0
}

# Function to get files from SD card (with responsiveness check)
get_latest_session() {
    local gopro_dir="$1"
    
    echo "Finding GoPro files from today..."
    
    # Test if the SD card is responsive first
    if ! test_sd_card_access "$gopro_dir"; then
        echo "SD card is not responding properly. Try:"
        echo "1. Ejecting and reinserting the SD card"
        echo "2. Checking if another process is accessing it"
        echo "3. Restarting your computer"
        return 1
    fi
    
    # Try to count files in the most basic way
    echo "Counting GoPro files..."
    local file_count=0
    
    # Change to the directory to avoid path issues
    cd "$gopro_dir" || return 1
    
    # Count files using a simple glob
    set -- GX??????.MP4
    if [ -f "$1" ]; then
        file_count=$#
    fi
    
    if [ "$file_count" -eq 0 ]; then
        echo "No GoPro files found."
        return 1
    fi
    
    echo "Found $file_count GoPro files."
    echo ""
    echo "Import all $file_count files from today? (Y/n): "
    read choice
    
    if [[ "$choice" == "n" ]] || [[ "$choice" == "N" ]]; then
        echo "Import cancelled."
        return 1
    fi
    
    # Return full paths to files
    for file in GX??????.MP4; do
        if [ -f "$file" ]; then
            echo "$gopro_dir/$file"
        fi
    done
    
    return 0
}

# Function to organize files by court
# Function to copy files to a single court directory (since each SD card = one court)
copy_selected_files() {
    local session_files=("$@")
    local dest_base="${session_files[-1]}"  # Last argument is destination
    unset session_files[-1]  # Remove destination from files array
    
    local court_dir="$dest_base/court_1"
    
    if [ "$DRY_RUN" = true ]; then
        echo "DEBUG: Would create court directory: $court_dir"
    else
        mkdir -p "$court_dir"
    fi
    
    echo "Copying selected files to court directory..."
    echo "Court 1:"
    
    for file in "${session_files[@]}"; do
        local filename=$(basename "$file")
        if [ "$DRY_RUN" = true ]; then
            echo "  DEBUG: Would copy $filename to $court_dir/"
        else
            echo "  Copying $filename..."
            cp "$file" "$court_dir/"
        fi
    done
    
    local file_count=${#session_files[@]}
    echo ""
    echo "✓ Copied $file_count files to $court_dir"
}

# Function to get suggested date from files (for user input)
get_suggested_date() {
    # Simply return the current date formatted as YYYY_MM_DD since we can't easily
    # access file dates without potentially hanging
    date "+%Y_%m_%d"
}

# Main script
main() {
    echo "=== GoPro SD Card Import Script ==="
    echo ""
    
    # Show usage if help requested
    if [[ "$1" == "-h" ]] || [[ "$1" == "--help" ]]; then
        show_usage
        exit 0
    fi
    
    # Detect SD cards
    echo "Scanning for SD cards..."
    sd_cards=()
    while IFS= read -r card; do
        [ -n "$card" ] && sd_cards+=("$card")
    done < <(detect_sd_cards)
    
    if [ ${#sd_cards[@]} -eq 0 ]; then
        echo "No SD cards with GoPro files detected."
        echo "Make sure your SD card is inserted and mounted."
        exit 1
    fi
    
    # If multiple SD cards, let user choose
    if [ ${#sd_cards[@]} -gt 1 ]; then
        echo ""
        echo "Multiple SD cards detected:"
        for i in "${!sd_cards[@]}"; do
            volume_name=$(basename "${sd_cards[$i]}")
            gopro_dir="${sd_cards[$i]}/DCIM/100GOPRO"
            gopro_count=$(find "$gopro_dir" -name "$GOPRO_PATTERN" 2>/dev/null | wc -l | tr -d ' ')
            echo "$((i+1)). $volume_name ($gopro_count files)"
        done
        echo -n "Select SD card (1-${#sd_cards[@]}): "
        read choice
        selected_sd="${sd_cards[$((choice-1))]}"
    else
        selected_sd="${sd_cards[0]}"
    fi
    
    volume_name=$(basename "$selected_sd")
    gopro_dir="$selected_sd/DCIM/100GOPRO"
    
    echo ""
    echo "Selected: $volume_name"
    echo "Scanning: $gopro_dir"
    
    # Create a temp file for session files
    session_files_temp="/tmp/session_files_$$"
    
    # Get the latest recording session
    if ! get_latest_session "$gopro_dir" > "$session_files_temp"; then
        echo "No files selected for import."
        rm -f "$session_files_temp"
        exit 1
    fi
    
    # Read files from temp file into array
    session_files=()
    while IFS= read -r line; do
        [ -n "$line" ] && session_files+=("$line")
    done < "$session_files_temp"
    rm -f "$session_files_temp"
    
    echo ""
    echo "Ready to import ${#session_files[@]} files from selected session."
    
    # Get suggested date from selected files
    suggested_date=$(get_suggested_date "${session_files[@]}")
    
    # Get date and event name
    read date_id event_name <<< $(get_user_input "$1" "$2" "$suggested_date")
    
    # Create destination directory
    dest_base="$MOVIES_DIR/bdl_${event_name}_${date_id}"
    
    if [ "$DRY_RUN" = true ]; then
        echo ""
        echo "DEBUG: Would create base directory: $dest_base"
    fi
    
    if [ -d "$dest_base" ]; then
        echo ""
        echo "Warning: Directory $dest_base already exists."
        if [ "$DRY_RUN" = true ]; then
            echo "DEBUG: In dry-run mode, would ask for confirmation"
        else
            echo -n "Continue anyway? (y/N): "
            read confirm
            if [[ "$confirm" != "y" ]] && [[ "$confirm" != "Y" ]]; then
                echo "Import cancelled."
                exit 1
            fi
        fi
    fi
    
    # Since each SD card is one court, create a single court directory
    echo ""
    echo "Each SD card represents one court."
    echo "Creating court_1 directory for this SD card's files..."
    
    copy_selected_files "${session_files[@]}" "$dest_base"
    
    echo ""
    if [ "$DRY_RUN" = true ]; then
        echo "=== DRY RUN COMPLETE ==="
        echo "Would import files to: $dest_base"
        echo "Total files that would be copied: ${#session_files[@]}"
        echo ""
        echo "To actually perform the import, run without --dry-run:"
        echo "./import_gopro_videos.sh '$date_id' '$event_name'"
    else
        echo "=== Import Complete ==="
        echo "Files imported to: $dest_base"
        echo "Total files copied: ${#session_files[@]}"
        echo ""
        echo "Next steps:"
        echo "1. Review the imported files"
        echo "2. Run process_league_night.sh to merge videos"
        echo "3. Example: ./process_league_night.sh '$dest_base' '${date_id}'"
    fi
}

# Run main function with all arguments
main "$@"
