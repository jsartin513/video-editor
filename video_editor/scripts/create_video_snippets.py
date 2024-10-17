from video_snippet import create_video_snippets
from video_snippet import VideoClip



class CompositeVideoClip():
    def __init__(self, name, start_time, transition_times, transition_speeds, end_time):
        self.name = name
        self.start_time = start_time
        self.transition_times = transition_times
        self.transition_speeds = transition_speeds
        self.end_time = end_time

FILE_PATH = "/Users/jessica.sartin/Movies/Saved Dodgeball Clips/"
snippets = [
     VideoClip("29:30", "amanda_catch_pitchback", 7),
     VideoClip("34:38", "kyle_amanda_defensive_finish"),
     VideoClip("38:42", "marcos_dodge_3", 7),
     VideoClip("45:55", "vin_dodge_2_and_hit_1"),
     VideoClip("6:18", "alex_counter_and_catch"),
     VideoClip("28:10", "sami_dodge_2")

]

folder_path = "/Users/jessica.sartin/Movies/October 2024 open gyms"
file_name = "BDL Open Gym 10.13.24： 3 Team Rotation.mp4"
second_file_name = "BDL Open Gym 10.6.24： 3 Team Rotation.mp4"
file_path = folder_path + file_name

def run():
    create_video_snippets(file_path, snippets)

if __name__ == '__main__':
    run()