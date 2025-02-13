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

# returns: list of dictionaries with the home team and away team names
def get_ordered_teams(court_number):
    all_teams_including_refs = []
    if court_number == 1:
        all_teams_including_refs = ROUND_ROBIN_COURT_1_TEAMS
    elif court_number == 2:
        all_teams_including_refs = ROUND_ROBIN_COURT_2_TEAMS
    elif court_number == 3:
        all_teams_including_refs = ROUND_ROBIN_COURT_3_TEAMS
    
    ordered_teams = []
    for i in range(0, len(all_teams_including_refs), 3):
        ordered_teams.append({
            "home_team": all_teams_including_refs[i],
            "away_team": all_teams_including_refs[i + 1]
        })
    return ordered_teams

# returns: list of dictionaries with the home team and away team names and the logo paths for each
def get_ordered_teams_with_logo_paths(court_number):
    ordered_teams = get_ordered_teams(court_number)
    ordered_teams_with_logo_paths = []
    for matchup in ordered_teams:
        home_team = matchup["home_team"]
        away_team = matchup["away_team"]
        home_team_logo_path = get_logo_path(home_team) # TODO: There's only 12 teams, we don't need to keep getting the logo path
        away_team_logo_path = get_logo_path(away_team)
        ordered_teams_with_logo_paths.append({
            "home_team": home_team,
            "away_team": away_team,
            "home_team_logo_path": home_team_logo_path,
            "away_team_logo_path": away_team_logo_path
        })
    return ordered_teams_with_logo_paths


    

# Rename the videos in the directory to the following format: "Home Team vs. Away Team.mp4"
# directory_name: the name of the directory containing the videos
# ordered_teams_including_refs: a list of teams in the order they appear in the video
def rename_videos(directory_name, ordered_teams_including_refs):
    # The list of teams will include the home team, away team, and ref
    # We only care about the home team and away team for each game
    # For each video in the directory, ordered by timestamp, if the video is at least 5 minutes long,
    # We will rename it to the following format: "Home Team vs. Away Team.mp4"
    # If the video is less than 5 minutes long, we will ignore it
    home_team_index = 0
    output_directory = f'{directory_name}/processed_videos'
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    for video in list_files_sorted_by_date(directory_name):
        if video.endswith(".mp4"):
            video_path = os.path.join(directory_name, video)
            # Get the length of the video
            # If the video is at least 5 minutes long, rename it
            # Otherwise, ignore it
            video_length = get_video_length(video_path)
            if video_length >= 300:
                # Get the home team and away team
                home_team = ordered_teams_including_refs[home_team_index]
                away_team = ordered_teams_including_refs[home_team_index + 1]
                home_team_index += 3
                new_video_name = f"{home_team}_{away_team}_round_robin.mp4"
                new_video_path = os.path.join(output_directory, new_video_name)
                shutil.copy(video_path, new_video_path)
                log(f"Copied {video} to {new_video_path}")


                # # Add the team names to the video
                # add_team_name_to_video(new_video_path, home_team, away_team)
                # log(f"Added team names to {new_video_name}")
            else:
                log(f"Ignoring {video} because it is too short to be a matchup")
        else:
            log(f"Ignoring {video}")
        


def run(directory_name, ordered_teams_including_refs):
    # Rename the videos in the directory
    rename_videos(directory_name, ordered_teams_including_refs)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Handle tournament videos.')
    # parser.add_argument('directory_name', type=str, help='The name of the directory containing the videos')
    # parser.add_argument('--court', type=int, help='The court number', default=1)
    parser.add_argument('--round_type', type=str, help='The type of round (round_robin, playoffs, finals)', default='round_robin')
    parser.add_argument('--min_video_length', type=int, help='The minimum length of a video in seconds', default=300)
    args = parser.parse_args()

    # directory_name = args.directory_name
    sheet_data = get_google_sheet_data()
    schedule = parse_schedule(sheet_data)

    for court_number in range(1, 4):
        court_name = f"Court {court_number}"
        ordered_teams = schedule[court_name]
        log(f"Ordered teams for {court_name}: {ordered_teams}")
    
    # log(f"Ordered teams: {ordered_teams}")

    # run(directory_name, ordered_teams)
