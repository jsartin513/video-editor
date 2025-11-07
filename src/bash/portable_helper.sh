#!/bin/bash

# Quick Setup and Test Script for Portable Video Processing
# This script helps you set up and test the portable SD card processing system

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

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Show usage
show_usage() {
    cat << EOF
Quick Setup and Test for Portable Video Processing

This script helps you set up and test the dual SD card video processing system:
- Regular SD card becomes the "processing hub"
- Micro SD card contains GoPro footage
- Processing happens entirely on the regular SD card

Usage: $0 COMMAND [OPTIONS]

Commands:
    setup                   Set up a regular SD card as processing hub
    test                    Test the portable processing system
    list-cards              Show all available SD cards
    help                    Show this help

Examples:
    $0 setup                # Auto-detect and set up processing hub
    $0 test                 # Test processing with detected cards
    $0 list-cards           # Show all SD cards

EOF
}

# List all available SD cards
list_sd_cards() {
    log_info "Scanning for SD cards..."
    
    local regular_cards=()
    local gopro_cards=()
    
    for volume in /Volumes/*; do
        if [[ -d "$volume" && -w "$volume" ]]; then
            local volume_name=$(basename "$volume")
            local free_space_kb=$(df "$volume" | tail -1 | awk '{print $4}')
            local free_space_gb=$((free_space_kb / 1024 / 1024))
            
            # Check if it's a GoPro card
            if [[ -d "$volume/DCIM/100GOPRO" ]]; then
                local gopro_count=$(find "$volume/DCIM/100GOPRO" -name "*.MP4" 2>/dev/null | wc -l | tr -d ' ')
                gopro_cards+=("$volume_name")
                echo "📹 GoPro Card: $volume_name ($gopro_count MP4 files)"
            else
                # Check if it's already a processing hub
                if [[ -f "$volume/processing_scripts/run_portable.sh" ]]; then
                    echo "⚙️  Processing Hub: $volume_name (${free_space_gb}GB available)"
                else
                    regular_cards+=("$volume_name")
                    echo "💾 Regular SD Card: $volume_name (${free_space_gb}GB available)"
                fi
            fi
        fi
    done
    
    echo ""
    log_info "Summary:"
    echo "  Regular SD cards: ${#regular_cards[@]}"
    echo "  GoPro cards: ${#gopro_cards[@]}"
    echo "  Processing hubs: $(find /Volumes/*/processing_scripts/run_portable.sh 2>/dev/null | wc -l | tr -d ' ')"
}

# Set up processing hub
setup_processing_hub() {
    log_info "Setting up portable processing hub..."
    
    # Check if setup script exists
    local setup_script="$SCRIPT_DIR/portable_setup.sh"
    if [[ ! -f "$setup_script" ]]; then
        log_error "Setup script not found: $setup_script"
        log_info "Make sure you're running this from the correct directory"
        return 1
    fi
    
    # Make sure it's executable
    chmod +x "$setup_script"
    
    # Run the setup script
    "$setup_script" "$@"
}

# Test the portable system
test_portable_system() {
    log_info "Testing portable processing system..."
    
    # Find processing hubs
    local hubs=()
    for volume in /Volumes/*; do
        if [[ -f "$volume/processing_scripts/run_portable.sh" ]]; then
            hubs+=("$volume")
        fi
    done
    
    # Find GoPro cards
    local gopro_cards=()
    for volume in /Volumes/*; do
        if [[ -d "$volume/DCIM/100GOPRO" ]]; then
            local gopro_count=$(find "$volume/DCIM/100GOPRO" -name "*.MP4" 2>/dev/null | wc -l | tr -d ' ')
            if [[ $gopro_count -gt 0 ]]; then
                gopro_cards+=("$volume")
            fi
        fi
    done
    
    # Report findings
    echo ""
    log_info "System check:"
    echo "  Processing hubs found: ${#hubs[@]}"
    echo "  GoPro cards found: ${#gopro_cards[@]}"
    
    if [[ ${#hubs[@]} -eq 0 ]]; then
        log_error "No processing hubs found!"
        log_info "Run '$0 setup' to create a processing hub"
        return 1
    fi
    
    if [[ ${#gopro_cards[@]} -eq 0 ]]; then
        log_error "No GoPro cards found!"
        log_info "Insert a micro SD card with GoPro footage"
        return 1
    fi
    
    # Show what we found
    echo ""
    log_success "Ready to process!"
    
    for hub in "${hubs[@]}"; do
        log_info "Processing hub: $(basename "$hub")"
    done
    
    for card in "${gopro_cards[@]}"; do
        local count=$(find "$card/DCIM/100GOPRO" -name "*.MP4" 2>/dev/null | wc -l | tr -d ' ')
        log_info "GoPro card: $(basename "$card") ($count files)"
    done
    
    # Ask if user wants to start processing
    echo ""
    read -p "Start processing now? (y/N): " start_processing
    if [[ "$start_processing" == "y" || "$start_processing" == "Y" ]]; then
        local hub="${hubs[0]}"
        log_info "Starting processing with hub: $(basename "$hub")"
        "$hub/processing_scripts/run_portable.sh"
    else
        log_info "To start processing later, run:"
        for hub in "${hubs[@]}"; do
            echo "  $hub/processing_scripts/run_portable.sh"
        done
    fi
}

# Check dependencies
check_dependencies() {
    log_info "Checking system dependencies..."
    
    local missing_deps=()
    local required_deps=("ffmpeg" "jq")
    
    for dep in "${required_deps[@]}"; do
        if ! command -v "$dep" >/dev/null 2>&1; then
            missing_deps+=("$dep")
        else
            log_success "  ✓ $dep found"
        fi
    done
    
    if [[ ${#missing_deps[@]} -gt 0 ]]; then
        log_error "Missing dependencies: ${missing_deps[*]}"
        log_info "Install them with:"
        log_info "  macOS: brew install ${missing_deps[*]}"
        log_info "  Linux: sudo apt install ${missing_deps[*]}"
        return 1
    fi
    
    log_success "All dependencies found"
    return 0
}

# Main function
main() {
    case "${1:-help}" in
        setup)
            shift
            check_dependencies && setup_processing_hub "$@"
            ;;
        test)
            check_dependencies && test_portable_system
            ;;
        list-cards)
            list_sd_cards
            ;;
        help|--help|-h)
            show_usage
            ;;
        *)
            log_error "Unknown command: $1"
            echo ""
            show_usage
            exit 1
            ;;
    esac
}

# Show banner
echo ""
echo "=============================================="
echo "    Portable Video Processing Quick Setup"
echo "=============================================="
echo ""

# Run main function
main "$@"
