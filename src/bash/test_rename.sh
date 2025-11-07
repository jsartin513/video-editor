#!/bin/bash

# Test script to run the rename function
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/gopro_workflow.sh"

# Run the rename function
rename_video_files "/Users/MrsHazmat/Movies/BDL_throwdown_4/court_1_all/split_videos" "BDL Throwdown 4" "Court 1" "/Users/MrsHazmat/Movies/BDL_throwdown_4/court_1_all/games.jsonl" "1"
echo "========================="

for video_file in "$split_dir"/*.mp4; do
    [[ -f "$video_file" ]] || continue
    
    original_name=$(basename "$video_file")
    base_name="${original_name%.*}"
    extension="${original_name##*.}"
    
    # Extract team names from filename (assuming format: Team1_vs_Team2.mp4)
    team1=$(echo "$base_name" | sed 's/_vs_.*//')
    team2=$(echo "$base_name" | sed 's/.*_vs_//')
    
    # Convert underscores to spaces for JSONL lookup
    team1_spaces=$(echo "$team1" | sed 's/_/ /g')
    team2_spaces=$(echo "$team2" | sed 's/_/ /g')
    
    # Look for round and type information in JSONL
    game_info=$(jq -r --arg team1 "$team1_spaces" --arg team2 "$team2_spaces" \
        'select(.home_team == $team1 and .away_team == $team2) | "\(.round // "")|\(.type // "")"' \
        "$jsonl_file" 2>/dev/null || echo "")
    
    # If not found, try the reverse (away vs home)
    if [[ -z "$game_info" ]]; then
        game_info=$(jq -r --arg team1 "$team2_spaces" --arg team2 "$team1_spaces" \
            'select(.home_team == $team1 and .away_team == $team2) | "\(.round // "")|\(.type // "")"' \
            "$jsonl_file" 2>/dev/null || echo "")
    fi
    
    if [[ -n "$game_info" ]]; then
        round_from_jsonl=$(echo "$game_info" | cut -d'|' -f1)
        type_from_jsonl=$(echo "$game_info" | cut -d'|' -f2)
    fi
    
    # Convert type to proper format (e.g., "round_robin" -> "Round Robin")
    formatted_type=""
    if [[ -n "$type_from_jsonl" ]]; then
        formatted_type=$(echo "$type_from_jsonl" | sed 's/_/ /g' | awk '{for(i=1;i<=NF;i++) $i=toupper(substr($i,1,1)) tolower(substr($i,2))}1')
    fi
    
    # Extract team names from original filename and format them properly
    team1_formatted=$(echo "$team1" | sed 's/_/ /g')
    team2_formatted=$(echo "$team2" | sed 's/_/ /g')
    teams="${team1_formatted} vs ${team2_formatted}"
    
    # Build the new name in the format: "Round Robin 1: Court 1: Team1 vs Team2"
    new_name=""
    if [[ -n "$formatted_type" && -n "$round_from_jsonl" ]]; then
        new_name="${formatted_type} ${round_from_jsonl}"
    elif [[ -n "$round_from_jsonl" ]]; then
        new_name="Round ${round_from_jsonl}"
    fi
    
    if [[ -n "$court_name" ]]; then
        # Format court name (replace underscores with spaces)
        formatted_court=$(echo "$court_name" | sed 's/_/ /g')
        [[ -n "$new_name" ]] && new_name="${new_name}: "
        new_name="${new_name}${formatted_court}"
    fi
    
    # Add team names
    [[ -n "$new_name" ]] && new_name="${new_name}: "
    new_name="${new_name}${teams}.${extension}"
    
    echo "Original: $original_name"
    echo "New:      $new_name"
    echo "---"
done
