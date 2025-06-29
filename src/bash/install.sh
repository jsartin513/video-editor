#!/bin/bash

# GoPro Workflow Installation Script
# Installs all required dependencies and sets up the environment

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

# Detect OS
detect_os() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        OS="linux"
    elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
        OS="windows"
    else
        OS="unknown"
    fi
    echo "$OS"
}

# Check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Install on macOS using Homebrew
install_macos() {
    log_info "Installing dependencies for macOS..."
    
    # Check if Homebrew is installed
    if ! command_exists brew; then
        log_info "Installing Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi
    
    # Update Homebrew
    log_info "Updating Homebrew..."
    brew update
    
    # Install ffmpeg
    if ! command_exists ffmpeg; then
        log_info "Installing ffmpeg..."
        brew install ffmpeg
    else
        log_success "ffmpeg already installed"
    fi
    
    # Install jq for JSON processing
    if ! command_exists jq; then
        log_info "Installing jq..."
        brew install jq
    else
        log_success "jq already installed"
    fi
    
    # Install additional useful tools
    if ! command_exists mediainfo; then
        log_info "Installing mediainfo..."
        brew install mediainfo
    else
        log_success "mediainfo already installed"
    fi
}

# Install on Linux
install_linux() {
    log_info "Installing dependencies for Linux..."
    
    # Detect Linux distribution
    if [[ -f /etc/debian_version ]]; then
        # Debian/Ubuntu
        log_info "Detected Debian/Ubuntu system"
        
        # Update package list
        sudo apt update
        
        # Install ffmpeg
        if ! command_exists ffmpeg; then
            log_info "Installing ffmpeg..."
            sudo apt install -y ffmpeg
        else
            log_success "ffmpeg already installed"
        fi
        
        # Install jq
        if ! command_exists jq; then
            log_info "Installing jq..."
            sudo apt install -y jq
        else
            log_success "jq already installed"
        fi
        
        # Install mediainfo
        if ! command_exists mediainfo; then
            log_info "Installing mediainfo..."
            sudo apt install -y mediainfo
        else
            log_success "mediainfo already installed"
        fi
        
    elif [[ -f /etc/redhat-release ]]; then
        # Red Hat/CentOS/Fedora
        log_info "Detected Red Hat/CentOS/Fedora system"
        
        # Install ffmpeg (may require EPEL repository)
        if ! command_exists ffmpeg; then
            log_info "Installing ffmpeg..."
            if command_exists dnf; then
                sudo dnf install -y ffmpeg
            elif command_exists yum; then
                # Enable EPEL repository first
                sudo yum install -y epel-release
                sudo yum install -y ffmpeg
            fi
        else
            log_success "ffmpeg already installed"
        fi
        
        # Install jq
        if ! command_exists jq; then
            log_info "Installing jq..."
            if command_exists dnf; then
                sudo dnf install -y jq
            elif command_exists yum; then
                sudo yum install -y jq
            fi
        else
            log_success "jq already installed"
        fi
        
        # Install mediainfo
        if ! command_exists mediainfo; then
            log_info "Installing mediainfo..."
            if command_exists dnf; then
                sudo dnf install -y mediainfo
            elif command_exists yum; then
                sudo yum install -y mediainfo
            fi
        else
            log_success "mediainfo already installed"
        fi
        
    else
        log_warning "Unknown Linux distribution. Please install manually:"
        log_info "Required packages: ffmpeg, jq, mediainfo"
    fi
}

# Install on Windows (WSL or Git Bash)
install_windows() {
    log_info "Installing dependencies for Windows..."
    log_warning "For Windows, we recommend using WSL (Windows Subsystem for Linux)"
    
    if command_exists wsl; then
        log_info "WSL detected. Installing in WSL environment..."
        wsl bash -c "
            sudo apt update && 
            sudo apt install -y ffmpeg jq mediainfo
        "
    else
        log_error "Please install WSL or use a package manager like Chocolatey"
        log_info "Manual installation options:"
        log_info "1. Install WSL: https://docs.microsoft.com/en-us/windows/wsl/install"
        log_info "2. Install Chocolatey: https://chocolatey.org/install"
        log_info "3. Then run: choco install ffmpeg jq"
        exit 1
    fi
}

