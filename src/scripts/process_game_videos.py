import json
from moviepy import *
import numpy as np

import argparse

FONT_PATH = "./font/font.ttf"

LOGO_ICON_MAX_WIDTH = 180
LOGO_ICON_MIN_WIDTH = 120
TEAM_NAME_MAX_FONT_SIZE = 72
TEAM_NAME_MIN_FONT_SIZE = 36

STARTING_LOGO_POSITION = (0.11, 0.2)
STARTING_TEAM_NAME_POSITION = (0.205, 0.25)

ENDING_AWAY_TEAM_LOGO_POSITION = (0.5, 0.8)
ENDING_HOME_TEAM_LOGO_POSITION = (0.11, 0.8)
ENDING_AWAY_TEAM_NAME_POSITION = (0.55, 0.8)
ENDING_HOME_TEAM_NAME_POSITION = (0.205, 0.8)

TOTAL_DURATION = 15
STANDARD_TRANSITION_TIME = 3


def log(message):
    print(message)


def format_team_name_for_filename(team_name):
    return team_name.replace(" ", "_").replace(",", "").replace("'", "").lower()



# Create a circular mask
def get_circular_mask():
    center_x, center_y = LOGO_ICON_MAX_WIDTH // 2, LOGO_ICON_MAX_WIDTH // 2
    width, height = LOGO_ICON_MAX_WIDTH, LOGO_ICON_MAX_WIDTH
    radius = min(width, height) // 2
    mask = np.zeros((height, width)) 
    x, y = np.ogrid[:height, :width]
    mask[(x - center_y)**2 + (y - center_x)**2 <= radius**2] = 1  
    return mask



def function_for_size(t, start_size, end_size, clip_duration=STANDARD_TRANSITION_TIME):
    return start_size + (end_size - start_size) * t / clip_duration

# Create a function that takes in a time t and returns the position of an object moving from start_position to end_position
def function_for_position(t, start_position, end_position, clip_duration=STANDARD_TRANSITION_TIME):
    x_start_position, y_start_position = start_position
    x_end_position, y_end_position = end_position
    x_distance = x_end_position - x_start_position
    y_distance = y_end_position - y_start_position

    return (x_start_position + x_distance * t / clip_duration, y_start_position + y_distance * t / clip_duration)

# This is going to have static information about this tournament
def get_bdl_tournament_banner():
    text = "Boston Dodgeball League presents The Throw Down 3 - February 22, 2025"
    banner = (
        TextClip(font=FONT_PATH, text=text, size=(1920, 24))
        .with_position(("center", "top")).with_duration(TOTAL_DURATION)
    )
    return banner

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
    return output_path


# Create clips for the team name with "standard" transitions using the variables described above
def get_name_clips(team_name, start_position, end_position, start_time=0):
    fade_in_clip_start = start_time
    moving_clip_start = fade_in_clip_start + STANDARD_TRANSITION_TIME
    final_position_start = fade_in_clip_start + STANDARD_TRANSITION_TIME * 2
    team_clip_fade_in = (
        TextClip(font=FONT_PATH, text=team_name, font_size=TEAM_NAME_MAX_FONT_SIZE, color="black", duration=STANDARD_TRANSITION_TIME)
        .with_position(start_position, relative=True).with_effects([vfx.CrossFadeIn(STANDARD_TRANSITION_TIME)]).with_start(fade_in_clip_start)
    )
    team_clip_moving = (
        TextClip(font=FONT_PATH, text=team_name, font_size=TEAM_NAME_MAX_FONT_SIZE, color="black", duration=STANDARD_TRANSITION_TIME)
        .with_position(lambda t: function_for_position(t, start_position, end_position), relative=True).with_start(moving_clip_start)
    )
    team_clip_final_position = (
        TextClip(font=FONT_PATH, text=team_name, font_size=TEAM_NAME_MAX_FONT_SIZE, color="black", duration=TOTAL_DURATION - final_position_start)
        .with_position(end_position, relative=True).with_start(final_position_start)
    )
    return team_clip_fade_in, team_clip_moving, team_clip_final_position


