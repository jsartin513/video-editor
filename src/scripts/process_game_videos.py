import json
import math
import random
from moviepy import *
import numpy as np

import argparse

from utils.utils import log, format_team_name_for_filename
from utils.moviepy import function_for_position
from utils.files import concatenate_mp4_files, trim_mp4_file


FONT_PATH = "./font/font.ttf"

# BDL_LOGO_PATH = "src/static/grayscale_bdl_logo.png"
BDL_LOGO_PATH = "src/static/bdl_rectangle_logo.png"

LOGO_ICON_MAX_WIDTH = 180
LOGO_ICON_MIN_WIDTH = 120
TEAM_NAME_MAX_FONT_SIZE = 72
TEAM_NAME_MIN_FONT_SIZE = 36
LOGO_ICON_IN_GAME_WIDTH = 100
TEAM_NAME_IN_GAME_FONT_SIZE = 24  

STARTING_LOGO_POSITION = (0.11, 0.2)
STARTING_TEAM_NAME_POSITION = (0.205, 0.25)

ENDING_AWAY_TEAM_LOGO_POSITION = (0.5, 0.8)
ENDING_HOME_TEAM_LOGO_POSITION = (0.11, 0.8)
ENDING_AWAY_TEAM_NAME_POSITION = (0.55, 0.8)
ENDING_HOME_TEAM_NAME_POSITION = (0.205, 0.8)

OPENING_SCREEN_DURATION = 8
STANDARD_TRANSITION_TIME = 1

BLUE_COLOR = (65,143,222)
GOLD_COLOR = (253,218,36)

HEADER_TEXT = "Boston Dodgeball League"
SUBHEADER_TEXT = "The Throw Down 3"



def add_bdl_watermark(video_file_clip):
    bdl_logo = ImageClip(BDL_LOGO_PATH).resize(height=100).with_duration(video_file_clip.duration)
    video_with_watermark = CompositeVideoClip([video_file_clip, bdl_logo.set_position(("right", "bottom"))])
    return video_with_watermark


# Create a circular mask
def get_circular_mask():
    center_x, center_y = LOGO_ICON_MAX_WIDTH // 2, LOGO_ICON_MAX_WIDTH // 2
    width, height = LOGO_ICON_MAX_WIDTH, LOGO_ICON_MAX_WIDTH
    radius = min(width, height) // 2
    mask = np.zeros((height, width)) 
    x, y = np.ogrid[:height, :width]
    mask[(x - center_y)**2 + (y - center_x)**2 <= radius**2] = 1  
    return mask



# This is going to have static information about this tournament
def get_bdl_tournament_banner():
    text = "Boston Dodgeball League presents The Throw Down 3 - February 22, 2025"
    banner = (
        TextClip(font=FONT_PATH, text=text, size=(1920, 24))
        .with_position(("center", "top")).with_duration(OPENING_SCREEN_DURATION)
    )
    return banner


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
        TextClip(font=FONT_PATH, text=team_name, font_size=TEAM_NAME_MAX_FONT_SIZE, color="black", duration=OPENING_SCREEN_DURATION - final_position_start)
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
        .with_mask(circular_mask)
        .with_position(STARTING_LOGO_POSITION, relative=True).with_effects([vfx.CrossFadeIn(STANDARD_TRANSITION_TIME)]).with_start(fade_in_clip_start)
    )
    logo_clip_moving = (
        ImageClip(logo_path, duration=STANDARD_TRANSITION_TIME).resized(width=LOGO_ICON_MAX_WIDTH)
        .with_mask(circular_mask)
        .with_position(lambda t: function_for_position(t, STARTING_LOGO_POSITION, ending_logo_position), relative=True).with_start(moving_clip_start)
    )
    logo_clip_final_position = (
        ImageClip(logo_path, duration=OPENING_SCREEN_DURATION - final_position_start).resized(width=LOGO_ICON_MAX_WIDTH)
        .with_mask(circular_mask)
        .with_position(ending_logo_position, relative=True).with_start(final_position_start)
    )
    return logo_clip_fade_in, logo_clip_moving, logo_clip_final_position

