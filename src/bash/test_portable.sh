#!/bin/bash

# Test script for the portable processing system
# This script runs basic tests to verify the setup works correctly

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[TEST]${NC} $1"; }
log_pass() { echo -e "${GREEN}[PASS]${NC} $1"; }
log_fail() { echo -e "${RED}[FAIL]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

# Test counter
TESTS_RUN=0
TESTS_PASSED=0

run_test() {
    local test_name="$1"
    local test_command="$2"
    
    ((TESTS_RUN++))
    log_info "Testing: $test_name"
    
    if eval "$test_command"; then
        log_pass "$test_name"
        ((TESTS_PASSED++))
        return 0
    else
        log_fail "$test_name"
        return 1
    fi
}

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo "=============================================="
echo "    Portable Processing System Tests"
echo "=============================================="
echo ""

# Test 1: Check if all required scripts exist
run_test "Required scripts exist" "
    [[ -f '$SCRIPT_DIR/portable_setup.sh' ]] &&
    [[ -f '$SCRIPT_DIR/portable_helper.sh' ]] &&
    [[ -f '$SCRIPT_DIR/portable_interactive_processor.sh' ]]
"

# Test 2: Scripts are executable
run_test "Scripts are executable" "
    [[ -x '$SCRIPT_DIR/portable_setup.sh' ]] &&
    [[ -x '$SCRIPT_DIR/portable_helper.sh' ]] &&
    [[ -x '$SCRIPT_DIR/portable_interactive_processor.sh' ]]
"

# Test 3: Scripts have valid shebang
run_test "Scripts have valid shebang" "
    head -1 '$SCRIPT_DIR/portable_setup.sh' | grep -q '^#!/bin/bash' &&
    head -1 '$SCRIPT_DIR/portable_helper.sh' | grep -q '^#!/bin/bash' &&
    head -1 '$SCRIPT_DIR/portable_interactive_processor.sh' | grep -q '^#!/bin/bash'
"

# Test 4: Check system dependencies
run_test "System has required dependencies" "
    command -v ffmpeg >/dev/null 2>&1 &&
    command -v jq >/dev/null 2>&1
"

# Test 5: Helper script responds to commands
run_test "Helper script responds to --help" "
    '$SCRIPT_DIR/portable_helper.sh' help >/dev/null 2>&1
"

# Test 6: Setup script responds to --help
run_test "Setup script responds to --help" "
    '$SCRIPT_DIR/portable_setup.sh' --help >/dev/null 2>&1
"

# Test 7: Check if documentation exists
run_test "Documentation exists" "
    [[ -f '$SCRIPT_DIR/../../PORTABLE_README.md' ]]
"

# Test 8: Scan for available volumes (informational)
scan_volumes() {
    log_info "Scanning for available volumes..."
    if [[ -d "/Volumes" ]]; then
        local volume_count=0
        local regular_cards=0
        local gopro_cards=0
        
        for volume in /Volumes/*; do
            if [[ -d "$volume" ]]; then
                ((volume_count++))
                local volume_name=$(basename "$volume")
                
                if [[ -d "$volume/DCIM/100GOPRO" ]]; then
                    ((gopro_cards++))
                    log_info "  📹 GoPro card: $volume_name"
                elif [[ -w "$volume" ]]; then
                    ((regular_cards++))
                    log_info "  💾 Writable volume: $volume_name"
                else
                    log_info "  📂 Volume: $volume_name (read-only)"
                fi
            fi
        done
        
        log_info "Volume summary: $volume_count total, $regular_cards writable, $gopro_cards GoPro"
        
        if [[ $regular_cards -gt 0 ]]; then
            log_pass "Found writable volumes for processing hub setup"
            ((TESTS_PASSED++))
        else
            log_warn "No writable volumes found - insert an SD card to test setup"
        fi
        ((TESTS_RUN++))
    else
        log_warn "/Volumes directory not found (not on macOS?)"
    fi
}

scan_volumes

# Summary
echo ""
echo "=============================================="
echo "    Test Results"
echo "=============================================="
echo ""

if [[ $TESTS_PASSED -eq $TESTS_RUN ]]; then
    log_pass "All tests passed! ($TESTS_PASSED/$TESTS_RUN)"
    echo ""
    echo "✅ The portable processing system is ready to use!"
    echo ""
    echo "Next steps:"
    echo "  1. Insert a regular SD card"
    echo "  2. Run: $SCRIPT_DIR/portable_helper.sh setup"
    echo "  3. Insert a GoPro micro SD card"
    echo "  4. Run: $SCRIPT_DIR/portable_helper.sh test"
    echo ""
else
    log_fail "Some tests failed ($TESTS_PASSED/$TESTS_RUN passed)"
    echo ""
    echo "❌ Please fix the failing tests before using the system."
    echo ""
    
    if ! command -v ffmpeg >/dev/null 2>&1; then
        echo "Missing ffmpeg - install with: brew install ffmpeg (macOS)"
    fi
    
    if ! command -v jq >/dev/null 2>&1; then
        echo "Missing jq - install with: brew install jq (macOS)"
    fi
    
    exit 1
fi
