import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "scripts"))

from throwdown_bracket import classify_game, lookup_bracket_round


def test_round_robin_stays_round_robin():
    game_type, round_label = classify_game(
        "09:25",
        2,
        "13:50",
        {"13:50": "Round 1", "14:40": "Quarters"},
    )
    assert game_type == "round_robin"
    assert round_label == "Round 2"


def test_bracket_time_maps_to_quarters():
    game_type, round_label = classify_game(
        "14:40",
        11,
        "13:50",
        {"13:50": "Round 1", "14:40": "Quarters"},
    )
    assert game_type == "bracket"
    assert round_label == "Quarters"


def test_bracket_infers_semis_from_time():
    game_type, round_label = classify_game(
        "15:30",
        12,
        "13:50",
        {"13:50": "Round 1", "14:40": "Quarters", "15:30": "Semis"},
    )
    assert game_type == "bracket"
    assert round_label == "Semis"


def test_lookup_fuzzy_within_slot():
    assert lookup_bracket_round("14:41", {"14:40": "Quarters"}, "13:50") == "Quarters"
