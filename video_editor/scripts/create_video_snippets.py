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

        
            


def get_end_time(time, duration):
    time = time.split(":")
    seconds = int(time[1]) + duration
    time[1] = str(seconds)
    return ":".join(time)

for snippet in snippets:
    start_time = snippet.start_time
    end_time = get_end_time(start_time, snippet.duration)
    if snippet.name.endswith(".mp4"):
        new_filename = FILE_PATH + snippet.name
    else:
        new_filename = FILE_PATH + snippet.name + ".mp4"
    snippet.end_time = end_time
    


file_path = "/Users/jessica.sartin/Movies/BDL Open Gym 8.4.24：  3 Team Rotation.mp4"
# file_path = "/Users/jessica.sartin/Movies/BDL Open Gym 7.28.24： 6v6 Warm Up Matches.mp4"

create_video_snippets(file_path, snippets)