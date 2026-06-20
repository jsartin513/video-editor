"""
Throw Down bracket round inference from wall-clock start times.

Bracket games use type=bracket and round names like Quarters / Semis so split
output filenames look like:
  Bracket Quarters: Court 2: Sister Sister vs Static Shock.mp4
"""

from __future__ import annotations

import re

THROWDOWN_SKIP_SHEETS = {"Overview Schedule", "BOARD Schedule", "BLANK"}

BRACKET_ROUND_SEQUENCE = [
    "Round 1",
    "Round 1",
    "Quarters",
    "Quarters",
    "Semis",
    "Semis",
    "Finals",
    "Finals",
    "Championship",
]

# Saturday bracket slots (25-minute rhythm from 13:50). Merged with Overview
# Schedule rows when bracket matchups are filled in.
DEFAULT_SATURDAY_BRACKET_SLOTS = {
    "13:50": "Round 1",
    "14:15": "Round 1",
    "14:40": "Quarters",
    "15:05": "Quarters",
    "15:30": "Semis",
    "15:55": "Semis",
    "16:20": "Finals",
    "16:45": "Championship",
}

DEFAULT_SUNDAY_BRACKET_SLOTS = {
    "09:00": "Round 1",
    "09:25": "Round 1",
    "09:50": "Quarters",
    "10:15": "Quarters",
    "10:40": "Semis",
    "11:05": "Semis",
    "11:30": "Finals",
    "11:55": "Championship",
}

DEFAULT_BRACKET_START_BY_DATE = {
    "2026-06-20": "13:50",
    "2026-06-21": "09:00",
}

DEFAULT_SLOTS_BY_DATE = {
    "2026-06-20": DEFAULT_SATURDAY_BRACKET_SLOTS,
    "2026-06-21": DEFAULT_SUNDAY_BRACKET_SLOTS,
}

DEFAULT_ACTIVE_COURTS_BY_DATE = {
    "2026-06-20": [2, 3, 4],
    "2026-06-21": [2, 3],
}

OVERVIEW_COURT_COLUMNS = {
    2: 1,
    4: 2,
    6: 3,
    8: 4,
}

BRACKET_PLACEHOLDER = "TBD"

BRACKET_MARKER_RE = re.compile(r"START OF BRACKET", re.I)
ROUND_LABEL_RE = re.compile(
    r"^(Round\s*1|Quarters?|Semis?|Semifinals?|Finals?|Championship|3rd Place|Third Place)$",
    re.I,
)


def normalize_time(value):
    if value is None or str(value).strip() == "":
        return None
    if hasattr(value, "strftime"):
        return value.strftime("%H:%M")
    text = str(value).strip()
    if re.match(r"^\d{1,2}:\d{2}(:\d{2})?$", text):
        parts = text.split(":")
        if len(parts) == 2:
            return f"{int(parts[0]):02d}:{parts[1]}"
        return f"{int(parts[0]):02d}:{parts[1]}:{parts[2]}"
    return text


def time_to_minutes(time_str):
    parts = str(time_str).split(":")
    hours = int(parts[0])
    minutes = int(parts[1]) if len(parts) > 1 else 0
    return hours * 60 + minutes


def detect_bracket_start(workbook, date):
    found = None
    for sheet_name in workbook.sheetnames:
        if sheet_name in THROWDOWN_SKIP_SHEETS:
            continue
        for row in workbook[sheet_name].iter_rows(values_only=True):
            if not row or len(row) < 3:
                continue
            assignment = row[2]
            if not assignment or not isinstance(assignment, str):
                continue
            if not BRACKET_MARKER_RE.search(assignment):
                continue
            start = normalize_time(row[1])
            if start:
                found = start
    return found or DEFAULT_BRACKET_START_BY_DATE.get(date, "13:50")


