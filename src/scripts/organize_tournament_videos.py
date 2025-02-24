import argparse
import json
import os
import shutil

from utils.files import get_video_length, list_files_of_type_sorted_by_date, merge_list_of_videos
from utils.google_sheet_reader import get_google_sheet_data, parse_schedule
from utils.utils import log, format_team_name_for_filename

MISSED_GAME_INDICES = [5]

# Rename the videos in the directory to the following format: "Home Team vs. Away Team.mp4"
# directory_name: the name of the directory containing the videos
def rename_videos(directory_name, games_list, dry_run=False):
    output_directory = f'{directory_name}/processed_videos'
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    video_paths = []
    videos = get_likely_ordered_game_filenames(directory_name)
    idx_offset = 0
    for game_idx, video_list in enumerate(videos):
        game_video_paths = []
        if game_idx in MISSED_GAME_INDICES:
            idx_offset = 1
        game = games_list[game_idx + idx_offset] # In case any games are missed
        home_team = game["home_team"]
        away_team = game["away_team"]
        round = game["round"]


        for idx, video in enumerate(video_list, start=1):
            new_video_name = f"{format_team_name_for_filename(home_team)}_{format_team_name_for_filename(away_team)}_round_robin_round_{round}_part_{idx}.mp4"
            new_video_path = os.path.join(output_directory, new_video_name)
            old_video_path = os.path.join(directory_name, video)

            if not dry_run:
                shutil.copy(old_video_path, new_video_path)
            log(f"Copied {video_list} to {new_video_path}")
            game["video_path"] = new_video_path
            game_video_paths.append(new_video_path)
        video_paths.append(game_video_paths)

    return output_directory, video_paths


# Pull all videos in the directory greater than five minutes long
def get_likely_ordered_game_filenames(directory_name):
    game_video_filenames = []
    filenames_in_this_recording = []
    for video in list_files_of_type_sorted_by_date(directory_name):
            
        # Files are named like GX, a 2 digit number, then a 4 digit number.
        # When we go from one video to the next, if the 4 digit number stays the same
        # and the 2 digit number increments, the two videos are one recording split into two files.
        # When the 4-digit number increments, it's a new game.
        video_prefix = video[2:4]
        video_suffix = video[4:8]

        if filenames_in_this_recording:
            if video_suffix == filenames_in_this_recording[-1][4:8]: # Still creating the list for this recording
                filenames_in_this_recording.append(video)
                log(f"Appending {video} to filenames_in_this_recording")
            else: # This is a new recording, so we need to update the game_video_filenames with a tuple of each filename in this recording
                game_video_filenames.append(filenames_in_this_recording)
                filenames_in_this_recording = [video]
                log(f"New recording: {video}")
                log(f"Adding {filenames_in_this_recording} to game_video_filenames")
                log(f"Game video filenames: {game_video_filenames}")
        else:
            filenames_in_this_recording.append(video)
            log(f"First video: {video}")
    # Add the last recording
    game_video_filenames.append(filenames_in_this_recording)

    # Check through the videos and if the tuple has just one item AND that video is less than five minutes long, remove it from the list
    game_video_filenames = [video for video in game_video_filenames if len(video) > 1 or get_video_length(os.path.join(directory_name, video[0])) > 300]


    log(f"Game video filenames: {game_video_filenames}")
    return game_video_filenames


def create_metadata_file(schedule, output_path, video_paths):
    log(f"Creating metadata file at {output_path}/metadata.json")
    log(f"video_paths: {video_paths}")
    metadata = []
    idx_offset = 0
    for idx, game in enumerate(schedule):
        if idx in MISSED_GAME_INDICES:
            idx_offset = idx_offset - 1
            continue
        metadata.append({
            "home_team": game["home_team"],
            "away_team": game["away_team"],
            "video_path": video_paths[idx + idx_offset],
            "home_team_score": game.get("home_team_score", None),
            "away_team_score": game.get("away_team_score", None),
            "round": game["round"],
            "start_time": game["start_time"],
            "home_team_logo_path": game.get("home_team_logo_path", None),
            "away_team_logo_path": game.get("away_team_logo_path", None)
        })
    with open(f"{output_path}/metadata.json", "w") as f:
        json.dump(metadata, f)
    log(f"Metadata file created at {output_path}/metadata.json")

def run(directory_name, ordered_games, dry_run=False):
    # Rename the videos in the directory
    output_path, video_paths = rename_videos(directory_name, ordered_games, dry_run)
    create_metadata_file(ordered_games, output_path, video_paths)
    

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Handle tournament videos.')
    parser.add_argument('directory_name', type=str, help='The name of the directory containing the videos')
    parser.add_argument('--court', type=int, help='The court number')
    parser.add_argument('--dry-run', action='store_true', help='If true, do not copy the files, just print the output')

    args = parser.parse_args()

    sheet_data = get_google_sheet_data()
    schedule = parse_schedule(sheet_data)

    # for court_number in range(1, 4):
    court_name = f"Court {args.court}"
    ordered_games = schedule[court_name]

    # video_paths =rename_videos(args.directory_name, ordered_games)
    output_path = f"{args.directory_name}/processed_videos"

    if not os.path.exists(output_path):
        os.makedirs(output_path)

    opening_screens_output_path = f"{output_path}/opening_screens"

    run(args.directory_name, ordered_games, args.dry_run)