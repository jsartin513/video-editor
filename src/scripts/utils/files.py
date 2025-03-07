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


def concatenate_mp4_files(files, output_file):
    """Concatenates a list of mp4 files into a single mp4 file.

    Args:
      files: A list of file names to concatenate.
      output_file: The name of the output file.
    """
    with open("files.txt", "w") as f:
        for file in files:
            f.write(f"file '{file}'\n")

    subprocess.run(["ffmpeg", "-f", "concat", "-safe", "0", "-i", "files.txt", "-c", "copy", output_file])


def trim_mp4_file(file, start_time, end_time, output_file):
    """Trims an mp4 file to a specified start and end time.

    Args:
      file: The name of the file to trim.
      start_time: The start time in seconds.
      end_time: The end time in seconds.
      output_file: The name of the output file.
    """

    log(f"Trimming {file} from {start_time} to {end_time} and saving to {output_file}")
    subprocess.run(["ffmpeg", "-i", file, "-ss", str(start_time), "-to", str(end_time), "-c", "copy", output_file])

def get_video_start_and_end_timestamps(video_filename):
    """Gets the start and end timestamps of a video.

    Args:
      video_filename: The name of the video file.

    Returns:
      A tuple of the start and end timestamps.
    """
    result = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                             "format_tags=creation_time", "-of",
                             "default=noprint_wrappers=1:nokey=1", video_filename],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT)
    timestamps = result.stdout.decode("utf-8").split("\n")  
    log(f"video_filename: {video_filename}")
    log(f"timestamps: {timestamps}")
    return [(timestamps[0], timestamps[1])]
    

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
