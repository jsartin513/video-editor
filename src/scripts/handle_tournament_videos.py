import argparse
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

# Create a circular mask
def get_circular_mask():
    center_x, center_y = LOGO_ICON_MAX_WIDTH // 2, LOGO_ICON_MAX_WIDTH // 2
    width, height = LOGO_ICON_MAX_WIDTH, LOGO_ICON_MAX_WIDTH
    radius = min(width, height) // 2
    mask = np.zeros((height, width)) 
    x, y = np.ogrid[:height, :width]
    mask[(x - center_y)**2 + (y - center_x)**2 <= radius**2] = 1  
    return mask

LOGO_ICON_MAX_WIDTH = 180
TEAM_NAME_MAX_FONT_SIZE = 72
STARTING_LOGO_POSITION = (0.11, 0.2)
STARTING_TEAM_NAME_POSITION = (0.205, 0.25)

ENDING_AWAY_TEAM_LOGO_POSITION = (0.5, 0.8)
ENDING_HOME_TEAM_LOGO_POSITION = (0.11, 0.8)
ENDING_AWAY_TEAM_NAME_POSITION = (0.55, 0.8)
ENDING_HOME_TEAM_NAME_POSITION = (0.205, 0.8)

TOTAL_DURATION = 15
STANDARD_TRANSITION_TIME = 3

# Create a function that takes in a time t and returns the position of an object moving from start_position to end_position
def function_for_position(t, start_position, end_position, clip_duration=STANDARD_TRANSITION_TIME):
    x_start_position, y_start_position = start_position
    x_end_position, y_end_position = end_position
    x_distance = x_end_position - x_start_position
    y_distance = y_end_position - y_start_position

    return (x_start_position + x_distance * t / clip_duration, y_start_position + y_distance * t / clip_duration)

def get_home_team_logo_clips(home_team_logo_path):
    final_position_start = STANDARD_TRANSITION_TIME * 2
    circular_mask = ImageClip(get_circular_mask(), is_mask=True)
    home_team_logo_clip_fade_in = (
        ImageClip(home_team_logo_path, duration=STANDARD_TRANSITION_TIME).resized(width=LOGO_ICON_MAX_WIDTH)
        .with_mask(circular_mask).with_position(STARTING_LOGO_POSITION, relative=True).with_effects([vfx.CrossFadeIn(STANDARD_TRANSITION_TIME)])
    )
    home_team_logo_clip_moving = (
        ImageClip(home_team_logo_path, duration=STANDARD_TRANSITION_TIME).resized(width=LOGO_ICON_MAX_WIDTH)
        .with_mask(circular_mask).with_position(lambda t: function_for_position(t, STARTING_LOGO_POSITION, ENDING_HOME_TEAM_LOGO_POSITION), relative=True).with_start(STANDARD_TRANSITION_TIME)
    )
    home_team_logo_final_position = (
        ImageClip(home_team_logo_path, duration=TOTAL_DURATION - final_position_start).resized(width=LOGO_ICON_MAX_WIDTH)
        .with_mask(circular_mask).with_position(ENDING_HOME_TEAM_LOGO_POSITION, relative=True).with_start(final_position_start)
        )
    return home_team_logo_clip_fade_in, home_team_logo_clip_moving, home_team_logo_final_position

def get_home_team_name_clips(home_team_name):
    final_position_start = STANDARD_TRANSITION_TIME * 2
    home_team_clip_fade_in = (
        TextClip(font=FONT_PATH, text=home_team_name, font_size=TEAM_NAME_MAX_FONT_SIZE, color="black", duration=STANDARD_TRANSITION_TIME)
        .with_position(STARTING_TEAM_NAME_POSITION, relative=True).with_effects([vfx.CrossFadeIn(STANDARD_TRANSITION_TIME)])
    )
    home_team_clip_moving = (
        TextClip(font=FONT_PATH, text=home_team_name, font_size=TEAM_NAME_MAX_FONT_SIZE, color="black", duration=STANDARD_TRANSITION_TIME)
        .with_position(lambda t: function_for_position(t, STARTING_TEAM_NAME_POSITION, ENDING_HOME_TEAM_NAME_POSITION), relative=True).with_start(STANDARD_TRANSITION_TIME)
    )
    home_team_clip_final_position = (
        TextClip(font=FONT_PATH, text=home_team_name, font_size=TEAM_NAME_MAX_FONT_SIZE, color="black", duration=final_position_start)
        .with_position(ENDING_HOME_TEAM_NAME_POSITION, relative=True).with_start(final_position_start)
    )
    return home_team_clip_fade_in, home_team_clip_moving, home_team_clip_final_position

