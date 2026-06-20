"""Build matchup video filenames to match split_multi_source_videos.sh output."""


def _title_case_words(text):
    return " ".join(word[:1].upper() + word[1:].lower() for word in str(text).replace("_", " ").split())


def is_placeholder_team(name):
    if name is None:
        return True
    return str(name).strip().upper() in {"", "TBD", "TBA", "TBC"}


def build_matchup_filename(game):
    parts = []
    game_type = game.get("type") or ""
    round_label = game.get("round") or ""

    if game_type and round_label:
        parts.append(f"{_title_case_words(game_type)} {round_label}")
    elif round_label:
        parts.append(f"Round {round_label}")

    court = game.get("court") or game.get("court_display")
    if court:
        parts.append(str(court).replace("_", " "))

    home_team = game.get("home_team", "")
    away_team = game.get("away_team", "")
    if is_placeholder_team(home_team) or is_placeholder_team(away_team):
        start_time = game.get("start_time")
        if start_time:
            parts.append(str(start_time))

    parts.append(f"{home_team} vs {away_team}")
    return ": ".join(parts) + ".mp4"
