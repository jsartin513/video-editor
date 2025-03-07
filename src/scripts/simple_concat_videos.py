import argparse
import json
import math
import os
import random
from utils.files import trim_mp4_file, concatenate_mp4_files, get_video_length
from utils.utils import log, format_team_name_for_filename


######
##
##
# A game looks like this:
#   {
#     "home_team": "The Powerpuff Girls",
#     "away_team": "Totally Spies",
#     "video_path": [
#       "/Users/MrsHazmat/Recordings from Throw Down 3/Court 1 RR/processed_videos/the_powerpuff_girls_totally_spies_round_robin_round_1_part_1.mp4",
#       "/Users/MrsHazmat/Recordings from Throw Down 3/Court 1 RR/processed_videos/the_powerpuff_girls_totally_spies_round_robin_round_1_part_2.mp4"
#     ],
#     "home_team_score": "3",
#     "away_team_score": "1",
#     "round": "1",
#     "start_time": "10:30 AM",
#     "trim_time": 350,
#     "end_trim_time": 85,
#     "home_team_logo_path": "src/static/the_powerpuff_girls_logo.png",
#     "away_team_logo_path": "src/static/totally_spies_logo.png"
#   },
# We want to start with the first video in video_path starting from trim_time, 
# then add the rest of the videos in the list. The last video will have end_trim_time seconds trimmed off of the end.
def run(output_path, games):
    created_video_paths = []
    for game in games:
        final_output_path = f"{output_path}/final"
        if not os.path.exists(final_output_path):
            os.makedirs(final_output_path)
        video_paths = game["video_path"]
        trim_time = game.get("trim_time", 0)
        end_trim_time = game.get("end_trim_time", 0)
        formatted_home_team = format_team_name_for_filename(game["home_team"])
        formatted_away_team = format_team_name_for_filename(game["away_team"])
        output_file = f"{final_output_path}/Round Robin {game["round"]}: Court 2: {game["home_team"]} vs {game["away_team"]}.mp4"
        first_video = video_paths[0]
        first_video_length = get_video_length(first_video)
        other_videos = video_paths[1:]

        first_temp_filename = f"{output_path}/{formatted_home_team}_{formatted_away_team}_round_{game['round']}_merged_temp1.mp4"
        second_temp_filename = f"{output_path}/{formatted_home_team}_{formatted_away_team}_round_{game['round']}_merged_temp2.mp4"

        trim_mp4_file(first_video, trim_time, first_video_length, first_temp_filename)
        concatenate_mp4_files([first_temp_filename] + other_videos, second_temp_filename)


        concatenated_video_length = get_video_length(second_temp_filename)
        expected_length = concatenated_video_length - end_trim_time
        trim_mp4_file(second_temp_filename, 0, expected_length, output_file)

        created_video_paths.append(output_file)

        # Remove temp files
        os.remove(first_temp_filename)
        os.remove(second_temp_filename)

    return created_video_paths




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
    # # random_game_number = 6
    # del games[random_game_number] # For second run, bc we already ran it once
    # games = [games[random_game_number]]
    created_videos = run(output_path, games)
    log(f"Created videos: {created_videos}")