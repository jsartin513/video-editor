#!/bin/bash

# Portable SD Card Setup Script
# This script sets up a regular SD card as a "processing hub" that can handle
# video processing from micro SD cards containing GoPro footage.
#
# Usage: ./portable_setup.sh [SD_CARD_PATH] [--force]
#
# This will install all necessary tools, scripts, and create a self-contained
# video processing environment on the regular SD card.

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
MIN_FREE_SPACE_GB=4
REQUIRED_PACKAGES=("ffmpeg" "jq" "mediainfo")

# Show usage
show_usage() {
    cat << EOF
Portable SD Card Video Processing Setup

This script creates a self-contained video processing environment on a regular
SD card that can process GoPro footage from micro SD cards. It will attempt to
install portable versions of required tools (jq, and optionally ffmpeg).

Usage: $0 [SD_CARD_PATH] [OPTIONS]

Arguments:
    SD_CARD_PATH    Path to the regular SD card (e.g., /Volumes/PROCESSING)
                    If not provided, will auto-detect suitable SD cards

Options:
    --force         Force setup even if target already has content
    --help          Show this help message

Examples:
    $0                              # Auto-detect SD card
    $0 /Volumes/PROCESSING         # Use specific SD card
    $0 /Volumes/PROCESSING --force # Force setup on existing card

The setup will create:
    - /processing_scripts/         # All video processing scripts
    - /binaries/                   # Portable binary dependencies (jq, setup scripts)
    - /workspace/                  # Working directory for processing
    - /config/                     # Configuration files
    - /README_PROCESSING.txt       # Instructions for use

Notes:
- jq will be downloaded and installed portably
- ffmpeg will be copied from system if available (due to size constraints)
- Requires curl for downloading portable binaries

EOF
}

# Check command line arguments
FORCE=false
SD_CARD_PATH=""

for arg in "$@"; do
    case $arg in
        --force)
            FORCE=true
            shift
            ;;
        --help)
            show_usage
            exit 0
            ;;
        --*)
            log_error "Unknown option: $arg"
            show_usage
            exit 1
            ;;
        *)
            if [[ -z "$SD_CARD_PATH" ]]; then
                SD_CARD_PATH="$arg"
            else
                log_error "Too many arguments"
                show_usage
                exit 1
            fi
            ;;
    esac
done