def get_team_name_and_logo_for_video_overlay(team_name, logo_path, duration):
    logo_clip = (
        ImageClip(logo_path, duration=duration).resized(width=LOGO_ICON_IN_GAME_WIDTH).with_layer_index(15)
    )
    team_name_clip = (
        TextClip(font=FONT_PATH, text=team_name, font_size=TEAM_NAME_IN_GAME_FONT_SIZE, color="white", bg_color="black").with_layer_index(15)
    )
    return logo_clip, team_name_clip


# @param start_time: When to begin playing this clip in the final video, after any intros
# @param game: The game object with all the information about the game
# @param trim_time: How much time to trim from the beginning of the game video
# @return: A video clip with the game video, includign merged clips, and overlay information
def get_game_video_with_overlay(game, start_time, trim_time=0, end_trim_time=0):
    game_video_paths = game["video_path"]
    game_start_time = start_time
    videos_with_overlay = []

    for path in game_video_paths:
        if trim_time > 0:
            game_video = VideoFileClip(path).subclipped(trim_time).with_start(game_start_time).with_layer_index(10) # End time is just for testing this one
            trim_time = 0
        else:
            game_video = VideoFileClip(path).with_layer_index(10)
        game_duration = game_video.duration
    
        home_team_logo_clip, home_team_name_clip = get_team_name_and_logo_for_video_overlay(game["home_team"], game["home_team_logo_path"], game_duration)
        away_team_logo_clip, away_team_name_clip = get_team_name_and_logo_for_video_overlay(game["away_team"], game["away_team_logo_path"], game_duration)

        team_info_panel = clips_array([[home_team_logo_clip, home_team_name_clip], [away_team_logo_clip, away_team_name_clip]], bg_color=(0, 0, 0)).with_layer_index(15).with_position(("right", "center")).with_duration(game_duration)

        video_with_overlay = CompositeVideoClip([game_video, team_info_panel])

        videos_with_overlay.append(video_with_overlay)

    if end_trim_time > 0:
        videos_with_overlay[-1] = videos_with_overlay[-1].subclipped(0, end_trim_time)

    compiled_game_video = concatenate_videoclips(videos_with_overlay)
    return compiled_game_video
    

# Create opening screen with "standard" transitions using the variables described above
def create_opening_screen(output_directory, game):
    home_team = game["home_team"]
    away_team = game["away_team"]
    home_team_logo_path = game["home_team_logo_path"]
    away_team_logo_path = game["away_team_logo_path"]

    background_image = ImageClip(BDL_LOGO_PATH).with_duration(OPENING_SCREEN_DURATION)


    # tournament_banner = get_bdl_tournament_banner()
    home_team_logo_clip_fade_in, home_team_logo_clip_moving, home_team_logo_final_position = get_logo_clips(home_team_logo_path, ENDING_HOME_TEAM_LOGO_POSITION)
    home_team_clip_fade_in, home_team_clip_moving, home_team_clip_final_position = get_name_clips(home_team, STARTING_TEAM_NAME_POSITION, ENDING_HOME_TEAM_NAME_POSITION)
    away_team_logo_clip_fade_in, away_team_logo_clip_moving, away_team_logo_final_position = get_logo_clips(away_team_logo_path, ENDING_AWAY_TEAM_LOGO_POSITION, STANDARD_TRANSITION_TIME)
    away_team_clip_fade_in, away_team_clip_moving, away_team_clip_final_position = get_name_clips(away_team, STARTING_TEAM_NAME_POSITION, ENDING_AWAY_TEAM_NAME_POSITION, STANDARD_TRANSITION_TIME)
 
    opening_screen = CompositeVideoClip([
        background_image,
        # tournament_banner,
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
    # opening_screen.write_videofile(output_path, codec="libx264", fps=24)
    return opening_screen

def create_team_clip(team_name, logo_path, text_color, side="left", start_time=0):
    duration = OPENING_SCREEN_DURATION - start_time
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
        .with_mask(circular_mask)
        .with_effects([vfx.CrossFadeIn(STANDARD_TRANSITION_TIME)]).with_start(start_time)
    )
    team_name_clip = (
        TextClip(font=FONT_PATH, text=f"  {team_name}  ", font_size=TEAM_NAME_MIN_FONT_SIZE, color=text_color)
        .with_duration(duration)
        .with_effects([vfx.CrossFadeIn(STANDARD_TRANSITION_TIME)]).with_start(start_time)
    )
    return logo_clip, team_name_clip

def create_final_team_with_score_clip(team_name, game_score, logo_path, text_color, side="left", start_time=0):
    duration = OPENING_SCREEN_DURATION - start_time
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
        .with_mask(circular_mask)
    )
    team_name_clip = (
        TextClip(font=FONT_PATH, text=f"  {team_name}  ", font_size=TEAM_NAME_MIN_FONT_SIZE, color=text_color, duration=duration)
    )
    game_score_clip = (
        TextClip(font=FONT_PATH, text=f"  {game_score}  ", font_size=TEAM_NAME_MIN_FONT_SIZE, color=text_color, duration=duration)
    )
    return logo_clip, team_name_clip, game_score_clip