# Create clips for the logo with "standard" transitions using the variables described above
def get_logo_clips(logo_path, ending_logo_position, start_time=0):
    fade_in_clip_start = start_time
    moving_clip_start = fade_in_clip_start + STANDARD_TRANSITION_TIME
    final_position_start = fade_in_clip_start + STANDARD_TRANSITION_TIME * 2
    circular_mask = ImageClip(get_circular_mask(), is_mask=True)
    logo_clip_fade_in = (
        ImageClip(logo_path, duration=STANDARD_TRANSITION_TIME).resized(width=LOGO_ICON_MAX_WIDTH)
        .with_mask(circular_mask).with_position(STARTING_LOGO_POSITION, relative=True).with_effects([vfx.CrossFadeIn(STANDARD_TRANSITION_TIME)]).with_start(fade_in_clip_start)
    )
    logo_clip_moving = (
        ImageClip(logo_path, duration=STANDARD_TRANSITION_TIME).resized(width=LOGO_ICON_MAX_WIDTH)
        .with_mask(circular_mask).with_position(lambda t: function_for_position(t, STARTING_LOGO_POSITION, ending_logo_position), relative=True).with_start(moving_clip_start)
    )
    logo_clip_final_position = (
        ImageClip(logo_path, duration=TOTAL_DURATION - final_position_start).resized(width=LOGO_ICON_MAX_WIDTH)
        .with_mask(circular_mask).with_position(ending_logo_position, relative=True).with_start(final_position_start)
    )
    return logo_clip_fade_in, logo_clip_moving, logo_clip_final_position
# Create opening screen with "standard" transitions using the variables described above
def create_opening_screen(output_directory, game):
    home_team = game["home_team"]
    away_team = game["away_team"]
    home_team_logo_path = game["home_team_logo_path"]
    away_team_logo_path = game["away_team_logo_path"]
    output_path = f"{output_directory}/{format_team_name_for_filename(home_team)}_vs_{format_team_name_for_filename(away_team)}_opening_screen.mp4"

    background_image = ImageClip("src/static/bdl_rectangle_logo.png").with_duration(TOTAL_DURATION)
    
    tournament_banner = get_bdl_tournament_banner()
    home_team_logo_clip_fade_in, home_team_logo_clip_moving, home_team_logo_final_position = get_logo_clips(home_team_logo_path, ENDING_HOME_TEAM_LOGO_POSITION)
    home_team_clip_fade_in, home_team_clip_moving, home_team_clip_final_position = get_name_clips(home_team, STARTING_TEAM_NAME_POSITION, ENDING_HOME_TEAM_NAME_POSITION)
    away_team_logo_clip_fade_in, away_team_logo_clip_moving, away_team_logo_final_position = get_logo_clips(away_team_logo_path, ENDING_AWAY_TEAM_LOGO_POSITION, STANDARD_TRANSITION_TIME)
    away_team_clip_fade_in, away_team_clip_moving, away_team_clip_final_position = get_name_clips(away_team, STARTING_TEAM_NAME_POSITION, ENDING_AWAY_TEAM_NAME_POSITION, STANDARD_TRANSITION_TIME)
 
    opening_screen = CompositeVideoClip([
        background_image,
        tournament_banner,
        home_team_logo_clip_fade_in,
        home_team_logo_clip_moving,
        home_team_logo_final_position,
        home_team_clip_fade_in,
        home_team_clip_moving,
        home_team_clip_final_position,
        away_team_logo_clip_fade_in,
        away_team_logo_clip_moving,
        away_team_logo_final_position,
        away_team_clip_fade_in,
        away_team_clip_moving,
        away_team_clip_final_position
    ])
    opening_screen.write_videofile(output_path, codec="libx264", fps=24)


def process_game(output_path, game):
    create_opening_screen(output_path, game)
    # add_team_name_to_video(game["video_path"], game["home_team"], game["away_team"])


def run(output_path, games):
    for game in games:
        log(f"Processing game at {game['video_path']}")
        process_game(output_path, game)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Handle tournament videos.')
    parser.add_argument('directory_name', type=str, help='The name of the directory containing the videos')


    args = parser.parse_args()

    output_path = f"{args.directory_name}/processed_videos"
    metadata_path = f"{output_path}/metadata.json"

    with open(metadata_path, "r") as f:
        games = json.load(f)


    # Just run on one game for testing
    games = games[:1]
    run(output_path, games)