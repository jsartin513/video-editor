import os
import subprocess

from .utils import log


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


def merge_list_of_videos(video_files, output_file):
    """Merge a list of video files into one video file.

    Args:
        video_files: A list of video files to merge.
        output_file: The name of the output file.
    """
    with open("videos.txt", "w") as f:
        for video in video_files:
            f.write(f"file '{video}'\n")

    subprocess.run(["ffmpeg", "-f", "concat", "-safe", "0", "-i", "videos.txt", "-c", "copy", output_file])

def list_files_of_type_sorted_by_date(directory, filetype="mp4"):
  """Lists files in a directory sorted by modification date if they are of a certain type.

  Args:
    directory: The path to the directory.

  Returns:
    A list of file names sorted by modification date (oldest to newest).
  """
  files = [f for f in os.listdir(directory) if f.lower().endswith(filetype)]
  files_with_time = [(f, os.path.getmtime(os.path.join(directory, f))) for f in files]

  log(f"Files with time: {sorted(files_with_time, key=lambda x: x[1])}")
  
  return [f[0] for f in sorted(files_with_time, key=lambda x: x[1])]