def create_header_text_clips(header_text, subheader_text, round_text, text_color):
    header_font_size = 72
    subheader_font_size = 60
    round_font_size = 48

    bdl_logo_clip = ImageClip(BDL_LOGO_PATH).resized(height=150).with_duration(OPENING_SCREEN_DURATION).with_position((.1, .2), relative=True)

    header_text_clip = TextClip(font=FONT_PATH, text=header_text, font_size=header_font_size, color=text_color).with_position(("center", 0.2), relative=True).with_duration(OPENING_SCREEN_DURATION)
    sub_header_text_clip = TextClip(font=FONT_PATH, text=subheader_text, font_size=subheader_font_size, color=text_color).with_position(("center", 0.3), relative=True).with_duration(OPENING_SCREEN_DURATION)
    round_text_fade_in_clip = TextClip(font=FONT_PATH, text=round_text, font_size=round_font_size, color=text_color).with_position(("center", 0.4), relative=True).with_duration(STANDARD_TRANSITION_TIME).with_start(STANDARD_TRANSITION_TIME).with_effects([vfx.CrossFadeIn(STANDARD_TRANSITION_TIME)])
    round_text_clip = TextClip(font=FONT_PATH, text=round_text, font_size=round_font_size, color=text_color).with_position(("center", 0.4), relative=True).with_start(STANDARD_TRANSITION_TIME * 2).with_duration(OPENING_SCREEN_DURATION - STANDARD_TRANSITION_TIME * 2)
    return bdl_logo_clip, header_text_clip, sub_header_text_clip, round_text_fade_in_clip, round_text_clip

def create_simple_opening_screen(game):
    home_team = game["home_team"]
    away_team = game["away_team"]
    home_team_logo_path = game["home_team_logo_path"]
    away_team_logo_path = game["away_team_logo_path"]
    home_team_match_score = "0-0-0"
    away_team_match_score = "0-0-0"
    vs_text = "  vs  "
    
    background_color =  BLUE_COLOR #Dark blue
    text_color = GOLD_COLOR

    color_background = ColorClip(size=(1920, 1080), color=background_color, duration=OPENING_SCREEN_DURATION - STANDARD_TRANSITION_TIME)
    header_text = HEADER_TEXT
    sub_header_text = SUBHEADER_TEXT
    round_text = f"Round Robin Round {game['round']}"

    bdl_logo_clip, header_text_clip, sub_header_text_clip, round_text_fade_in_clip, round_text_clip = create_header_text_clips(header_text, sub_header_text, round_text, text_color)

    home_team_logo_clip, home_team_name_clip = create_team_clip(home_team, home_team_logo_path, text_color, side="left", start_time=STANDARD_TRANSITION_TIME)
    away_team_logo_clip, away_team_name_clip = create_team_clip(away_team, away_team_logo_path, text_color, side="right", start_time=STANDARD_TRANSITION_TIME)

    vs_clip = TextClip(font=FONT_PATH, text=vs_text, font_size=TEAM_NAME_MIN_FONT_SIZE, color=text_color).with_start(STANDARD_TRANSITION_TIME).with_duration(OPENING_SCREEN_DURATION)

    starting_clip = clips_array([[home_team_logo_clip, home_team_name_clip, vs_clip, away_team_name_clip, away_team_logo_clip]]).with_position(("center", 0.65), relative=True).with_duration(OPENING_SCREEN_DURATION)

    opening_screen = CompositeVideoClip([
        color_background, 
        bdl_logo_clip, 
        header_text_clip, 
        sub_header_text_clip,
        round_text_fade_in_clip,
        round_text_clip,
        starting_clip
        ]).with_layer_index(20)
    return opening_screen

