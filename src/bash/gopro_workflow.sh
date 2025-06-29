#!/bin/bash

# GoPro Video Processing Workflow
# Automates the entire process from raw GoPro videos to split game videos

set -e  # Exit on any error

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/gopro_config.conf"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Load configuration
load_config() {
    if [[ -f "$CONFIG_FILE" ]]; then
        source "$CONFIG_FILE"
        log_info "Loaded configuration from $CONFIG_FILE"
    else
        log_warning "No configuration file found. Using defaults."
        # Set defaults
        DEFAULT_TOURNAMENT_NAME="Tournament"
        DEFAULT_COURT_NAME="Court"
        DEFAULT_ROUND_NAME="Round"
    fi
}

# Create configuration file if it doesn't exist
create_config() {
    if [[ ! -f "$CONFIG_FILE" ]]; then
        cat > "$CONFIG_FILE" << EOF
# GoPro Workflow Configuration
DEFAULT_TOURNAMENT_NAME="Tournament"
DEFAULT_COURT_NAME="Court"  
DEFAULT_ROUND_NAME="Round"
AUTO_ADD_METADATA=true
CLEANUP_INTERMEDIATE_FILES=false
EOF
        log_success "Created configuration file: $CONFIG_FILE"
    fi
}

# Fix directory names by replacing spaces with underscores
fix_directory_names() {
    local input_dir="$1"
    local fixed=false
    
    log_info "Checking for spaces in directory names..."
    
    # Find directories with spaces and rename them
    find "$input_dir" -type d -name "* *" | while IFS= read -r dir; do
        new_dir="${dir// /_}"
        if [[ "$dir" != "$new_dir" ]]; then
            log_info "Renaming: '$dir' -> '$new_dir'"
            mv "$dir" "$new_dir"
            fixed=true
        fi
    done
    
    # Also fix filenames with spaces
    find "$input_dir" -type f -name "* *" | while IFS= read -r file; do
        dir=$(dirname "$file")
        filename=$(basename "$file")
        new_filename="${filename// /_}"
        if [[ "$filename" != "$new_filename" ]]; then
            log_info "Renaming file: '$filename' -> '$new_filename'"
            mv "$file" "$dir/$new_filename"
            fixed=true
        fi
    done
    
    if [[ "$fixed" == "true" ]]; then
        log_success "Fixed directory and file names"
    else
        log_info "No spaces found in names"
    fi
}

# Interactive JSONL creation
create_games_jsonl() {
    local jsonl_file="$1"
    local temp_file=$(mktemp)
    
    log_info "Creating games JSONL file: $jsonl_file"
    echo "Enter game information (press Enter with empty team name to finish):"
    
    while true; do
        echo
        read -p "Home team: " home_team
        [[ -z "$home_team" ]] && break
        
        read -p "Away team: " away_team
        [[ -z "$away_team" ]] && break
        
        read -p "Start time (HH:MM): " start_time
        while [[ ! "$start_time" =~ ^[0-9]{2}:[0-9]{2}$ ]]; do
            read -p "Invalid format. Start time (HH:MM): " start_time
        done
        
        read -p "Duration in minutes [60]: " minutes
        minutes=${minutes:-60}
        
        # Create JSON entry
        echo "{\"home_team\":\"$home_team\",\"away_team\":\"$away_team\",\"start_time\":\"$start_time\",\"minutes\":$minutes}" >> "$temp_file"
        
        log_success "Added game: $home_team vs $away_team"
    done
    
    if [[ -s "$temp_file" ]]; then
        mv "$temp_file" "$jsonl_file"
        log_success "Games JSONL file created: $jsonl_file"
    else
        rm "$temp_file"
        log_warning "No games added"
        return 1
    fi
}

# Load games from existing JSONL or create new one
prepare_games_jsonl() {
    local video_dir="$1"
    local jsonl_file="$video_dir/games.jsonl"
    
    if [[ -f "$jsonl_file" ]]; then
        read -p "Games JSONL file exists. Use existing? (y/n) [y]: " use_existing
        use_existing=${use_existing:-y}
        
        if [[ "$use_existing" =~ ^[Yy] ]]; then
            log_info "Using existing games file: $jsonl_file"
            return 0
        fi
    fi
    
    create_games_jsonl "$jsonl_file"
}

