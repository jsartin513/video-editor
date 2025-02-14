import argparse
import os
import shutil
from moviepy.video.VideoClip import *
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
from moviepy import *

from utils.files import get_video_length, list_files_sorted_by_date
from utils.google_sheet_reader import get_google_sheet_data, parse_schedule, get_logo_path



ROUND_ROBIN_COURT_1_TEAMS = ["home1", "away1", "ref1", "home2", "away2", "ref2", "home3", "away3", "ref3", "home4", "away4", "ref4", "home5", "away5", "ref5", "home6", "away6", "ref6"]
ROUND_ROBIN_COURT_2_TEAMS = []
ROUND_ROBIN_COURT_3_TEAMS = []

FONT_PATH = "./font/font.ttf"

def log(message):
    print(message)

# Add the team names to stylized panels in the video
def add_team_name_to_video(filename, home_team, away_team):
    output_path = f"{filename}_with_team_names.mp4"
    text = f"{home_team} vs. {away_team}"
    video = VideoFileClip(filename)
    home_team_clip = (
    TextClip(font=FONT_PATH, text=home_team, font_size=72, color="blue", bg_color="yellow")
    .with_position((1800, 2200))
    .with_duration(video.duration)
    )
    away_team_clip = (
    TextClip(font=FONT_PATH, text=away_team, font_size=72, color="blue", bg_color="yellow")
    .with_position((1200, 2200))
    .with_duration(video.duration)
    )

    video_with_text = CompositeVideoClip([video, home_team_clip, away_team_clip])

    video_with_text.write_videofile(output_path, codec="libx264", fps=24)

# add_team_name_to_video("/Users/jessica.sartin/Movies/GoPro/bdl_open_gym_july_22_2024/test_videos/processed_videos/shorter_video.mp4", "team 1", "team 2")



# This will create a video with the BDL logo in the background
# The home team name will come in from the top left
# And the away team name will come in from the bottom right
# Until they meet in the center
def create_opening_screen(home_team, away_team):
    home_team_logo_path = get_logo_path(home_team)
    away_team_logo_path = get_logo_path(away_team)

    background_image = ImageClip("static/bdl_rectangle_logo.png").with_duration(10)

    output_path = f"{home_team}_vs_{away_team}__opening_screen.mp4"
    home_team_clip = (
        TextClip(font=FONT_PATH, text=home_team, font_size=72, color="black", duration=10)
        .with_position((0.3, 0.35), relative=True).with_effects([vfx.CrossFadeIn(3)])
    )
    home_team_logo_clip = (
        ImageClip(home_team_logo_path, duration=10).resized(width=200)
        .with_position((0.2, 0.3), relative=True).with_effects([vfx.CrossFadeIn(3)])
    )
    away_team_clip = (
        TextClip(font=FONT_PATH, text=away_team, font_size=72, color="black", duration=7)
        .with_position((0.5, 0.55), relative=True).with_start(3).with_effects([vfx.CrossFadeIn(3)])
    )
    away_team_logo_clip = (
        ImageClip(away_team_logo_path, duration=7).resized(width=200)
        .with_position((0.4, 0.5), relative=True).with_start(3).with_effects([vfx.CrossFadeIn(3)])
    )
    opening_screen = CompositeVideoClip([background_image, home_team_clip, home_team_logo_clip, away_team_clip, away_team_logo_clip])
    opening_screen.write_videofile(output_path, codec="libx264", fps=24)

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
        new_video_name = f"{home_team}_{away_team}_round_robin.mp4"
        new_video_path = os.path.join(output_directory, new_video_name)
        old_video_path = os.path.join(directory_name, video)
        shutil.copy(old_video_path, new_video_path)
        log(f"Copied {video} with creation time {video} to {new_video_path}")
        game["video_path"] = new_video_path
        video_paths.append(new_video_path)
    return video_paths


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


def run(directory_name, ordered_teams_including_refs):
    # Rename the videos in the directory
    rename_videos(directory_name, ordered_teams_including_refs)

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

    video_paths =rename_videos(args.directory_name, ordered_games)

    
    # log(f"Ordered teams: {ordered_teams}")

    # run(directory_name, ordered_teams)
