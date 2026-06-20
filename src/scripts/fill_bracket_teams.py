#!/usr/bin/env python3
"""
Fill in bracket team names after seeding and optionally rename split videos.

Match games by court + start_time. TBD placeholder files include the start time
in the filename (e.g. Bracket Quarters: Court 2: 14:40: TBD vs TBD.mp4).

Usage:
  python fill_bracket_teams.py \\
    --jsonl schedule/generated/2026-06-20_court2.jsonl \\
    --updates bracket_teams.json \\
    --split-dir src/output/June2026Tournament/2026-06-20/court2/split_videos \\
    --rename

updates JSON format:
[
  {
    "start_time": "14:40",
    "court": "Court 2",
    "home_team": "Sister Sister",
    "away_team": "Static Shock"
  }
]
"""

import argparse
import json
import sys
from pathlib import Path

from game_filename import build_matchup_filename, is_placeholder_team


def load_jsonl(path):
    games = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                games.append(json.loads(line))
    return games


def write_jsonl(path, games):
    with open(path, "w") as f:
        for game in games:
            f.write(json.dumps(game) + "\n")


def match_key(game):
    court = game.get("court") or game.get("court_display") or ""
    return (game["start_time"], court.strip().lower())


def apply_updates(games, updates):
    by_key = {match_key(game): game for game in games}
    pairs = []
    for update in updates:
        key = (update["start_time"], update["court"].strip().lower())
        if key not in by_key:
            print(f"Warning: no game for {update['court']} at {update['start_time']}", file=sys.stderr)
            continue
        game = by_key[key]
        old_snapshot = dict(game)
        game["home_team"] = update["home_team"]
        game["away_team"] = update["away_team"]
        if update.get("round"):
            game["round"] = update["round"]
        if update.get("type"):
            game["type"] = update["type"]
        pairs.append((old_snapshot, game))
    print(f"Updated {len(pairs)} game(s)")
    return pairs


def rename_split_videos(renames, split_dir, dry_run=False):
    split_dir = Path(split_dir)
    for old_name, new_name in renames:
        old_path = split_dir / old_name
        new_path = split_dir / new_name
        if old_name == new_name:
            continue
        if not old_path.exists():
            print(f"Warning: split video not found: {old_path}", file=sys.stderr)
            continue
        if new_path.exists():
            print(f"Warning: target already exists, skipping: {new_path}", file=sys.stderr)
            continue
        if dry_run:
            print(f"Would rename: {old_name} -> {new_name}")
        else:
            old_path.rename(new_path)
            print(f"Renamed: {old_name} -> {new_name}")


def main():
    parser = argparse.ArgumentParser(description="Fill bracket team names in games.jsonl")
    parser.add_argument("--jsonl", required=True, help="Per-court games.jsonl to update")
    parser.add_argument("--updates", required=True, help="JSON file with team updates")
    parser.add_argument("--split-dir", default=None, help="split_videos/ folder to rename")
    parser.add_argument("--rename", action="store_true", help="Rename split videos to match new team names")
    parser.add_argument("--dry-run", action="store_true", help="Preview renames without writing")
    args = parser.parse_args()

    jsonl_path = Path(args.jsonl)
    updates_path = Path(args.updates)
    if not jsonl_path.exists():
        print(f"Error: JSONL not found: {jsonl_path}", file=sys.stderr)
        sys.exit(1)
    if not updates_path.exists():
        print(f"Error: updates file not found: {updates_path}", file=sys.stderr)
        sys.exit(1)

    with open(updates_path) as f:
        updates = json.load(f)
    if not isinstance(updates, list):
        print("Error: updates file must be a JSON array", file=sys.stderr)
        sys.exit(1)

    games = load_jsonl(jsonl_path)
    pairs = apply_updates(games, updates)
    renames = []
    for old_game, new_game in pairs:
        if args.rename and args.split_dir:
            renames.append((build_matchup_filename(old_game), build_matchup_filename(new_game)))

    if not args.dry_run:
        write_jsonl(jsonl_path, games)
        print(f"Wrote {jsonl_path}")
    else:
        print(f"[DRY RUN] Would write {jsonl_path}")

    if args.rename and args.split_dir:
        rename_split_videos(renames, args.split_dir, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
