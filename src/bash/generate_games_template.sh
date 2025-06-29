#!/bin/bash

# Generate JSONL template for games
# This script creates a template JSONL file that can be edited

set -e

show_usage() {
    cat << EOF
Usage: $0 [OPTIONS] [output_file]

Generate a JSONL template for game scheduling

OPTIONS:
    -n, --num-games     Number of games to generate template for [5]
    -d, --duration      Default game duration in minutes [60]
    -s, --start-time    Starting time for first game [09:00]
    -i, --interval      Interval between games in minutes [90]
    -r, --start-round   Starting round number [1]
    --round-name        Round name pattern (e.g., "Game", "Match") [Game]
    -h, --help          Show this help

EXAMPLES:
    $0 games.jsonl
    $0 -n 8 -s 10:00 -i 75 tournament_games.jsonl
    $0 --num-games 6 --duration 45 --start-round 3
    $0 -r 1 --round-name "Match" games.jsonl

EOF
}

# Default values
NUM_GAMES=5
DURATION=60
START_TIME="09:00"
INTERVAL=90
START_ROUND=1
ROUND_NAME="Game"
OUTPUT_FILE="games_template.jsonl"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -n|--num-games)
            NUM_GAMES="$2"
            shift 2
            ;;
        -d|--duration)
            DURATION="$2"
            shift 2
            ;;
        -s|--start-time)
            START_TIME="$2"
            shift 2
            ;;
        -i|--interval)
            INTERVAL="$2"
            shift 2
            ;;
        -r|--start-round)
            START_ROUND="$2"
            shift 2
            ;;
        --round-name)
            ROUND_NAME="$2"
            shift 2
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        -*)
            echo "Unknown option: $1"
            show_usage
            exit 1
            ;;
        *)
            OUTPUT_FILE="$1"
            shift
            ;;
    esac
done

# Function to add minutes to time
add_minutes() {
    local time="$1"
    local minutes="$2"
    
    # Convert time to total minutes
    local hours=${time%:*}
    local mins=${time#*:}
    local total_minutes=$((hours * 60 + mins + minutes))
    
    # Convert back to HH:MM format
    local new_hours=$((total_minutes / 60))
    local new_mins=$((total_minutes % 60))
    
    printf "%02d:%02d" "$new_hours" "$new_mins"
}

echo "Generating JSONL template: $OUTPUT_FILE"

# Create the template
current_time="$START_TIME"
current_round=$START_ROUND
for ((i=1; i<=NUM_GAMES; i++)); do
    cat >> "$OUTPUT_FILE" << EOF
{"home_team":"Home_Team_$i","away_team":"Away_Team_$i","start_time":"$current_time","minutes":$DURATION,"round":"$ROUND_NAME $current_round"}
EOF
    current_time=$(add_minutes "$current_time" "$INTERVAL")
    ((current_round++))
done

echo "Generated template with $NUM_GAMES games starting at $START_TIME"
echo "Edit $OUTPUT_FILE to customize team names and times"
echo ""
echo "Example entries:"
cat "$OUTPUT_FILE" | head -3