def _normalize_round_label(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"round", "time"}:
        return None
    if ROUND_LABEL_RE.match(text):
        if text.lower().startswith("quarter"):
            return "Quarters"
        if text.lower().startswith("semi"):
            return "Semis"
        if text.lower() == "finals":
            return "Finals"
        if "third" in text.lower() or "3rd" in text.lower():
            return "Third Place"
        if text.lower() == "championship":
            return "Championship"
        if re.match(r"^Round\s*1$", text, re.I):
            return "Round 1"
        return text
    if re.match(r"^Round\s+\d+$", text, re.I) and not text.lower().startswith("round 1"):
        return None
    return None


def parse_overview_bracket_map(workbook):
    """Build start_time -> bracket round from Overview Schedule bracket rows."""
    time_map = {}
    bracket_start = None
    current_round = None

    if "Overview Schedule" not in workbook.sheetnames:
        return bracket_start, time_map

    in_bracket = False
    for row in workbook["Overview Schedule"].iter_rows(values_only=True):
        if not row:
            continue

        assignment = row[2] if len(row) > 2 else None
        if assignment and isinstance(assignment, str) and BRACKET_MARKER_RE.search(assignment):
            bracket_start = normalize_time(row[1]) or bracket_start
            in_bracket = True
            continue

        if not in_bracket:
            continue

        round_label = _normalize_round_label(row[0])
        if round_label:
            current_round = round_label

        start_time = normalize_time(row[1])
        if start_time and current_round:
            time_map[start_time] = current_round

        if assignment and isinstance(assignment, str):
            inline = _normalize_round_label(assignment)
            if inline and start_time:
                time_map[start_time] = inline

    return bracket_start, time_map


def build_bracket_time_map(workbook, date):
    overview_start, overview_map = parse_overview_bracket_map(workbook)
    bracket_start = overview_start or detect_bracket_start(workbook, date)
    defaults = dict(DEFAULT_SLOTS_BY_DATE.get(date, DEFAULT_SATURDAY_BRACKET_SLOTS))
    defaults.update(overview_map)
    return bracket_start, defaults


