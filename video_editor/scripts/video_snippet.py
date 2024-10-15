import os
from moviepy.editor import *

class VideoClip:
    def __init__(self, start_time, name, duration=10, speed=1):
        self.start_time = start_time
        self.name = name
        self.duration = duration
        self.speed = speed

    def filename(self)-> str:
        if self.name.endswith(".mp4"):
            return self.name
        else:
            return self.name + ".mp4"
        
    def end_time(self):
        time = self.start_time.split(":")
        seconds = int(time[1]) + self.duration
        time[1] = str(seconds)
        return ":".join(time)

class VideoSnippet:
    def __init__(self, input_file, start_timestamp, end_timestamp, new_filename):
        self.input_file = input_file
        self.start_timestamp = start_timestamp
        self.end_timestamp = end_timestamp
        self.new_filename = new_filename

    def create_snippet(self, snippet):
        print(f"Creating snippet {snippet.new_filename}")
        # ffmpeg_command = f"ffmpeg -i {self.input_file} -ss {snippet.start_timestamp} -to {snippet.end_timestamp} -c copy {snippet.new_filename}"
        # os.system(ffmpeg_command)

class VideoSnippetSet:
    def __init__(self, input_file, snippets):
        self.input_file = input_file
        self.snippets = snippets

    def create_snippets(self):
        for snippet in self.snippets:
            clip = VideoFileClip(self.input_file).subclip(snippet.start_time, snippet.end_time).fx(vfx.speedx, snippet.speed)
            clip.write_videofile(snippet.filename())
            print(f"Snippet {snippet.filename()} created")

class VideoClipMaker:
    def __init__(self, output_file):
        self.output_file = output_file

    def create_video(self, input_files):
        print(f"Creating video {self.output_file}")
        clips = []
        for filename in input_files:
            with VideoFileClip(filename) as video_clip:
                clips.append(video_clip)
        composite_video = CompositeVideoClip(clips)
        composite_video.write_videofile(self.output_file, 60, codec="mpeg4")
        composite_video.close()
        
    

def create_video_snippets(input_file, snippets):
    video_snippet_set = VideoSnippetSet(input_file, snippets)
    video_snippet_set.create_snippets()

def merge_video_snippets(output_file, input_files):
    video_clip_maker = VideoClipMaker(output_file)
    video_clip_maker.create_video(input_files)

# Hardcode snippits and filename for now
SNIPPETS = [("30:33", "30:43", "jess_catches_abby.mp4"), ("33:45", "33.55", "jess_catches_armando.mp4")]
FILE_PATH = "/Users/jessica.sartin/Movies"
FILE_NAME = "sun28july_6v6.mp4"

def run():
    print("Creating video snippets")
    video_snippet_set = VideoSnippetSet(FILE_PATH, SNIPPETS)
    video_snippet_set.create_snippets()