def get_away_team_logo_clips(away_team_logo_path):
    final_position_start = STANDARD_TRANSITION_TIME * 3
    circular_mask = ImageClip(get_circular_mask(), is_mask=True)
    away_team_logo_clip_fade_in = (
        ImageClip(away_team_logo_path, duration=STANDARD_TRANSITION_TIME).resized(width=LOGO_ICON_MAX_WIDTH)
        .with_mask(circular_mask).with_position(STARTING_LOGO_POSITION, relative=True).with_effects([vfx.CrossFadeIn(STANDARD_TRANSITION_TIME)]).with_start(STANDARD_TRANSITION_TIME)
    )
    away_team_logo_clip_moving = (
        ImageClip(away_team_logo_path, duration=STANDARD_TRANSITION_TIME).resized(width=LOGO_ICON_MAX_WIDTH)
        .with_mask(circular_mask).with_position(lambda t: function_for_position(t, STARTING_LOGO_POSITION, ENDING_AWAY_TEAM_LOGO_POSITION), relative=True).with_start(STANDARD_TRANSITION_TIME * 2)
    )
    away_team_logo_final_position = (
        ImageClip(away_team_logo_path, duration=TOTAL_DURATION - final_position_start).resized(width=LOGO_ICON_MAX_WIDTH)
        .with_mask(circular_mask).with_position(ENDING_AWAY_TEAM_LOGO_POSITION, relative=True).with_start(final_position_start)
    )
    return away_team_logo_clip_fade_in, away_team_logo_clip_moving, away_team_logo_final_position

def get_away_team_name_clips(away_team_name):
    away_team_clip_fade_in = (
        TextClip(font=FONT_PATH, text=away_team_name, font_size=TEAM_NAME_MAX_FONT_SIZE, color="black", duration=STANDARD_TRANSITION_TIME)
        .with_position(STARTING_TEAM_NAME_POSITION, relative=True).with_effects([vfx.CrossFadeIn(STANDARD_TRANSITION_TIME)]).with_start(STANDARD_TRANSITION_TIME)
    )
    away_team_clip_moving = (
        TextClip(font=FONT_PATH, text=away_team_name, font_size=TEAM_NAME_MAX_FONT_SIZE, color="black", duration=STANDARD_TRANSITION_TIME)
        .with_position(lambda t: function_for_position(t, STARTING_TEAM_NAME_POSITION, ENDING_AWAY_TEAM_NAME_POSITION), relative=True).with_start(STANDARD_TRANSITION_TIME * 2)
    )
    away_team_clip_final_position = (
        TextClip(font=FONT_PATH, text=away_team_name, font_size=TEAM_NAME_MAX_FONT_SIZE, color="black", duration=TOTAL_DURATION - STANDARD_TRANSITION_TIME * 3)
        .with_position(ENDING_AWAY_TEAM_NAME_POSITION, relative=True).with_start(STANDARD_TRANSITION_TIME * 3)
    )
    return away_team_clip_fade_in, away_team_clip_moving, away_team_clip_final_position

# This is going to have static information about this tournament
def get_bdl_tournament_banner():
    text = "Boston Dodgeball League presents The Throw Down 3 - February 22, 2025"
    banner = (
        TextClip(font=FONT_PATH, text=text, size=(1920, 24))
        .with_position(("center", "top")).with_duration(TOTAL_DURATION)
    )
    return banner

# Create opening screen with "standard" transitions using the variables described above
def create_opening_screen(output_directory, game):
    home_team = game["home_team"]
    away_team = game["away_team"]
    home_team_logo_path = game["home_team_logo_path"]
    away_team_logo_path = game["away_team_logo_path"]
    output_path = f"{output_directory}/{format_team_name_for_filename(home_team)}_vs_{format_team_name_for_filename(away_team)}_opening_screen.mp4"

    background_image = ImageClip("src/static/bdl_rectangle_logo.png").with_duration(TOTAL_DURATION)
    
    tournament_banner = get_bdl_tournament_banner()
    home_team_logo_clip_fade_in, home_team_logo_clip_moving, home_team_logo_final_position = get_home_team_logo_clips(home_team_logo_path)
    home_team_clip_fade_in, home_team_clip_moving, home_team_clip_final_position = get_home_team_name_clips(home_team)
    away_team_logo_clip_fade_in, away_team_logo_clip_moving, away_team_logo_final_position = get_away_team_logo_clips(away_team_logo_path)
    away_team_clip_fade_in, away_team_clip_moving, away_team_clip_final_position = get_away_team_name_clips(away_team)
 
    opening_screen = CompositeVideoClip([
        background_image,tournament_banner,  home_team_clip_fade_in, home_team_clip_moving, home_team_logo_clip_fade_in, home_team_logo_clip_moving, home_team_logo_final_position, 
        home_team_clip_final_position, 
        away_team_logo_clip_fade_in, away_team_logo_clip_moving, away_team_logo_final_position, away_team_clip_fade_in, away_team_clip_moving, away_team_clip_final_position])
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
        log(f"Copied {video} to {new_video_path}")
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

    # video_paths =rename_videos(args.directory_name, ordered_games)
    output_path = f"{args.directory_name}/processed_videos/opening_screens"

    # if not os.path.exists(output_path):
    #     os.makedirs(output_path)


    # for game in ordered_games:
    #     create_opening_screen(output_path, game)
    create_opening_screen(output_path, ordered_games[0])
    
    # log(f"Ordered teams: {ordered_teams}")

    # run(directory_name, ordered_teams)