# Add metadata to video files
add_video_metadata() {
    local split_dir="$1"
    local tournament_name="$2"
    local court_name="$3"
    local round_name="$4"
    
    if [[ "$AUTO_ADD_METADATA" != "true" ]]; then
        return 0
    fi
    
    log_info "Adding metadata to video files..."
    
    for video_file in "$split_dir"/*.mp4; do
        [[ -f "$video_file" ]] || continue
        
        local file_base=$(basename "$video_file" .mp4)
        local temp_file="${video_file%.mp4}_temp.mp4"
        
        # Extract team names from filename
        local teams=$(echo "$file_base" | sed 's/_vs_/ vs /')
        
        log_info "Adding metadata to: $file_base"
        
        ffmpeg -hide_banner -loglevel error -i "$video_file" \
            -metadata title="$teams - $tournament_name $round_name" \
            -metadata description="$tournament_name - $round_name - $court_name" \
            -metadata comment="Generated by GoPro Workflow" \
            -c copy "$temp_file"
        
        mv "$temp_file" "$video_file"
    done
    
    log_success "Added metadata to all videos"
}

# Rename video files with tournament/round/court information
rename_video_files() {
    local split_dir="$1"
    local tournament_name="$2"
    local court_name="$3"
    local jsonl_file="$4"
    local start_round="$5"
    
    log_info "Renaming video files with tournament information..."
    
    local count=0
    local current_round="$start_round"
    
    for video_file in "$split_dir"/*.mp4; do
        [[ -f "$video_file" ]] || continue
        
        local original_name=$(basename "$video_file")
        local base_name="${original_name%.*}"
        local extension="${original_name##*.}"
        
        # Try to extract round from JSONL file based on team names
        local round_from_jsonl=""
        if [[ -f "$jsonl_file" ]]; then
            # Extract team names from filename (assuming format: Team1_vs_Team2.mp4)
            local team1=$(echo "$base_name" | sed 's/_vs_.*//')
            local team2=$(echo "$base_name" | sed 's/.*_vs_//')
            
            # Look for round information in JSONL
            round_from_jsonl=$(jq -r --arg team1 "$team1" --arg team2 "$team2" \
                'select(.home_team == $team1 and .away_team == $team2) | .round // empty' \
                "$jsonl_file" 2>/dev/null || echo "")
            
            # If not found, try the reverse (away vs home)
            if [[ -z "$round_from_jsonl" ]]; then
                round_from_jsonl=$(jq -r --arg team1 "$team2" --arg team2 "$team1" \
                    'select(.home_team == $team1 and .away_team == $team2) | .round // empty' \
                    "$jsonl_file" 2>/dev/null || echo "")
            fi
        fi
        
        # Use round from JSONL if available, otherwise use incremental round
        local round_name=""
        if [[ -n "$round_from_jsonl" ]]; then
            round_name="$round_from_jsonl"
        else
            round_name="Game_$current_round"
            ((current_round++))
        fi
        
        local new_name=""
        
        # Build new name: Tournament_Round_Court_OriginalName.ext
        if [[ -n "$tournament_name" ]]; then
            new_name="${tournament_name}"
        fi
        
        if [[ -n "$round_name" ]]; then
            [[ -n "$new_name" ]] && new_name="${new_name}_"
            new_name="${new_name}${round_name}"
        fi
        
        if [[ -n "$court_name" ]]; then
            [[ -n "$new_name" ]] && new_name="${new_name}_"
            new_name="${new_name}${court_name}"
        fi
        
        # Add original name
        [[ -n "$new_name" ]] && new_name="${new_name}_"
        new_name="${new_name}${base_name}.${extension}"
        
        # Skip if no change needed
        if [[ "$original_name" == "$new_name" ]]; then
            continue
        fi
        
        local new_path="$split_dir/$new_name"
        
        # Skip if target file already exists
        if [[ -f "$new_path" ]]; then
            log_warning "Target file already exists: $new_name"
            continue
        fi
        
        log_info "Renaming: $original_name -> $new_name"
        mv "$video_file" "$new_path"
        ((count++))
    done
    
    if [[ $count -gt 0 ]]; then
        log_success "Renamed $count video files"
    else
        log_info "No files needed renaming"
    fi
}