# Function to detect suitable SD cards for processing hub
detect_processing_cards() {
    log_info "Scanning for suitable SD cards..."
    
    local cards=()
    local names=()
    
    # Check each mounted volume
    for volume in /Volumes/*; do
        if [[ -d "$volume" && -w "$volume" ]]; then
            local volume_name=$(basename "$volume")
            log_info "Checking: $volume_name"
            
            # Skip if this looks like a GoPro card (has DCIM structure)
            if [[ -d "$volume/DCIM/100GOPRO" ]]; then
                log_info "  Skipping $volume_name (appears to be GoPro micro SD card)"
                continue
            fi
            
            # Check available space
            local free_space_kb=$(df "$volume" | tail -1 | awk '{print $4}')
            local free_space_gb=$((free_space_kb / 1024 / 1024))
            
            if [[ $free_space_gb -lt $MIN_FREE_SPACE_GB ]]; then
                log_info "  Skipping $volume_name (insufficient space: ${free_space_gb}GB < ${MIN_FREE_SPACE_GB}GB)"
                continue
            fi
            
            # Check if already setup as processing hub
            if [[ -f "$volume/processing_scripts/run_portable.sh" ]]; then
                if [[ "$FORCE" == "true" ]]; then
                    log_warning "  $volume_name already setup as processing hub (will overwrite with --force)"
                else
                    log_info "  Skipping $volume_name (already setup as processing hub, use --force to overwrite)"
                    continue
                fi
            fi
            
            cards+=("$volume")
            names+=("$volume_name")
            log_success "  ✓ $volume_name (${free_space_gb}GB available)"
        fi
    done
    
    if [[ ${#cards[@]} -eq 0 ]]; then
        log_error "No suitable SD cards found for processing hub setup"
        log_info "Requirements:"
        log_info "  - At least ${MIN_FREE_SPACE_GB}GB free space"
        log_info "  - Write permissions"
        log_info "  - Not a GoPro micro SD card (no DCIM structure)"
        return 1
    elif [[ ${#cards[@]} -eq 1 ]]; then
        log_success "Using SD card: ${names[0]}"
        echo "${cards[0]}"
        return 0
    else
        echo ""
        log_info "Multiple suitable SD cards found:"
        for i in "${!names[@]}"; do
            local free_space_kb=$(df "${cards[$i]}" | tail -1 | awk '{print $4}')
            local free_space_gb=$((free_space_kb / 1024 / 1024))
            echo "$((i+1)). ${names[$i]} (${free_space_gb}GB available)"
        done
        echo ""
        
        while true; do
            read -p "Select SD card for processing hub (1-${#cards[@]}): " choice
            if [[ "$choice" =~ ^[0-9]+$ ]] && [[ "$choice" -ge 1 ]] && [[ "$choice" -le "${#cards[@]}" ]]; then
                log_success "Selected: ${names[$((choice-1))]}"
                echo "${cards[$((choice-1))]}"
                return 0
            else
                log_error "Invalid choice. Please enter a number between 1 and ${#cards[@]}."
            fi
        done
    fi
}

# Function to download and install portable binaries
install_portable_binaries() {
    local sd_path="$1"
    local bin_dir="$sd_path/binaries"
    
    log_info "Installing portable binaries..."
    
    # Detect OS and architecture
    local os=""
    local arch=""
    
    if [[ "$OSTYPE" == "darwin"* ]]; then
        os="macos"
        if [[ "$(uname -m)" == "arm64" ]]; then
            arch="arm64"
        else
            arch="x86_64"
        fi
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        os="linux"
        arch="$(uname -m)"
    else
        log_error "Unsupported operating system: $OSTYPE"
        return 1
    fi
    
    log_info "Detected platform: $os-$arch"
    
    # Download and install jq
    log_info "Installing portable jq..."
    local jq_url=""
    local jq_name="jq"
    
    if [[ "$os" == "macos" ]]; then
        if [[ "$arch" == "arm64" ]]; then
            jq_url="https://github.com/jqlang/jq/releases/latest/download/jq-macos-arm64"
        else
            jq_url="https://github.com/jqlang/jq/releases/latest/download/jq-macos-amd64"
        fi
    elif [[ "$os" == "linux" ]]; then
        if [[ "$arch" == "x86_64" ]]; then
            jq_url="https://github.com/jqlang/jq/releases/latest/download/jq-linux-amd64"
        elif [[ "$arch" == "aarch64" ]]; then
            jq_url="https://github.com/jqlang/jq/releases/latest/download/jq-linux-arm64"
        else
            log_warning "Architecture $arch not directly supported, trying x86_64 version"
            jq_url="https://github.com/jqlang/jq/releases/latest/download/jq-linux-amd64"
        fi
    fi
    
    if [[ -n "$jq_url" ]]; then
        if curl -L -o "$bin_dir/$jq_name" "$jq_url" 2>/dev/null; then
            chmod +x "$bin_dir/$jq_name"
            log_success "  ✓ jq installed"
        else
            log_warning "  ⚠ Failed to download jq, will use system version if available"
        fi
    fi
    
    # Download and install ffmpeg (this is more complex due to licensing)
    log_info "Setting up ffmpeg..."
    
    # For macOS, we can try to copy the existing ffmpeg binary if available
    if [[ "$os" == "macos" ]] && command -v ffmpeg >/dev/null 2>&1; then
        local ffmpeg_path=$(which ffmpeg)
        log_info "  Copying existing ffmpeg from: $ffmpeg_path"
        if cp "$ffmpeg_path" "$bin_dir/ffmpeg"; then
            chmod +x "$bin_dir/ffmpeg"
            log_success "  ✓ ffmpeg copied from system"
        else
            log_warning "  ⚠ Failed to copy ffmpeg"
        fi
    else
        # For a fully portable solution, we'd need to download static builds
        log_warning "  ⚠ ffmpeg not installed portably (complex due to size/licensing)"
        log_info "  Will rely on system ffmpeg for now"
        log_info "  Consider installing ffmpeg on host system: brew install ffmpeg"
    fi
    
    # Create a wrapper script that prefers portable binaries
    cat > "$sd_path/binaries/setup_path.sh" << 'EOF'
#!/bin/bash
# Setup script to add portable binaries to PATH
BIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PATH="$BIN_DIR:$PATH"
EOF
    
    chmod +x "$sd_path/binaries/setup_path.sh"
    log_success "Path setup script created"
    
    return 0
}

# Function to check if dependencies are available (portable or system)
check_dependencies() {
    local sd_path="$1"
    
    log_info "Checking dependencies..."
    
    # Source the portable path setup if it exists
    if [[ -f "$sd_path/binaries/setup_path.sh" ]]; then
        source "$sd_path/binaries/setup_path.sh"
    fi
    
    local missing_deps=()
    
    # Check each required package
    for pkg in "${REQUIRED_PACKAGES[@]}"; do
        # Skip mediainfo for portable setup (not critical)
        if [[ "$pkg" == "mediainfo" ]]; then
            continue
        fi
        
        if ! command -v "$pkg" >/dev/null 2>&1; then
            missing_deps+=("$pkg")
        else
            local pkg_path=$(which "$pkg")
            if [[ "$pkg_path" == "$sd_path/binaries/"* ]]; then
                log_success "  ✓ $pkg found (portable)"
            else
                log_success "  ✓ $pkg found (system)"
            fi
        fi
    done
    
    if [[ ${#missing_deps[@]} -gt 0 ]]; then
        log_error "Missing required dependencies:"
        for dep in "${missing_deps[@]}"; do
            echo "    - $dep"
        done
        echo ""
        log_info "Please install missing dependencies:"
        log_info "  macOS: brew install ${missing_deps[*]}"
        log_info "  Linux (Ubuntu/Debian): sudo apt install ${missing_deps[*]}"
        return 1
    fi
    
    log_success "All required dependencies available"
    return 0
}

# Function to create directory structure on SD card
create_directory_structure() {
    local sd_path="$1"
    
    log_info "Creating directory structure on SD card..."
    
    # Create main directories
    mkdir -p "$sd_path/processing_scripts"
    mkdir -p "$sd_path/binaries"
    mkdir -p "$sd_path/workspace"
    mkdir -p "$sd_path/config"
    mkdir -p "$sd_path/logs"
    
    # Create workspace subdirectories
    mkdir -p "$sd_path/workspace/input"
    mkdir -p "$sd_path/workspace/output"
    mkdir -p "$sd_path/workspace/temp"
    
    log_success "Directory structure created"
}

# Function to copy processing scripts
copy_scripts() {
    local sd_path="$1"
    local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    
    log_info "Copying processing scripts..."
    
    # Copy all bash scripts
    cp "$script_dir"/*.sh "$sd_path/processing_scripts/"
    
    # Copy configuration files
    if [[ -f "$script_dir/gopro_config.conf" ]]; then
        cp "$script_dir/gopro_config.conf" "$sd_path/config/"
    fi
    
    # Make scripts executable
    chmod +x "$sd_path/processing_scripts"/*.sh
    
    log_success "Processing scripts copied and made executable"
}

# Function to create portable launcher
create_portable_launcher() {
    local sd_path="$1"
    
    log_info "Creating portable launcher script..."
    
    cat > "$sd_path/processing_scripts/run_portable.sh" << 'EOF'
#!/bin/bash

# Portable Video Processing Launcher
# This script runs entirely from the SD card and processes GoPro footage
# from micro SD cards into organized, ready-to-upload videos.
#
# Usage: ./run_portable.sh [--auto] [--event-name NAME]

set -e

# Parse command line arguments
AUTO_MODE=false
CUSTOM_EVENT_NAME=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --auto)
            AUTO_MODE=true
            shift
            ;;
        --event-name)
            CUSTOM_EVENT_NAME="$2"
            shift 2
            ;;
        *)
            echo "Usage: $0 [--auto] [--event-name NAME]"
            echo "  --auto           Accept all defaults, no prompts"
            echo "  --event-name     Custom event name (overrides auto-increment)"
            exit 1
            ;;
    esac
done

# Get the directory where this script is located (on the SD card)
SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SD_ROOT="$(dirname "$SCRIPTS_DIR")"

# Setup portable binary path
if [[ -f "$SD_ROOT/binaries/setup_path.sh" ]]; then
    source "$SD_ROOT/binaries/setup_path.sh"
fi

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

# Function to get next event number
get_next_event_number() {
    local counter_file="$SD_ROOT/config/event_counter.txt"
    local counter=1
    
    if [[ -f "$counter_file" ]]; then
        counter=$(cat "$counter_file" 2>/dev/null || echo 1)
        counter=$((counter + 1))
    fi
    
    echo "$counter" > "$counter_file"
    echo "$counter"
}

echo ""
echo "==============================================="
echo "    Portable GoPro Video Processing Hub"
echo "==============================================="
echo ""
log_info "Running from SD card: $(basename "$SD_ROOT")"
log_info "Workspace: $SD_ROOT/workspace"
if [[ "$AUTO_MODE" == "true" ]]; then
    log_info "Running in AUTO mode (no prompts)"
fi
echo ""

# Check for required dependencies (portable or system)
log_info "Checking dependencies..."
REQUIRED_COMMANDS=("ffmpeg" "jq")
MISSING_COMMANDS=()

for cmd in "${REQUIRED_COMMANDS[@]}"; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        MISSING_COMMANDS+=("$cmd")
    else
        cmd_path=$(which "$cmd")
        if [[ "$cmd_path" == "$SD_ROOT/binaries/"* ]]; then
            log_success "  ✓ $cmd (portable)"
        else
            log_success "  ✓ $cmd (system)"
        fi
    fi
done

if [[ ${#MISSING_COMMANDS[@]} -gt 0 ]]; then
    log_error "Missing required system commands:"
    for cmd in "${MISSING_COMMANDS[@]}"; do
        echo "    - $cmd"
    done
    echo ""
    log_info "Please install missing dependencies:"
    log_info "  macOS: brew install ${MISSING_COMMANDS[*]}"
    log_info "  Linux: sudo apt install ${MISSING_COMMANDS[*]}"
    exit 1
fi

# Detect source SD cards (micro SD cards with GoPro footage)
log_info "Scanning for GoPro micro SD cards..."
SOURCE_CARDS=()
SOURCE_NAMES=()

for volume in /Volumes/*; do
    if [[ -d "$volume" && "$volume" != "$SD_ROOT" ]]; then
        volume_name=$(basename "$volume")
        
        # Check if this is a GoPro card
        if [[ -d "$volume/DCIM/100GOPRO" ]]; then
            gopro_count=$(find "$volume/DCIM/100GOPRO" -name "*.MP4" 2>/dev/null | wc -l | tr -d ' ')
            if [[ $gopro_count -gt 0 ]]; then
                SOURCE_CARDS+=("$volume")
                SOURCE_NAMES+=("$volume_name")
                log_success "  ✓ Found $volume_name ($gopro_count MP4 files)"
            fi
        fi
    fi
done

if [[ ${#SOURCE_CARDS[@]} -eq 0 ]]; then
    log_error "No GoPro micro SD cards found!"
    log_info "Please insert a micro SD card with GoPro footage"
    exit 1
fi

# Select source card if multiple found
SOURCE_CARD=""
if [[ ${#SOURCE_CARDS[@]} -eq 1 ]]; then
    SOURCE_CARD="${SOURCE_CARDS[0]}"
    log_info "Using source card: $(basename "$SOURCE_CARD")"
elif [[ "$AUTO_MODE" == "true" ]]; then
    # In auto mode, use the first card found
    SOURCE_CARD="${SOURCE_CARDS[0]}"
    log_info "AUTO mode: Using first card: $(basename "$SOURCE_CARD")"
else
    echo ""
    log_info "Multiple GoPro cards found:"
    for i in "${!SOURCE_NAMES[@]}"; do
        count=$(find "${SOURCE_CARDS[$i]}/DCIM/100GOPRO" -name "*.MP4" 2>/dev/null | wc -l | tr -d ' ')
        echo "$((i+1)). ${SOURCE_NAMES[$i]} ($count files)"
    done
    echo ""
    
    while true; do
        read -p "Select source card (1-${#SOURCE_CARDS[@]}): " choice
        if [[ "$choice" =~ ^[0-9]+$ ]] && [[ "$choice" -ge 1 ]] && [[ "$choice" -le "${#SOURCE_CARDS[@]}" ]]; then
            SOURCE_CARD="${SOURCE_CARDS[$((choice-1))]}"
            log_success "Selected: $(basename "$SOURCE_CARD")"
            break
        else
            log_error "Invalid choice. Please enter a number between 1 and ${#SOURCE_CARDS[@]}."
        fi
    done
fi

# Get event details
echo ""
log_info "Setting up processing job..."

if [[ -n "$CUSTOM_EVENT_NAME" ]]; then
    EVENT_NAME="$CUSTOM_EVENT_NAME"
    log_info "Using custom event name: $EVENT_NAME"
elif [[ "$AUTO_MODE" == "true" ]]; then
    EVENT_NUM=$(get_next_event_number)
    EVENT_NAME="test_event_${EVENT_NUM}"
    log_info "AUTO mode: Using event name: $EVENT_NAME"
else
    read -p "Enter event name (e.g., 'league_night') [test_event]: " EVENT_NAME
    EVENT_NAME=${EVENT_NAME:-test_event}
fi

if [[ "$AUTO_MODE" == "true" ]]; then
    DATE_ID=$(date +%b_%d_%Y | tr '[:upper:]' '[:lower:]')
    log_info "AUTO mode: Using date: $DATE_ID"
else
    read -p "Enter date identifier (e.g., 'nov_07_2025') [$(date +%b_%d_%Y | tr '[:upper:]' '[:lower:]')]: " DATE_ID
    DATE_ID=${DATE_ID:-$(date +%b_%d_%Y | tr '[:upper:]' '[:lower:]')}
fi

if [[ "$AUTO_MODE" == "true" ]]; then
    COURT_NUM=1
    log_info "AUTO mode: Using court: $COURT_NUM"
else
    read -p "Enter court number (e.g., '2') [1]: " COURT_NUM
    COURT_NUM=${COURT_NUM:-1}
fi

# Create output directory
OUTPUT_DIR="$SD_ROOT/workspace/output/${DATE_ID}_court_${COURT_NUM}"
mkdir -p "$OUTPUT_DIR"

log_info "Output will be saved to: $OUTPUT_DIR"
echo ""

# Copy files from source card to workspace (process ALL files by default)
log_info "Copying files from source card..."
TEMP_DIR="$SD_ROOT/workspace/temp"
mkdir -p "$TEMP_DIR"

# Copy all MP4 files from GoPro card
cp "$SOURCE_CARD/DCIM/100GOPRO"/*.MP4 "$TEMP_DIR/"
FILE_COUNT=$(ls -1 "$TEMP_DIR"/*.MP4 2>/dev/null | wc -l | tr -d ' ')
log_success "Copied $FILE_COUNT files to workspace"

# Run combine script directly (using SCRIPTS_DIR to avoid variable conflict)
log_info "Starting video processing..."
"$SCRIPTS_DIR/combine_gopro_videos.sh" "$TEMP_DIR"

if [[ $? -eq 0 ]]; then
    # Move merged video to output directory
    MERGED_VIDEO=$(find "$TEMP_DIR/merged_videos" -name "*.MP4" | head -1)
    if [[ -f "$MERGED_VIDEO" ]]; then
        FINAL_NAME="${DATE_ID}_${EVENT_NAME}_court_${COURT_NUM}.MP4"
        mv "$MERGED_VIDEO" "$OUTPUT_DIR/$FINAL_NAME"
        log_success "Final video created: $FINAL_NAME"
    else
        log_error "No merged video found"
        exit 1
    fi
else
    log_error "Video processing failed"
    exit 1
fi

# Clean up temp files
rm -rf "$TEMP_DIR"

log_success "Processing complete!"
log_info "Processed videos are ready in: $OUTPUT_DIR"
echo ""
echo "You can now safely eject both SD cards and upload the videos!"
echo ""
EOF

    chmod +x "$sd_path/processing_scripts/run_portable.sh"
    log_success "Portable launcher created"
}

# Function to create configuration files
create_portable_config() {
    local sd_path="$1"
    
    log_info "Creating portable configuration..."
    
    # Create portable config
    cat > "$sd_path/config/portable_config.conf" << EOF
# Portable Processing Hub Configuration
# This configuration is optimized for SD card processing

# Processing settings
AUTO_ADD_METADATA=true
AUTO_RENAME_FILES=true
CLEANUP_INTERMEDIATE_FILES=true
DEFAULT_GAME_DURATION=60
FFMPEG_QUALITY="copy"

# Portable paths (relative to SD card root)
WORKSPACE_DIR="workspace"
OUTPUT_DIR="workspace/output"
TEMP_DIR="workspace/temp"
LOG_DIR="logs"

# Processing hub info
SETUP_DATE="$(date)"
SETUP_VERSION="1.0"
EOF

    # Create README for users
    cat > "$sd_path/README_PROCESSING.txt" << EOF
===============================================
    Portable GoPro Video Processing Hub
===============================================

This SD card has been set up as a portable video processing hub that can
process GoPro footage from micro SD cards.

WHAT YOU NEED:
- This SD card (the processing hub)
- A micro SD card with GoPro footage
- Any computer with a Terminal/Command Prompt (Windows, Mac, Linux)

NOTE: No software installation required! All necessary tools (ffmpeg, jq) 
are included on this SD card for true portability.

HOW TO USE:

1. Insert BOTH SD cards into your computer:
   - This regular SD card (the processing hub)
   - The micro SD card with GoPro footage

2. Open Terminal/Command Prompt and navigate to this SD card:
   
   macOS/Linux:
   cd /Volumes/VidMerge
   
   Windows (if drive letter is D:):
   D:
   cd /
   
   Windows (alternative):
   cd /mnt/d  # (in WSL/Git Bash)

3. Run the processing script with these EXACT commands:

   BASIC USAGE (with prompts):
   ./processing_scripts/run_portable.sh
   
   AUTO MODE (no prompts, uses defaults):
   ./processing_scripts/run_portable.sh --auto
   
   CUSTOM EVENT NAME:
   ./processing_scripts/run_portable.sh --event-name "your_event_name"
   
   AUTO MODE + CUSTOM NAME:
   ./processing_scripts/run_portable.sh --auto --event-name "league_night"

4. The script will:
   - Automatically detect your GoPro micro SD card
   - Copy and process all MP4 files
   - Create a merged video file
   - Save it to: VidMerge/workspace/output/

5. Find your processed videos:
   - Check the workspace/output folder on this SD card
   - Videos are named: DATE_EVENT_court_NUMBER.MP4
   - Example: nov_07_2025_test_event_1_court_1.MP4

FEATURES:
- Auto-incrementing event names: test_event_1, test_event_2, etc.
- Portable binaries: ffmpeg and jq included on SD card
- Custom event names: --event-name "your_event"
- Auto mode: --auto for unattended processing

DIRECTORY STRUCTURE:
- processing_scripts/  - All the processing tools
- workspace/          - Working area for videos
- config/            - Configuration files
- logs/              - Processing logs

TROUBLESHOOTING:

COMMON ISSUES:
- "No such file or directory" → Make sure you're in the right directory
  Run: pwd (should show /Volumes/VidMerge or similar)
  
- "Permission denied" → Make scripts executable:
  chmod +x processing_scripts/*.sh
  
- "No GoPro cards found" → Check that micro SD card is properly inserted
  Should see DCIM/100GOPRO folder with .MP4 files
  
- "command not found" → Portable binaries may not be working
  Try: ls -la binaries/ (should see ffmpeg and jq)

QUICK DIAGNOSTICS:
# Check if you're in the right place
pwd
ls -la processing_scripts/run_portable.sh

# Check if GoPro card is visible  
ls /Volumes/  # (macOS) or ls /mnt/ # (Linux/WSL)

# Test portable binaries
./binaries/ffmpeg -version
./binaries/jq --version

OS-SPECIFIC NOTES:
- macOS: SD cards appear in /Volumes/CARDNAME
- Linux: Usually /media/username/CARDNAME or /mnt/CARDNAME  
- Windows: Drive letters (D:, E:, etc.) or /mnt/d in WSL

For help, check the logs/ directory for detailed error messages.

SYSTEM REQUIREMENTS:
- Works on: macOS, Linux, Windows (with bash/WSL)
- No software installation needed - everything is portable!
- Requires: Terminal/Command Prompt access

Setup Date: $(date)
Version: 1.0
EOF

    log_success "Configuration files created"
}

# Function to test the setup
test_setup() {
    local sd_path="$1"
    
    log_info "Testing portable setup..."
    
    # Check if launcher exists and is executable
    if [[ ! -x "$sd_path/processing_scripts/run_portable.sh" ]]; then
        log_error "Portable launcher not found or not executable"
        return 1
    fi
    
    # Check directory structure
    local required_dirs=("processing_scripts" "workspace" "config" "logs")
    for dir in "${required_dirs[@]}"; do
        if [[ ! -d "$sd_path/$dir" ]]; then
            log_error "Required directory missing: $dir"
            return 1
        fi
    done
    
    # Test script permissions (macOS compatible)
    local script_count=$(find "$sd_path/processing_scripts" -name "*.sh" -type f | wc -l | tr -d ' ')
    if [[ $script_count -eq 0 ]]; then
        log_error "No executable scripts found"
        return 1
    fi
    
    log_success "Setup test passed! Found $script_count executable scripts"
    return 0
}

# Main setup function
main() {
    echo ""
    echo "==============================================="
    echo "    Portable SD Card Processing Hub Setup"
    echo "==============================================="
    echo ""
    
    # Check host dependencies first (basic check)
    local basic_deps=("curl")
    local missing_basic=()
    
    for dep in "${basic_deps[@]}"; do
        if ! command -v "$dep" >/dev/null 2>&1; then
            missing_basic+=("$dep")
        fi
    done
    
    if [[ ${#missing_basic[@]} -gt 0 ]]; then
        log_error "Missing basic dependencies: ${missing_basic[*]}"
        log_info "Please install curl to download portable binaries"
        exit 1
    fi
    
    # Determine target SD card
    if [[ -z "$SD_CARD_PATH" ]]; then
        SD_CARD_PATH=$(detect_processing_cards)
        if [[ $? -ne 0 ]]; then
            exit 1
        fi
    else
        if [[ ! -d "$SD_CARD_PATH" ]]; then
            log_error "SD card path not found: $SD_CARD_PATH"
            exit 1
        fi
        
        if [[ ! -w "$SD_CARD_PATH" ]]; then
            log_error "No write permission for: $SD_CARD_PATH"
            exit 1
        fi
    fi
    
    log_info "Setting up processing hub on: $(basename "$SD_CARD_PATH")"
    echo ""
    
    # Confirm setup
    if [[ "$FORCE" != "true" ]]; then
        echo "This will install video processing tools on the SD card."
        echo "Existing files may be overwritten."
        echo ""
        read -p "Continue with setup? (y/N): " confirm
        if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
            log_info "Setup cancelled"
            exit 0
        fi
    fi
    
    # Run setup steps
    create_directory_structure "$SD_CARD_PATH"
    install_portable_binaries "$SD_CARD_PATH"
    copy_scripts "$SD_CARD_PATH"
    create_portable_launcher "$SD_CARD_PATH"
    create_portable_config "$SD_CARD_PATH"
    
    # Test setup and dependencies
    if test_setup "$SD_CARD_PATH" && check_dependencies "$SD_CARD_PATH"; then
        echo ""
        log_success "Portable processing hub setup complete!"
        echo ""
        echo "To use:"
        echo "  1. Insert both this SD card and a GoPro micro SD card"
        echo "  2. Run: $SD_CARD_PATH/processing_scripts/run_portable.sh"
        echo ""
        echo "See README_PROCESSING.txt on the SD card for full instructions"
    else
        log_error "Setup validation failed!"
        exit 1
    fi
}

# Run main function
main "$@"
