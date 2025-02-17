import json
import math
import random
from moviepy import *
import numpy as np

import argparse

from utils.utils import log, format_team_name_for_filename

FONT_PATH = "./font/font.ttf"

# BDL_LOGO_PATH = "src/static/grayscale_bdl_logo.png"
BDL_LOGO_PATH = "src/static/bdl_rectangle_logo.png"

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

TOTAL_DURATION = 10
STANDARD_TRANSITION_TIME = 1.5

HEADER_TEXT = "Boston Dodgeball League"
SUBHEADER_TEXT = "The Throw Down 3"



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

    background_image = ImageClip(BDL_LOGO_PATH).with_duration(TOTAL_DURATION)
    # background_image = ImageClip(BDL_LOGO_PATH).with_duration(TOTAL_DURATION - STANDARD_TRANSITION_TIME)
    # background_image_fading = ImageClip(BDL_LOGO_PATH).with_duration(STANDARD_TRANSITION_TIME).with_start(TOTAL_DURATION - STANDARD_TRANSITION_TIME).with_effects([vfx.CrossFadeOut(STANDARD_TRANSITION_TIME)])
    # game_video_fade_in = VideoFileClip(game["video_path"]).with_duration(13).with_start(TOTAL_DURATION - STANDARD_TRANSITION_TIME).with_effects([vfx.CrossFadeIn(STANDARD_TRANSITION_TIME)])


    tournament_banner = get_bdl_tournament_banner()
    home_team_logo_clip_fade_in, home_team_logo_clip_moving, home_team_logo_final_position = get_logo_clips(home_team_logo_path, ENDING_HOME_TEAM_LOGO_POSITION)
    home_team_clip_fade_in, home_team_clip_moving, home_team_clip_final_position = get_name_clips(home_team, STARTING_TEAM_NAME_POSITION, ENDING_HOME_TEAM_NAME_POSITION)
    away_team_logo_clip_fade_in, away_team_logo_clip_moving, away_team_logo_final_position = get_logo_clips(away_team_logo_path, ENDING_AWAY_TEAM_LOGO_POSITION, STANDARD_TRANSITION_TIME)
    away_team_clip_fade_in, away_team_clip_moving, away_team_clip_final_position = get_name_clips(away_team, STARTING_TEAM_NAME_POSITION, ENDING_AWAY_TEAM_NAME_POSITION, STANDARD_TRANSITION_TIME)
 
    opening_screen = CompositeVideoClip([
        background_image,
        # background_image_fading,
        # game_video_fade_in,
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


def create_team_clip(team_name, match_score, logo_path, text_color, side="left", start_time=0):
    duration = TOTAL_DURATION - start_time
    # Add position based on which side it is (left or right)
    if side == "left":
        logo_position = (0.1, 0.6)
        team_name_position = (0.25, 0.6)
        match_score_position = (0.25, 0.7)
    else:
        logo_position = (0.8, 0.6)
        team_name_position = (0.6, 0.6)
        match_score_position = (0.6, 0.7)

    # Create the logo clip
    circular_mask = ImageClip(get_circular_mask(), is_mask=True)
    logo_clip = (
        ImageClip(logo_path, duration=duration).resized(width=LOGO_ICON_MAX_WIDTH)
        .with_mask(circular_mask).with_position(logo_position, relative=True)
        .with_effects([vfx.CrossFadeIn(STANDARD_TRANSITION_TIME)]).with_start(start_time)
    )
    team_name_clip = (
        TextClip(font=FONT_PATH, text=team_name, font_size=TEAM_NAME_MIN_FONT_SIZE, color=text_color)
        .with_position(team_name_position, relative=True).with_duration(duration)
        .with_effects([vfx.CrossFadeIn(STANDARD_TRANSITION_TIME)]).with_start(start_time)
    )
    match_score_clip = (
        TextClip(font=FONT_PATH, text=match_score, font_size=TEAM_NAME_MIN_FONT_SIZE, color=text_color)
        .with_position(match_score_position, relative=True).with_duration(duration - STANDARD_TRANSITION_TIME)
        .with_effects([vfx.CrossFadeIn(STANDARD_TRANSITION_TIME)]).with_start(start_time + STANDARD_TRANSITION_TIME)
    )
    return logo_clip, team_name_clip, match_score_clip

def create_header_text_clips(header_text, subheader_text, round_text, text_color):
    header_font_size = 72
    subheader_font_size = 60
    round_font_size = 48

    header_text_clip = TextClip(font=FONT_PATH, text=header_text, font_size=header_font_size, color=text_color).with_position(("center", 0.2), relative=True).with_duration(TOTAL_DURATION)
    sub_header_text_clip = TextClip(font=FONT_PATH, text=subheader_text, font_size=subheader_font_size, color=text_color).with_position(("center", 0.3), relative=True).with_duration(TOTAL_DURATION)
    round_text_fade_in_clip = TextClip(font=FONT_PATH, text=round_text, font_size=round_font_size, color=text_color).with_position(("center", 0.4), relative=True).with_duration(STANDARD_TRANSITION_TIME).with_start(STANDARD_TRANSITION_TIME).with_effects([vfx.CrossFadeIn(STANDARD_TRANSITION_TIME)])
    round_text_clip = TextClip(font=FONT_PATH, text=round_text, font_size=round_font_size, color=text_color).with_position(("center", 0.4), relative=True).with_start(STANDARD_TRANSITION_TIME * 2).with_duration(TOTAL_DURATION - STANDARD_TRANSITION_TIME * 2)
    return header_text_clip, sub_header_text_clip, round_text_fade_in_clip, round_text_clip

def create_simple_opening_screen(output_directory, game):
    home_team = game["home_team"]
    away_team = game["away_team"]
    home_team_logo_path = game["home_team_logo_path"]
    away_team_logo_path = game["away_team_logo_path"]
    home_team_match_score = "0-0-0"
    away_team_match_score = "0-0-0"
    vs_text = "vs"
    
    output_path = f"{output_directory}/{format_team_name_for_filename(home_team)}_vs_{format_team_name_for_filename(away_team)}_opening_screen.mp4"

    background_color =  (0, 0, 255) #Dark blue
    text_color = (255, 255, 255)

    color_background = ColorClip(size=(1920, 1080), color=background_color, duration=TOTAL_DURATION)
    header_text = HEADER_TEXT
    sub_header_text = SUBHEADER_TEXT
    round_text = f"Round Robin Round {game['round']}"

    header_text_clip, sub_header_text_clip, round_text_fade_in_clip, round_text_clip = create_header_text_clips(header_text, sub_header_text, round_text, text_color)

    home_team_logo_clip, home_team_name_clip, home_team_match_score_clip = create_team_clip(home_team, home_team_match_score, home_team_logo_path, text_color, side="left", start_time=STANDARD_TRANSITION_TIME)
    away_team_logo_clip, away_team_name_clip, away_team_match_score_clip = create_team_clip(away_team, away_team_match_score, away_team_logo_path, text_color, side="right", start_time=STANDARD_TRANSITION_TIME)

    vs_clip = TextClip(font=FONT_PATH, text=vs_text, font_size=TEAM_NAME_MIN_FONT_SIZE, color=text_color).with_position((0.5, 0.65), relative=True).with_start(STANDARD_TRANSITION_TIME).with_duration(TOTAL_DURATION - STANDARD_TRANSITION_TIME)

    opening_screen = CompositeVideoClip([
        color_background, 
        header_text_clip, 
        sub_header_text_clip,
        round_text_fade_in_clip,
        round_text_clip,
        home_team_logo_clip,
        away_team_logo_clip,
        home_team_name_clip,
        away_team_name_clip,
        home_team_match_score_clip,
        away_team_match_score_clip,
        vs_clip
        ])
    opening_screen.write_videofile(output_path, codec="libx264", fps=24)

def create_ending_screen(output_directory, game):
    background_color =  (0, 0, 255) #Dark blue
    text_color = (255, 255, 255)

    color_background = ColorClip(size=(1920, 1080), color=background_color, duration=TOTAL_DURATION)

    home_team = game["home_team"]
    away_team = game["away_team"]
    home_team_logo_path = game["home_team_logo_path"]
    away_team_logo_path = game["away_team_logo_path"]
    home_team_match_score_start = "0-0-0" # Might be needed once we have dynamic scores
    away_team_match_score_start = "0-0-0"
    home_team_game_score = "1" # This will be dynamic
    away_team_game_score = "2" # This will be dynamic
    home_team_match_score_end = "0-1-0" # This will be dynamic
    away_team_match_score_end = "1-0-0" # This will be dynamic

    final_score_text = f"Final Score: {home_team} {home_team_game_score} - {away_team_game_score} {away_team}"
     
    header_text_clip, sub_header_text_clip, final_score_fade_in_clip, final_score_clip = create_header_text_clips(HEADER_TEXT, SUBHEADER_TEXT, final_score_text, text_color)

    home_team_logo_clip_start, home_team_name_clip_start, home_team_match_score_clip_start = create_team_clip(home_team, home_team_match_score_end, home_team_logo_path, text_color, side="left", start_time=STANDARD_TRANSITION_TIME)
    away_team_logo_clip_start, away_team_name_clip_start, away_team_match_score_clip_start = create_team_clip(away_team, away_team_match_score_end, away_team_logo_path, text_color, side="right", start_time=STANDARD_TRANSITION_TIME * 2)

    closing_screen = CompositeVideoClip([
        color_background, 
        header_text_clip, 
        sub_header_text_clip,
        final_score_fade_in_clip,
        final_score_clip,
        home_team_logo_clip_start,
        away_team_logo_clip_start,
        home_team_name_clip_start,
        away_team_name_clip_start,
        home_team_match_score_clip_start,
        away_team_match_score_clip_start,
        ])
    closing_screen.write_videofile(f"{output_directory}/{format_team_name_for_filename(home_team)}_vs_{format_team_name_for_filename(away_team)}_closing_screen.mp4", codec="libx264", fps=24)


    

def process_game(output_path, game):
    create_simple_opening_screen(output_path, game)
    # add_team_name_to_video(game["video_path"], game["home_team"], game["away_team"])
    create_ending_screen(output_path, game)


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


    # Pick one random game of the 10 for testing
    random_game_number = math.floor(random.random() * 10)
    games = [games[random_game_number]]
    run(output_path, games)