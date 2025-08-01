import argparse
import json
import os
import shutil

from utils.files import get_video_length, list_files_of_type_sorted_by_date, get_video_start_and_end_timestamps
from utils.google_sheet_reader import get_parsed_schedule, get_parsed_bracket
from utils.utils import log, format_team_name_for_filename

MISSED_GAME_INDICES = []

# We didn't always reset the camera between rounds. 
# So any of these filenames span at least the end of one game and start of the next
FILENAMES_WITH_MULTIPLE_GAMES = ['GX010343.MP4', 'GX020343.MP4', 'GX010344.MP4', 'GX010348.MP4', 'GX010344.MP4', 'GX010349.MP4', 'GX020348.MP4']

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
            idx_offset = idx_offset + 1
            continue
        try:
            game = games_list[game_idx - idx_offset] # In case any games are missed
        except IndexError:
            log(f"Game {game_idx} was missed")
            break
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
        duplicated_so_move_on = False

        if filenames_in_this_recording:
            if video_suffix == filenames_in_this_recording[-1][4:8] and not duplicated_so_move_on: # Still creating the list for this recording
                filenames_in_this_recording.append(video)
                log(f"Appending {video} to filenames_in_this_recording")
                if video in FILENAMES_WITH_MULTIPLE_GAMES:
                    duplicated_so_move_on = True
                    game_video_filenames.append(filenames_in_this_recording)
                    log(f"Adding {filenames_in_this_recording} to game_video_filenames, split across rounds")
                    log(f"Game video filenames: {game_video_filenames}")
                    filenames_in_this_recording = [video]
            else: # This is a new recording, so we need to update the game_video_filenames with a tuple of each filename in this recording
                game_video_filenames.append(filenames_in_this_recording)
                filenames_in_this_recording = [video]
                log(f"New recording: {video}")
                log(f"Adding {filenames_in_this_recording} to game_video_filenames")
                log(f"Game video filenames: {game_video_filenames}")
                if video in FILENAMES_WITH_MULTIPLE_GAMES:
                    duplicated_so_move_on = True
                    game_video_filenames.append(filenames_in_this_recording)
                    log(f"Adding {filenames_in_this_recording} to game_video_filenames, split across rounds")
                    log(f"Game video filenames: {game_video_filenames}")
                    filenames_in_this_recording = [video]
        else:
            filenames_in_this_recording.append(video)
            log(f"First video: {video}")
            
    # Add the last recording
    game_video_filenames.append(filenames_in_this_recording)

    # Check through the videos and if the tuple has just one item AND that video is less than five minutes long, remove it from the list
    game_video_filenames = [video for video in game_video_filenames if len(video) > 1 or get_video_length(os.path.join(directory_name, video[0])) > 300]


    log(f"Game video filenames: {game_video_filenames}")
    return game_video_filenames

VIDEOPATH_WITH_TIMES = "/Users/MrsHazmat/throw_down_3_recordings/court_1_rr/processed_videos/final_videos"
def get_start_times_from_hardcoded_file_path():
    start_and_end_times_by_round = {}
    for final_video in list_files_of_type_sorted_by_date(VIDEOPATH_WITH_TIMES):
        log(f"Final video: {final_video}")
        start_time, end_time = get_video_start_and_end_timestamps(os.path.join(VIDEOPATH_WITH_TIMES, final_video))[0]
        log(f"Start time: {start_time}")
        log(f"End time: {end_time}")
        round_number = final_video.split("_")[-2]
        start_and_end_times_by_round[round_number] = (start_time, end_time)
    return start_and_end_times_by_round



def create_metadata_file(schedule, output_path, video_paths):
    log(f"Creating metadata file at {output_path}/metadata.json")
    log(f"video_paths: {video_paths}")
    metadata = []
    idx_offset = 0
    for idx, game in enumerate(schedule):
        if idx in MISSED_GAME_INDICES:
            idx_offset = idx_offset - 1
            continue
        try:
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
        except IndexError:
            log(f"Game {idx} was missed")
            break
    with open(f"{output_path}/metadata.json", "w") as f:
        json.dump(metadata, f)
    log(f"Metadata file created at {output_path}/metadata.json")

def run(directory_name, ordered_games, dry_run=False):
    # Rename the videos in the directory
    output_path, video_paths = rename_videos(directory_name, ordered_games, dry_run)
    # get_start_times_from_hardcoded_file_path()
    # Create a metadata file
    create_metadata_file(ordered_games, output_path, video_paths)
    

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Handle tournament videos.')
    parser.add_argument('directory_name', type=str, help='The name of the directory containing the videos')
    parser.add_argument('--court', type=int, help='The court number')
    parser.add_argument('--bracket', action='store_true', help='If true, the games are bracket games')
    parser.add_argument('--dry-run', action='store_true', help='If true, do not copy the files, just print the output')

    args = parser.parse_args()
    court_name = f"Court {args.court}"

    if args.bracket:
        schedule = get_parsed_bracket()
        games_for_court = [game for game in schedule if game["court"].strip() == court_name.lower()]
        round_mapping = {
            "Round 1": 1,
            "Quarters": 2,
            "Semis": 3,
            "Finals": 4}
        ordered_games = sorted(games_for_court, key=lambda x: (round_mapping[x["round"]], x["subround"]))
    else:
        schedule = get_parsed_schedule()
        ordered_games = schedule[court_name]

    # video_paths =rename_videos(args.directory_name, ordered_games)
    output_path = f"{args.directory_name}/processed_videos"

    if not os.path.exists(output_path):
        os.makedirs(output_path)

    opening_screens_output_path = f"{output_path}/opening_screens"

    run(args.directory_name, ordered_games, args.dry_run)