# Main workflow function
run_workflow() {
    local video_dir="$1"
    
    # Validate input directory
    if [[ ! -d "$video_dir" ]]; then
        log_error "Directory not found: $video_dir"
        exit 1
    fi
    
    log_info "Starting GoPro video processing workflow"
    log_info "Input directory: $video_dir"
    
    # Step 1: Fix directory names
    fix_directory_names "$video_dir"
    
    # Step 2: Prepare games JSONL
    prepare_games_jsonl "$video_dir"
    local jsonl_file="$video_dir/games.jsonl"
    
    if [[ ! -f "$jsonl_file" ]]; then
        log_error "Games JSONL file not found. Cannot proceed."
        exit 1
    fi
    
    # Step 3: Combine GoPro videos
    log_info "Combining GoPro videos..."
    "$SCRIPT_DIR/combine_gopro_videos.sh" "$video_dir"
    
    if [[ $? -ne 0 ]]; then
        log_error "Failed to combine GoPro videos"
        exit 1
    fi
    
    log_success "GoPro videos combined successfully"
    
    # Step 4: Split videos based on games
    local merged_dir="$video_dir/merged_videos"
    local split_dir="$video_dir/split_videos"
    
    log_info "Splitting videos into individual games..."
    
    # Process each merged video
    for merged_video in "$merged_dir"/*.MP4; do
        [[ -f "$merged_video" ]] || continue
        
        log_info "Processing: $(basename "$merged_video")"
        "$SCRIPT_DIR/split_game_videos.sh" "$merged_video" "$jsonl_file"
        
        if [[ $? -ne 0 ]]; then
            log_error "Failed to split video: $merged_video"
            exit 1
        fi
    done
    
    log_success "Videos split successfully"
    
    # Step 5: Add metadata and rename files
    local should_add_info="$AUTO_RENAME_FILES"
    if [[ "$should_add_info" != "true" ]]; then
        read -p "Add tournament/round/court information to videos? (y/n) [y]: " add_info
        add_info=${add_info:-y}
        should_add_info="$add_info"
    fi
    
    if [[ "$should_add_info" =~ ^[Yy]|^true$ ]]; then
        read -p "Tournament name [$DEFAULT_TOURNAMENT_NAME]: " tournament_name
        tournament_name=${tournament_name:-$DEFAULT_TOURNAMENT_NAME}
        
        read -p "Court name [$DEFAULT_COURT_NAME]: " court_name
        court_name=${court_name:-$DEFAULT_COURT_NAME}
        
        # Ask for starting round number only if rounds aren't in JSONL
        local has_rounds_in_jsonl=false
        if [[ -f "$jsonl_file" ]] && jq -e '.[0].round' "$jsonl_file" >/dev/null 2>&1; then
            has_rounds_in_jsonl=true
            log_info "Using round information from games JSONL file"
        else
            read -p "Starting round number [1]: " start_round
            start_round=${start_round:-1}
            log_info "Using incremental round numbering starting from $start_round"
        fi
        
        # Rename files first (before adding metadata to avoid file not found issues)
        rename_video_files "$split_dir" "$tournament_name" "$court_name" "$jsonl_file" "${start_round:-1}"
        
        # Add metadata to renamed files (we'll extract round info from the new filenames)
        add_video_metadata "$split_dir" "$tournament_name" "$court_name" "Round"
    fi
    
    # Step 6: Cleanup (optional)
    if [[ "$CLEANUP_INTERMEDIATE_FILES" == "true" ]]; then
        log_info "Cleaning up intermediate files..."
        # Add cleanup logic here if needed
    fi
    
    log_success "Workflow completed successfully!"
    log_info "Final videos are in: $split_dir"
}

# Usage information
show_usage() {
    cat << EOF
Usage: $0 [OPTIONS] <video_directory>

GoPro Video Processing Workflow

This script automates the entire process of:
1. Fixing directory names (removing spaces)
2. Creating/using games JSONL file
3. Combining GoPro video segments
4. Splitting combined videos into individual games
5. Renaming videos with tournament/round/court information
6. Adding metadata (tournament, round, court info)

OPTIONS:
    -h, --help      Show this help message
    -c, --config    Create/edit configuration file
    -d, --debug     Enable debug mode

EXAMPLES:
    $0 /path/to/gopro/videos
    $0 --config
    $0 --debug /path/to/videos

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_usage
            exit 0
            ;;
        -c|--config)
            create_config
            if command -v nano >/dev/null; then
                nano "$CONFIG_FILE"
            elif command -v vim >/dev/null; then
                vim "$CONFIG_FILE"
            else
                log_info "Edit the configuration file: $CONFIG_FILE"
                cat "$CONFIG_FILE"
            fi
            exit 0
            ;;
        -d|--debug)
            set -x
            shift
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

# Main execution
if [[ -z "$VIDEO_DIR" ]]; then
    show_usage
    exit 1
fi

# Load configuration and run workflow
load_config
create_config
run_workflow "$VIDEO_DIR"