# Verify installation
verify_installation() {
    log_info "Verifying installation..."
    
    local all_good=true
    
    # Check ffmpeg
    if command_exists ffmpeg; then
        local ffmpeg_version=$(ffmpeg -version 2>&1 | head -n1 | cut -d' ' -f3)
        log_success "ffmpeg installed: $ffmpeg_version"
    else
        log_error "ffmpeg not found"
        all_good=false
    fi
    
    # Check ffprobe
    if command_exists ffprobe; then
        local ffprobe_version=$(ffprobe -version 2>&1 | head -n1 | cut -d' ' -f3)
        log_success "ffprobe installed: $ffprobe_version"
    else
        log_error "ffprobe not found"
        all_good=false
    fi
    
    # Check jq
    if command_exists jq; then
        local jq_version=$(jq --version)
        log_success "jq installed: $jq_version"
    else
        log_error "jq not found"
        all_good=false
    fi
    
    # Check mediainfo (optional but recommended)
    if command_exists mediainfo; then
        local mediainfo_version=$(mediainfo --version | head -n1)
        log_success "mediainfo installed: $mediainfo_version"
    else
        log_warning "mediainfo not found (optional)"
    fi
    
    if [[ "$all_good" == "true" ]]; then
        log_success "All required dependencies are installed!"
        return 0
    else
        log_error "Some dependencies are missing"
        return 1
    fi
}

# Setup workflow scripts
setup_scripts() {
    log_info "Setting up workflow scripts..."
    
    local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    
    # Make all scripts executable
    chmod +x "$script_dir"/*.sh
    log_success "Made all scripts executable"
    
    # Create config file if it doesn't exist
    if [[ ! -f "$script_dir/gopro_config.conf" ]]; then
        log_info "Creating default configuration file..."
        cat > "$script_dir/gopro_config.conf" << 'EOF'
# GoPro Workflow Configuration
DEFAULT_TOURNAMENT_NAME="Tournament"
DEFAULT_COURT_NAME="Court"  
DEFAULT_ROUND_NAME="Round"
AUTO_ADD_METADATA=true
AUTO_RENAME_FILES=true
CLEANUP_INTERMEDIATE_FILES=false
DEFAULT_GAME_DURATION=60
FFMPEG_QUALITY="copy"
GAME_FILE_PREFIX=""
GAME_FILE_SUFFIX=""
EOF
        log_success "Created configuration file"
    fi
    
    # Test workflow script
    if [[ -f "$script_dir/gopro_workflow.sh" ]]; then
        log_info "Testing workflow script..."
        if "$script_dir/gopro_workflow.sh" --help >/dev/null 2>&1; then
            log_success "Workflow script is working"
        else
            log_warning "Workflow script may have issues"
        fi
    fi
}

# Show usage information
show_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Install GoPro workflow dependencies and setup scripts

OPTIONS:
    --verify-only    Only verify existing installation
    --skip-setup     Skip script setup, only install dependencies
    -h, --help       Show this help

This script will install:
- ffmpeg (video processing)
- ffprobe (video metadata extraction)
- jq (JSON processing)
- mediainfo (optional, for detailed video info)

Supported platforms:
- macOS (using Homebrew)
- Linux (Debian/Ubuntu, Red Hat/CentOS/Fedora)
- Windows (via WSL)

EOF
}

# Parse command line arguments
VERIFY_ONLY=false
SKIP_SETUP=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --verify-only)
            VERIFY_ONLY=true
            shift
            ;;
        --skip-setup)
            SKIP_SETUP=true
            shift
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Main installation process
main() {
    log_info "GoPro Workflow Installation Script"
    log_info "=================================="
    
    # Detect operating system
    OS=$(detect_os)
    log_info "Detected OS: $OS"
    
    # If verify-only, just check installation
    if [[ "$VERIFY_ONLY" == "true" ]]; then
        verify_installation
        exit $?
    fi
    
    # Install dependencies based on OS
    case "$OS" in
        "macos")
            install_macos
            ;;
        "linux")
            install_linux
            ;;
        "windows")
            install_windows
            ;;
        *)
            log_error "Unsupported operating system: $OS"
            log_info "Please install manually: ffmpeg, jq, mediainfo"
            exit 1
            ;;
    esac
    
    # Verify installation
    if ! verify_installation; then
        log_error "Installation verification failed"
        exit 1
    fi
    
    # Setup scripts
    if [[ "$SKIP_SETUP" != "true" ]]; then
        setup_scripts
    fi
    
    log_success "Installation completed successfully!"
    log_info ""
    log_info "Next steps:"
    log_info "1. Copy your GoPro videos to a folder (no spaces in path)"
    log_info "2. Run: ./gopro_workflow.sh /path/to/your/videos"
    log_info "3. Or see README.md for detailed usage instructions"
}

# Run main function
main "$@"
