import argparse
import json
import os
import subprocess

from utils.google_sheet_reader import get_parsed_bracket
from utils.files import get_video_length, concatenate_mp4_files, trim_mp4_file, list_files_of_type_sorted_by_date
from utils.utils import log, format_team_name_for_filename


GAME_TIMES =[
    {"round": "1", "start_seconds": 540, "video_file": "GX020146.MP4", "round_length_in_seconds": 1080},
]

GAMES=[
# {'away_team': 'Plank',
#   'court': 'court 3 ',
#   'home_team': "Shogun's Shadows",
#   'round': 'Round 1',
#   'subround': 'second series', "start_seconds": 400, "video_file": "GX040146.MP4", "round_length_in_seconds": 1080},
 {'away_team': 'Scooby Snacks',
  'court': 'court 2 ',
  'home_team': 'The Powerpuff Girls',
  'round': 'Round 1',
  'subround': 'first series'},
 {'away_team': 'Secret Lab Syndicate',
  'court': 'court 2 ',
  'home_team': 'Imaginary Friends',
  'round': 'Round 1',
  'subround': 'second series'},
#  {'away_team': 'Kids Next Door',
#   'court': 'court 3 ',
#   'home_team': 'Boston T Titans',
#   'round': 'Round 1',
#   'subround': 'first series', "start_seconds": 540, "video_file": "GX020146.MP4", "round_length_in_seconds": 1080},
 {'away_team': 'Plank',
  'court': 'court 2 ',
  'home_team': "Grim's Reapers",
  'round': 'Quarters',
  'subround': 'second series'},
 {'away_team': 'The Powerpuff Girls',
  'court': 'court 2 ',
  'home_team': 'Totally Spies',
  'round': 'Quarters',
  'subround': 'first series'},
#  {'away_team': 'Secret Lab Syndicate',
#   'court': 'court 3 ',
#   'home_team': "Courage's Crusaders",
#   'round': 'Quarters',
#   'subround': 'second series', "round_length_in_seconds": 1080, "start_seconds":140, "video_file": "GX010148.MP4"},
#  {'away_team': 'Boston T Titans',
#   'court': 'court 3 ',
#   'home_team': 'Dodge This, Mama',
#   'round': 'Quarters',
#   'subround': 'first series', "round_length_in_seconds": 1180, "start_seconds": 180, "video_file": "GX010147.MP4"},
#  {'away_team': 'Totally Spies',
#   'court': 'court 3',
#   'home_team': 'Plank',
#   'round': 'Semis',
#   'subround': None, "start_seconds": 90, "video_file": "GX010149.MP4", "round_length_in_seconds": 1700},
 {'away_team': 'Dodge This, Mama',
  'court': 'court 2',
  'home_team': 'Secret Lab Syndicate',
  'round': 'Semis',
  'subround': None},
 {'away_team': 'Dodge This, Mama',
  'court': 'court 2',
  'home_team': 'Totally Spies',
  'round': 'Finals',
  'subround': 'Championship'},
 {'away_team': 'Plank', # The camera fell - also needs to be processed with rotation if possible
  'court': 'court 3',
  'home_team': 'Secret Lab Syndicate',
  'round': 'Finals',
  'subround': 'Third Place', "start_seconds": 220, "video_file": "GX010150.MP4", "round_length_in_seconds": 1700},
  ]

COURT_3_DIRECTORY = "/Users/MrsHazmat/throw_down_3_recordings/court_3_playoffs"
COURT_2_DIRECTORY = "/Users/MrsHazmat/throw_down_3_recordings/court_2_playoffs"




def create_playoff_game_videos(games, directory):
    all_files = list_files_of_type_sorted_by_date(directory)
    log(f"all_files: {all_files}")

    for game in games:
        log(f"Game: {game}")
        start_seconds = game.get("start_seconds", 0)
        round_length = game.get("round_length_in_seconds", 1800)
        output_filename = os.path.join(directory, f"{game['round']}: {game['court']}: {format_team_name_for_filename(game['home_team'])}_{format_team_name_for_filename(game['away_team'])}.mp4")

        current_length = 0
        current_file_index = all_files.index(game["video_file"])
        files_to_concatenate = []

        while current_length < round_length and current_file_index < len(all_files):
            log(f"current_length: {current_length}")
            log(f"current_file_index: {current_file_index}")
            log(f"Round length: {round_length}")
            current_file = all_files[current_file_index]
            current_file_path = os.path.join(directory, current_file)
            video_length = get_video_length(current_file_path)

            if current_length == 0:
                temp_output = os.path.join(directory, f"temp_{current_file_index}.mp4")
                trimmed_length = min(video_length - start_seconds, round_length)
                end_time = start_seconds + trimmed_length
                trim_mp4_file(current_file_path, start_seconds, end_time, temp_output)
                files_to_concatenate.append(temp_output)
                current_length += trimmed_length
            else:
                temp_output = os.path.join(directory, f"temp_{current_file_index}.mp4")
                trimmed_length = min(video_length, round_length - current_length)
                end_time = start_seconds + trimmed_length
                trim_mp4_file(current_file_path, 0, end_time, temp_output)
                files_to_concatenate.append(temp_output)
                current_length += trimmed_length

            current_file_index += 1
            start_seconds = 0

        if files_to_concatenate:
            full_filenames = [os.path.join(directory, f) for f in files_to_concatenate]
            concatenate_mp4_files(full_filenames, output_filename)
            log(f"Concatenated {files_to_concatenate} into {output_filename}")
            for temp_file in files_to_concatenate:
                os.remove(temp_file)

    return [os.path.join(directory, f"{game['round']}: {game['court']}: {game['home_team']}_{game['away_team']}.mp4") for game in games]

# def run():
#     bracket = get_parsed_bracket()
#     log(bracket)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Concatenate videos for a tournament.')
    args = parser.parse_args()

    court_3_games = [game for game in GAMES if game["court"].lower().strip() == "court 3"]
    court_2_games = [game for game in GAMES if game["court"].lower().strip() == "court 2"]

    log(f"Court 3 games: {court_3_games}")

    create_playoff_game_videos(court_3_games, COURT_3_DIRECTORY)