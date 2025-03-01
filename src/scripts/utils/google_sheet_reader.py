import requests
import csv
from io import StringIO

ROUND_ROBIN_SHEET_URL = "https://docs.google.com/spreadsheets/d/1CC5uA0ZrP39eM6OC0JgE8JlwDrqpr4-ykp6kIKtgHXQ/export?format=csv&gid=182568368"
BRACKET_SHEET_URL = "https://docs.google.com/spreadsheets/d/1CC5uA0ZrP39eM6OC0JgE8JlwDrqpr4-ykp6kIKtgHXQ/export?format=csv&gid=2111325620"
COURT_1_HEADER_TEXT = "Court 1"
COURT_2_HEADER_TEXT = "Court 2"
COURT_3_HEADER_TEXT = "Court 3"
COURT_1_SCORE_TEXT = "Score_1"
COURT_2_SCORE_TEXT = "Score_2"
COURT_3_SCORE_TEXT = "Score_3"

BRACKET_ROUND_COLUMNS = ["Round 1", "Quarters", "Semis"]
FINALS_ROUND_COLUMNS = ["Finals", "Championship"]


def get_logo_path(team_name):
    updated_team_name = team_name.replace(" ", "_").replace(",", "").replace("'", "").lower()
    return f"src/static/{updated_team_name}_logo.png"



def get_parsed_schedule():
    sheet_data = get_google_sheet_data(ROUND_ROBIN_SHEET_URL)
    schedule = parse_schedule(sheet_data)
    return schedule

def get_google_sheet_data(sheet_url):
    response = requests.get(sheet_url)
    response.raise_for_status()  # Ensure we notice bad responses
    csv_data = response.text
    return csv_data

def get_parsed_bracket():
    sheet_data = get_google_sheet_data(BRACKET_SHEET_URL)
    bracket = parse_bracket(sheet_data)
    return bracket


def parse_bracket(csv_data):
    csv_data = get_google_sheet_data(BRACKET_SHEET_URL)
    reader = csv.DictReader(StringIO(csv_data))
    bracket = {round_name: [] for round_name in BRACKET_ROUND_COLUMNS}
    finals = {round_name: [] for round_name in FINALS_ROUND_COLUMNS}
    for row in reader:
        for round_name in BRACKET_ROUND_COLUMNS:
            if row.get(round_name) and row[round_name].strip() != "":
                bracket[round_name].append(row[round_name])
        for round_name in FINALS_ROUND_COLUMNS:
            if row.get(round_name)and row[round_name].strip() != "":
                finals[round_name].append(row[round_name])
    
    games = []
    for round_name, round_games in bracket.items():
        for idx, game_piece in enumerate(round_games):
            if idx % 3 == 0:
                home_team = game_piece
                court_and_subround = round_games[idx + 1]
                away_team = round_games[idx + 2]
                if "series" in court_and_subround:
                    court = court_and_subround.split("(")[0]
                    subround = court_and_subround.split("(")[1][:-1]
                else:
                    court = court_and_subround
                    subround = None
                game = {
                    "round": round_name,
                    "home_team": home_team,
                    "away_team": away_team,
                    "court": court,
                    "subround": subround
                }
                games.append(game)

    return games



def parse_schedule(csv_data, add_logo_paths=True):
    reader = csv.DictReader(StringIO(csv_data))
    schedule = {COURT_1_HEADER_TEXT: [], COURT_2_HEADER_TEXT: [], COURT_3_HEADER_TEXT: []}
    for (idx, row) in enumerate(reader):
        if idx % 3 == 0: # Home team row
            round_number = row['Round #']
            start_time = row['Start Time']
            schedule[COURT_1_HEADER_TEXT].append({
                'round': round_number,
                'start_time': start_time,
                'home_team': row[COURT_1_HEADER_TEXT],
                'home_team_score': row[COURT_1_SCORE_TEXT],
            })
            schedule[COURT_2_HEADER_TEXT].append({
                'round': round_number,
                'start_time': start_time,
                'home_team': row[COURT_2_HEADER_TEXT],
                'home_team_score': row[COURT_2_SCORE_TEXT],
            })
            schedule[COURT_3_HEADER_TEXT].append({
                'round': round_number,
                'start_time': start_time,
                'home_team': row[COURT_3_HEADER_TEXT],
                'home_team_score': row[COURT_3_SCORE_TEXT],
                
            })    
            if add_logo_paths:
                schedule[COURT_1_HEADER_TEXT][-1]['home_team_logo_path'] = get_logo_path(row[COURT_1_HEADER_TEXT])
                schedule[COURT_2_HEADER_TEXT][-1]['home_team_logo_path'] = get_logo_path(row[COURT_2_HEADER_TEXT])
                schedule[COURT_3_HEADER_TEXT][-1]['home_team_logo_path'] = get_logo_path(row[COURT_3_HEADER_TEXT])
        elif idx % 3 == 1: # Away team row
            schedule[COURT_1_HEADER_TEXT][-1]['away_team'] = row[COURT_1_HEADER_TEXT]
            schedule[COURT_1_HEADER_TEXT][-1]['away_team_score'] = row[COURT_1_SCORE_TEXT]
            schedule[COURT_2_HEADER_TEXT][-1]['away_team'] = row[COURT_2_HEADER_TEXT]
            schedule[COURT_2_HEADER_TEXT][-1]['away_team_score'] = row[COURT_2_SCORE_TEXT]
            schedule[COURT_3_HEADER_TEXT][-1]['away_team'] = row[COURT_3_HEADER_TEXT]
            schedule[COURT_3_HEADER_TEXT][-1]['away_team_score'] = row[COURT_3_SCORE_TEXT]
            if add_logo_paths:
                schedule[COURT_1_HEADER_TEXT][-1]['away_team_logo_path'] = get_logo_path(row[COURT_1_HEADER_TEXT])
                schedule[COURT_2_HEADER_TEXT][-1]['away_team_logo_path'] = get_logo_path(row[COURT_2_HEADER_TEXT])
                schedule[COURT_3_HEADER_TEXT][-1]['away_team_logo_path'] = get_logo_path(row[COURT_3_HEADER_TEXT])
    
    return schedule