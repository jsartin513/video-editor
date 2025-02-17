import argparse
import json
import os
import shutil
from moviepy.video.VideoClip import *
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
from moviepy import *

from utils.files import get_video_length, list_files_sorted_by_date
from utils.google_sheet_reader import get_google_sheet_data, parse_schedule


FONT_PATH = "./font/font.ttf"

def log(message):
    print(message)

def format_team_name_for_filename(team_name):
    return team_name.replace(" ", "_").replace(",", "").replace("'", "").lower()


# add_team_name_to_video("/Users/jessica.sartin/Movies/GoPro/bdl_open_gym_july_22_2024/test_videos/processed_videos/shorter_video.mp4", "team 1", "team 2")




# create_opening_screen("Kids Next Door", "Boston T Titans")

# Rename the videos in the directory to the following format: "Home Team vs. Away Team.mp4"
# directory_name: the name of the directory containing the videos
# ordered_teams_including_refs: a list of teams in the order they appear in the video
def rename_videos(directory_name, games_list):
    output_directory = f'{directory_name}/processed_videos'
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    videos = get_likely_ordered_game_filenames(directory_name)
    video_paths = []
    for idx, video in enumerate(videos):
        game = games_list[idx]
        home_team = game["home_team"]
        away_team = game["away_team"]
        round = game["round"]
        new_video_name = f"{format_team_name_for_filename(home_team)}_{format_team_name_for_filename(away_team)}_round_robin_round_{round}.mp4"
        new_video_path = os.path.join(output_directory, new_video_name)
        old_video_path = os.path.join(directory_name, video)
        shutil.copy(old_video_path, new_video_path)
        log(f"Copied {video} to {new_video_path}")
        game["video_path"] = new_video_path
        video_paths.append(new_video_path)
    return output_directory, video_paths


# Pull all videos in the directory greater than five minutes long
def get_likely_ordered_game_filenames(directory_name):
    game_video_filenames = []
    for video in list_files_sorted_by_date(directory_name):
        if video.endswith(".mp4"):
            video_path = os.path.join(directory_name, video)
            video_length = get_video_length(video_path)
            if video_length >= 300:
                game_video_filenames.append(video)
    log(f"Game video filenames: {game_video_filenames}")
    return game_video_filenames


def create_metadata_file(schedule, output_path, video_paths):
    metadata = []
    for idx, game in enumerate(schedule):
        metadata.append({
            "home_team": game["home_team"],
            "away_team": game["away_team"],
            "video_path": video_paths[idx],
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

def run(directory_name, ordered_games):
    # Rename the videos in the directory
    output_path, video_paths = rename_videos(directory_name, ordered_games)
    create_metadata_file(ordered_games, output_path, video_paths)


    
    

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Handle tournament videos.')
    parser.add_argument('directory_name', type=str, help='The name of the directory containing the videos')
    parser.add_argument('--court', type=int, help='The court number')
    # parser.add_argument('--round_type', type=str, help='The type of round (round_robin, playoffs, finals)', default='round_robin')
    # parser.add_argument('--min_video_length', type=int, help='The minimum length of a video in seconds', default=300)
    args = parser.parse_args()

    # directory_name = args.directory_name
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


    run(args.directory_name, ordered_games)