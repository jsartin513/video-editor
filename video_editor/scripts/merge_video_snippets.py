from video_snippet import merge_video_snippets

input_files = ["jess_catches_abby.mp4", 
               "between_two_catches.mp4",
               "jess_catches_lauren_same_game_as_abby.mp4",
               "after_two_catches.mp4"]

output_file = "jess_double_catch_game.mp4"

merge_video_snippets(output_file, input_files)