def create_ending_screen(game):
    background_color =  BLUE_COLOR #Dark blue
    text_color = GOLD_COLOR

    color_background = ColorClip(size=(1920, 1080), color=background_color, duration=OPENING_SCREEN_DURATION)

    home_team = game["home_team"]
    away_team = game["away_team"]
    home_team_logo_path = game["home_team_logo_path"]
    away_team_logo_path = game["away_team_logo_path"]
    home_team_match_score_start = "0-0-0" # Might be needed once we have dynamic scores
    away_team_match_score_start = "0-0-0"
    home_team_game_score = game["home_team_score"]
    away_team_game_score = game["away_team_score"]
    home_team_match_score_end = "0-1-0" # This will be dynamic
    away_team_match_score_end = "1-0-0" # This will be dynamic

    final_score_text = f"  {home_team_game_score} - {away_team_game_score}  "
     
    bdl_logo_clip, header_text_clip, sub_header_text_clip, final_score_fade_in_clip, final_score_clip = create_header_text_clips(HEADER_TEXT, SUBHEADER_TEXT, "", text_color)
 
    final_score_clip = TextClip(font=FONT_PATH, text=final_score_text, font_size=TEAM_NAME_MIN_FONT_SIZE, color=text_color)
    home_team_logo_clip_start, home_team_name_clip_start, home_game_score_clip = create_final_team_with_score_clip(home_team, home_team_game_score, home_team_logo_path, text_color)
    away_team_logo_clip_start, away_team_name_clip_start, away_game_score_clip = create_final_team_with_score_clip(away_team, away_team_game_score, away_team_logo_path, text_color)

    scores_clip = clips_array([[home_team_logo_clip_start, home_team_name_clip_start, final_score_clip, away_team_name_clip_start, away_team_logo_clip_start],
                               ]
                               ).with_position(("center", "center")).with_duration(OPENING_SCREEN_DURATION - STANDARD_TRANSITION_TIME * 2).with_start(STANDARD_TRANSITION_TIME * 2)

    closing_screen = CompositeVideoClip([
        color_background, 
        bdl_logo_clip,
        header_text_clip, 
        sub_header_text_clip,
        scores_clip,
        ])
    return closing_screen


    
