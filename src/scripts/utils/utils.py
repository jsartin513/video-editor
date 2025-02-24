import pprint

def log(message):
    pprint.pprint(message)


def format_team_name_for_filename(team_name):
    return team_name.replace(" ", "_").replace(",", "").replace("'", "").lower()