def lookup_bracket_round(start_time, time_map, bracket_start, bracket_minutes=25):
    if start_time in time_map:
        return time_map[start_time]

    target = time_to_minutes(start_time)
    best_round = None
    best_distance = 9999
    for slot_time, round_name in time_map.items():
        distance = abs(target - time_to_minutes(slot_time))
        if distance < best_distance:
            best_distance = distance
            best_round = round_name

    tolerance = max(12, bracket_minutes // 2)
    if best_round and best_distance <= tolerance:
        return best_round

    elapsed = round((target - time_to_minutes(bracket_start)) / bracket_minutes)
    if 0 <= elapsed < len(BRACKET_ROUND_SEQUENCE):
        return BRACKET_ROUND_SEQUENCE[elapsed]
    if elapsed >= 0:
        return BRACKET_ROUND_SEQUENCE[-1]
    return "Round 1"


def classify_game(start_time, round_num, bracket_start, time_map, bracket_minutes=25, round_robin_max=10):
    """
    Return (type, round) for JSONL output.

    Round robin keeps Round N through round_robin_max; later times or explicit
    bracket slots become type=bracket with Quarters / Semis / etc.
    """
    if time_to_minutes(start_time) < time_to_minutes(bracket_start):
        return "round_robin", f"Round {round_num}"

    if round_num is not None and round_num > round_robin_max:
        bracket_round = lookup_bracket_round(start_time, time_map, bracket_start, bracket_minutes)
        return "bracket", bracket_round

    bracket_round = lookup_bracket_round(start_time, time_map, bracket_start, bracket_minutes)
    return "bracket", bracket_round


def is_placeholder_team(name):
    if name is None:
        return True
    text = str(name).strip().upper()
    return text in {"", "TBD", "TBA", "TBC"}


def active_courts_for_date(date, skip_courts, active_courts=None):
    if active_courts:
        return [c for c in active_courts if c not in skip_courts]
    courts = DEFAULT_ACTIVE_COURTS_BY_DATE.get(date, [2, 3, 4])
    return [c for c in courts if c not in skip_courts]


def game_slot_key(start_time, court_num):
    return (start_time, court_num)


def generate_bracket_placeholder_games(date, active_court_nums, bracket_time_map, bracket_start, minutes):
    games = []
    for start_time in sorted(bracket_time_map.keys()):
        if time_to_minutes(start_time) < time_to_minutes(bracket_start):
            continue
        round_label = bracket_time_map[start_time]
        for court_num in active_court_nums:
            games.append({
                "date": date,
                "court": f"court{court_num}",
                "court_display": f"Court {court_num}",
                "type": "bracket",
                "round": round_label,
                "home_team": BRACKET_PLACEHOLDER,
                "away_team": BRACKET_PLACEHOLDER,
                "start_time": start_time,
                "minutes": minutes,
            })
    return games


def parse_overview_bracket_games(workbook, date, skip_courts, minutes, aliases, bracket_start, bracket_time_map, resolve_team_name):
    """Parse bracket matchups from Overview Schedule when team names are filled in."""
    games = []
    if "Overview Schedule" not in workbook.sheetnames:
        return games

    in_bracket = False
    pending_homes = {}
    current_start = None
    current_round = None

    for row in workbook["Overview Schedule"].iter_rows(values_only=True):
        if not row:
            continue

        assignment = row[2] if len(row) > 2 else None
        if assignment and isinstance(assignment, str) and BRACKET_MARKER_RE.search(assignment):
            in_bracket = True
            pending_homes = {}
            current_start = None
            current_round = None
            continue

        if not in_bracket:
            continue

        round_label = _normalize_round_label(row[0])
        start_time = normalize_time(row[1])
        if start_time:
            current_start = start_time
            if round_label:
                current_round = round_label
            elif current_start in bracket_time_map:
                current_round = bracket_time_map[current_start]
            pending_homes = {}
        elif round_label:
            current_round = round_label

        if not current_start or not current_round:
            continue

        for col_idx, court_num in OVERVIEW_COURT_COLUMNS.items():
            if court_num in skip_courts:
                continue
            if col_idx >= len(row):
                continue
            cell = row[col_idx]
            if cell is None or not str(cell).strip():
                continue
            team = resolve_team_name(str(cell).strip(), aliases)
            if is_placeholder_team(team):
                continue

            if start_time:
                pending_homes[court_num] = team
            elif court_num in pending_homes:
                games.append({
                    "date": date,
                    "court": f"court{court_num}",
                    "court_display": f"Court {court_num}",
                    "type": "bracket",
                    "round": current_round,
                    "home_team": pending_homes[court_num],
                    "away_team": team,
                    "start_time": current_start,
                    "minutes": minutes,
                })
                del pending_homes[court_num]

    return games


def merge_bracket_games(parsed_games, workbook, date, skip_courts, minutes, aliases, resolve_team_name, include_placeholders=True, active_courts=None):
    bracket_start, bracket_time_map = build_bracket_time_map(workbook, date)
    court_nums = active_courts_for_date(date, skip_courts, active_courts)

    overview_games = parse_overview_bracket_games(
        workbook,
        date,
        skip_courts,
        minutes,
        aliases,
        bracket_start,
        bracket_time_map,
        resolve_team_name,
    )

    by_slot = {}
    for game in parsed_games:
        court_num = int(re.search(r"(\d+)", game["court"]).group(1))
        by_slot[game_slot_key(game["start_time"], court_num)] = game

    for game in overview_games:
        court_num = int(re.search(r"(\d+)", game["court"]).group(1))
        by_slot[game_slot_key(game["start_time"], court_num)] = game

    if include_placeholders:
        for game in generate_bracket_placeholder_games(
            date, court_nums, bracket_time_map, bracket_start, minutes
        ):
            key = game_slot_key(game["start_time"], int(re.search(r"(\d+)", game["court"]).group(1)))
            by_slot.setdefault(key, game)

    merged = list(by_slot.values())
    merged.sort(key=lambda g: (g["date"], g["court"], g["start_time"], g["round"]))
    return merged, bracket_start, len(overview_games), len([g for g in by_slot.values() if g["type"] == "bracket"])
