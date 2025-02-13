import requests
import csv
from io import StringIO

GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/1CC5uA0ZrP39eM6OC0JgE8JlwDrqpr4-ykp6kIKtgHXQ/export?format=csv&gid=182568368"

def get_google_sheet_data():
    response = requests.get(GOOGLE_SHEET_URL)
    response.raise_for_status()  # Ensure we notice bad responses
    csv_data = response.text
    print(csv_data)
    return csv_data


def parse_schedule(csv_data):
    reader = csv.DictReader(StringIO(csv_data))
    schedule = {'Court 1': [], 'Court 2': [], 'Court 3': []}
    for (idx, row) in enumerate(reader):
        if idx % 3 == 0: # Home team row
            round_number = row['Round #']
            start_time = row['Start Time']
            schedule['Court 1'].append({
                'round': round_number,
                'start_time': start_time,
                'home_team': row['Court 1'],
            })
            schedule['Court 2'].append({
                'round': round_number,
                'start_time': start_time,
                'home_team': row['Court 2'],
            })
            schedule['Court 3'].append({
                'round': round_number,
                'start_time': start_time,
                'home_team': row['Court 3'],
            })
        elif idx % 3 == 1: # Away team row
            schedule['Court 1'][-1]['away_team'] = row['Court 1']
            schedule['Court 2'][-1]['away_team'] = row['Court 2']
            schedule['Court 3'][-1]['away_team'] = row['Court 3']
    return schedule


# Example usage:
# csv_data = get_google_sheet_data()
# schedule = parse_schedule(csv_data)
# print(schedule)
