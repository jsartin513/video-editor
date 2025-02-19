STANDARD_TRANSITION_TIME = 1

# Create a function that takes in a time t and returns the size of an object moving from start_size to end_size
def function_for_size(t, start_size, end_size, clip_duration=STANDARD_TRANSITION_TIME):
    return start_size + (end_size - start_size) * t / clip_duration

# Create a function that takes in a time t and returns the position of an object moving from start_position to end_position
def function_for_position(t, start_position, end_position, clip_duration=STANDARD_TRANSITION_TIME):
    x_start_position, y_start_position = start_position
    x_end_position, y_end_position = end_position
    x_distance = x_end_position - x_start_position
    y_distance = y_end_position - y_start_position

    return (x_start_position + x_distance * t / clip_duration, y_start_position + y_distance * t / clip_duration)
