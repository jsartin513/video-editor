def log(message):
    print(message)


def format_team_name_for_filename(team_name):
    return team_name.replace(" ", "_").replace(",", "").replace("'", "").lower()