# Returns an ordered list of filenames, including opening screen, game videos, and closing screen
def process_game(output_path, game):
    home_team = game["home_team"]
    away_team = game["away_team"]
    formatted_home_team = format_team_name_for_filename(home_team)
    formatted_away_team = format_team_name_for_filename(away_team)


    game_path_list = game["video_path"]
    first_game_path = game_path_list[0]
    last_game_path = game_path_list[-1]

    trim_time = game.get("trim_time", 0)
    end_trim_time = game.get("end_trim_time", 0)


    game_start_time = OPENING_SCREEN_DURATION - STANDARD_TRANSITION_TIME
    transition_end_time = game_start_time
    trim_time = trim_time - transition_end_time # Adjust the trim time to account for the transition time
    # game_video = get_game_video_with_overlay(game, 0, trim_time) # Original video - later it'll have team info

    original_opening_video_duration = VideoFileClip(first_game_path).duration

    # First ten seconds of game video to go under the opening screen
    opening_screen_game_video = VideoFileClip(first_game_path).subclipped(trim_time, trim_time + OPENING_SCREEN_DURATION).with_start(0).with_layer_index(10)

    end_duration = OPENING_SCREEN_DURATION + end_trim_time
    # Last ten seconds of game video to go under the closing screen
    closing_screen_game_video = VideoFileClip(last_game_path).subclipped(-end_duration, end_trim_time).with_start(0).with_layer_index(10)

    
    # Get some info about the game video so we can apply it to the opening and closing screens
    game_video_size = opening_screen_game_video.size
    game_video_fps = opening_screen_game_video.fps
    # game_video_duration = game_video.duration
    # trimmed_game_video_duration = game_video_duration - OPENING_SCREEN_DURATION



    opening_screen_filename = f"{output_path}/{formatted_home_team}_vs_{formatted_away_team}_opening_screen.mp4"
    closing_screen_filename = f"{output_path}/{formatted_home_team}_vs_{formatted_away_team}_closing_screen.mp4"

    opening_screen = create_simple_opening_screen(game).with_effects([vfx.SlideOut(STANDARD_TRANSITION_TIME, "top")]).resized((game_video_size))
    closing_screen = create_ending_screen(game).with_effects([vfx.CrossFadeIn(STANDARD_TRANSITION_TIME)]).resized((game_video_size)).with_layer_index(20)


    full_opening_screen = CompositeVideoClip([opening_screen, opening_screen_game_video]).with_duration(OPENING_SCREEN_DURATION)
    full_closing_screen = CompositeVideoClip([closing_screen_game_video, closing_screen]).with_duration(OPENING_SCREEN_DURATION)
    # full_video = CompositeVideoClip([opening_screen, game_video, closing_screen])
    # full_video.write_videofile(f"{output_path}/{formatted_home_team}_vs_{formatted_away_team}_full.mp4", codec="libx264", fps=24, audio=True, audio_codec="aac", temp_audiofile="temp-audio.m4a")

    log(f"Game video details: {game}")
    log(f"Game video size: {game_video_size}")
    # log(f"Final video details: {full_video}")
    # log(f"Final video width: {full_video.size[0]}")
    # log(f"Final video height: {full_video.size[1]}")
    # log(f"Final video duration: {full_video.duration}")
    # log(f"Final video fps: {full_video.fps}")

    full_opening_screen.write_videofile(opening_screen_filename, codec="libx264", fps=24)

    full_closing_screen.write_videofile(closing_screen_filename, codec="libx264", fps=24)


    # We want to concatenate all of the videos together. 
    # We must trim the first and last videos to match up with the opening and closing screens.
    # Any other videos can be concatenated as is.

    first_video_filename = f"{output_path}/{formatted_home_team}_vs_{formatted_away_team}_trimmed_first_game.mp4"
    last_video_filename = f"{output_path}/{formatted_home_team}_vs_{formatted_away_team}_trimmed_last_game.mp4"



    # Trim the first and last videos
    trim_mp4_file(first_game_path, trim_time + OPENING_SCREEN_DURATION, original_opening_video_duration, first_video_filename)
    
    end_file_trim_time = closing_screen_game_video.duration - end_trim_time
    trim_mp4_file(last_game_path, 0, end_file_trim_time, last_video_filename)


    concatenaed_filename = f"{output_path}/{formatted_home_team}_vs_{formatted_away_team}_concatenaed.mp4"
    #Just for today, I know these are the only two videos in the list
    # Concatenate all the videos together
    concatenate_mp4_files([opening_screen_filename, first_video_filename, last_video_filename, closing_screen_filename], concatenaed_filename)

    return concatenaed_filename

def run(output_path, games):
    for game in games:
        log(f"Processing game at {game['video_path']}")
        # Create opening and closing screens
        concatenaed_filename =  process_game(output_path, game)
        log(f"Game video processed at {concatenaed_filename}")
        


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Handle tournament videos.')
    parser.add_argument('directory_name', type=str, help='The name of the directory containing the videos')
    args = parser.parse_args()

    output_path = f"{args.directory_name}/processed_videos"
    metadata_path = f"{output_path}/metadata.json"

    with open(metadata_path, "r") as f:
        games = json.load(f)


    # Pick one random game of the 10 for testing
    # random_game_number = math.floor(random.random() * 10)
    # random_game_number = 6
    # del games[random_game_number] # For second run, bc we already ran it once
    # games = [games[random_game_number]]
    run(output_path, games)