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
        
    

def create_video_snippets(folder_path, input_file_name, snippets):
    input_file = folder_path + input_file_name
    for snippet in snippets:
        clip = VideoFileClip(input_file).subclip(snippet.start_time, snippet.end_time).fx(vfx.speedx, snippet.speed)
        output_filename = folder_path + snippet.filename()
        clip.write_videofile(output_filename)
        print(f"Snippet {snippet.filename()} created")

def merge_video_snippets(output_file, input_files):
    video_clip_maker = VideoClipMaker(output_file)
    video_clip_maker.create_video(input_files)
