import argparse
import os
from moviepy.editor import *

import subprocess

ROUND_ROBIN_COURT_1_TEAMS = []
ROUND_ROBIN_COURT_2_TEAMS = []
ROUND_ROBIN_COURT_3_TEAMS = []

def log(message):
    print(message)

# Get the length of a video in seconds
# filename: the name of the video file
# returns: the length of the video in seconds
# Credit: https://stackoverflow.com/questions/3844430/how-to-get-the-duration-of-a-video-in-python
# Uses bash for speed
def get_video_length(filename):
    result = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                             "format=duration", "-of",
                             "default=noprint_wrappers=1:nokey=1", filename],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT)
    return float(result.stdout)

# Add the team names to stylized panels in the video
def add_team_name_to_video(filename, home_team, away_team):
    output_path = f"{filename}_with_team_names.mp4"
    text = f"{home_team} vs. {away_team}"
    video = VideoFileClip(filename)
    text_clip = (
    TextClip(text, fontsize=30, color="blue", font="Arial")
    .set_position(("center", "bottom"))
    .set_duration(video.duration)
    )

    video_with_text = CompositeVideoClip([video, text_clip])
    video_with_text.write_videofile(output_path, codec="libx264", fps=24)

# Add the scores to the video
### home_team_timestamps: a list of timestamps where the home team scored
### away_team_timestamps: a list of timestamps where the away team scored
### filename: the name of the video file
### home_team: the name of the home team
### away_team: the name of the away team
def add_scores_to_video(filename, home_team, away_team, home_team_timestamps, away_team_timestamps):
    output_path = f"{filename}_with_scores.mp4"
    video = VideoFileClip(filename)
    home_team_score = 0
    away_team_score = 0
    current_timestamp = 0
    text = f"{home_team} {home_team_score} - {away_team_score} {away_team}"
    all_sorted_timestamps = sorted(home_team_timestamps + away_team_timestamps)
    videos_with_text = []
    for timestamp in all_sorted_timestamps:
        duration = timestamp - current_timestamp
        text_clip = (
            TextClip(text, fontsize=30, color="blue", font="Arial")
            .set_position(("center", "bottom"))
            .set_duration(duration)
        )
        video_with_text = CompositeVideoClip([video.subclip(current_timestamp, timestamp), text_clip])
        if timestamp in home_team_timestamps:
            home_team_score += 1
        elif timestamp in away_team_timestamps:
            away_team_score += 1
        text += f"\n{home_team} {home_team_score} - {away_team_score} {away_team}"
        videos_with_text.append(video_with_text)
        current_timestamp = timestamp

    final_video = concatenate_videoclips(videos_with_text)
    final_video.write_videofile(output_path, codec="libx264", fps=24)


# Rename the videos in the directory to the following format: "Home Team vs. Away Team.mp4"
# directory_name: the name of the directory containing the videos
# ordered_teams_including_refs: a list of teams in the order they appear in the video
def rename_videos(directory_name, ordered_teams_including_refs):
    # The list of teams will include the home team, away team, and ref
    # We only care about the home team and away team for each game
    # For each video in the directory, ordered by timestamp, if the video is at least 5 minutes long,
    # We will rename it to the following format: "Home Team vs. Away Team.mp4"
    # If the video is less than 5 minutes long, we will ignore it
    for video in os.listdir(directory_name):
        if video.endswith(".mp4"):
            video_path = os.path.join(directory_name, video)
            # Get the length of the video
            # If the video is at least 5 minutes long, rename it
            # Otherwise, ignore it
            video_length = get_video_length(video_path)
            if video_length >= 300:
                # Get the home team and away team
                home_team = ordered_teams_including_refs[0]
                away_team = ordered_teams_including_refs[1]
                new_video_name = f"{home_team} vs. {away_team}.mp4"
                new_video_path = os.path.join(directory_name, new_video_name)
                os.rename(video_path, new_video_path)
                log(f"Renamed {video} to {new_video_name}")
        else:
            log(f"Ignoring {video}")
        


def run(directory_name, ordered_teams_including_refs):
    pass

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Handle tournament videos.')
    parser.add_argument('directory_name', type=str, help='The name of the directory containing the videos')
    parser.add_argument('court', type=int, help='The court number')
    parser.add_argument('round_type', type=str, help='The type of round (round_robin, playoffs, finals)')
    args = parser.parse_args()

    
    directory_name = args.directory_name
    if args.court == 1:
        ordered_teams_including_refs = ROUND_ROBIN_COURT_1_TEAMS
    elif args.court == 2:
        ordered_teams_including_refs = ROUND_ROBIN_COURT_2_TEAMS
    elif args.court == 3:
        ordered_teams_including_refs = ROUND_ROBIN_COURT_3_TEAMS
    run(directory_name, ordered_teams_including_refs)