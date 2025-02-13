import requests
import csv
from io import StringIO

GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/1CC5uA0ZrP39eM6OC0JgE8JlwDrqpr4-ykp6kIKtgHXQ/export?format=csv&gid=182568368"
COURT_1_HEADER_TEXT = "Court 1"
COURT_2_HEADER_TEXT = "Court 2"
COURT_3_HEADER_TEXT = "Court 3"

def get_google_sheet_data():
    response = requests.get(GOOGLE_SHEET_URL)
    response.raise_for_status()  # Ensure we notice bad responses
    csv_data = response.text
    print(csv_data)
    return csv_data


def parse_schedule(csv_data):
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
            })
            schedule[COURT_2_HEADER_TEXT].append({
                'round': round_number,
                'start_time': start_time,
                'home_team': row[COURT_2_HEADER_TEXT],
            })
            schedule[COURT_3_HEADER_TEXT].append({
                'round': round_number,
                'start_time': start_time,
                'home_team': row[COURT_3_HEADER_TEXT],
            })
        elif idx % 3 == 1: # Away team row
            schedule[COURT_1_HEADER_TEXT][-1]['away_team'] = row[COURT_1_HEADER_TEXT]
            schedule[COURT_2_HEADER_TEXT][-1]['away_team'] = row[COURT_2_HEADER_TEXT]
            schedule[COURT_3_HEADER_TEXT][-1]['away_team'] = row[COURT_3_HEADER_TEXT]
    return schedule


# Example usage:
# csv_data = get_google_sheet_data()
# schedule = parse_schedule(csv_data)
# print(schedule)
