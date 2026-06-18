from __future__ import annotations

import json
from pathlib import Path

import pytest

from verify_overhead_schedule import (
    ExpectedEvent,
    Game,
    TranscriptSegment,
    build_expected_events,
    classify_speech_role,
    in_skip_range,
    load_games,
    match_events_to_transcript,
    normalize_team,
    parse_skip_ranges,
    score_segment,
    seconds_to_hms,
    time_to_seconds,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
SCHEDULE_DIR = FIXTURES / "schedule"


class TestTimeHelpers:
    def test_time_to_seconds_hm(self):
        assert time_to_seconds("09:00") == 9 * 3600
        assert time_to_seconds("09:25") == 9 * 3600 + 25 * 60

    def test_time_to_seconds_hms(self):
        assert time_to_seconds("09:00:30") == 9 * 3600 + 30

    def test_time_to_seconds_invalid(self):
        with pytest.raises(ValueError, match="Invalid time"):
            time_to_seconds("9am")

    def test_seconds_to_hms(self):
        assert seconds_to_hms(3661) == "01:01:01"
        assert seconds_to_hms(-5) == "00:00:00"


class TestNormalizeTeam:
    def test_strips_the_and_punctuation(self):
        assert normalize_team("The Alpha-Squad!") == "alphasquad"


class TestSkipRanges:
    def test_parse_skip_ranges(self):
        assert parse_skip_ranges(["12:05-13:30"]) == [
            (12 * 3600 + 5 * 60, 13 * 3600 + 30 * 60)
        ]

    def test_parse_skip_ranges_invalid(self):
        with pytest.raises(ValueError, match="Invalid skip range"):
            parse_skip_ranges(["noon"])

    def test_in_skip_range(self):
        ranges = parse_skip_ranges(["12:00-13:00"])
        assert in_skip_range(12 * 3600 + 30 * 60, ranges)
        assert not in_skip_range(11 * 3600, ranges)


class TestLoadGames:
    def test_load_games_from_fixture(self):
        games = load_games(SCHEDULE_DIR, "2026-06-20", [2])
        assert len(games) == 2
        assert games[0].home_team == "Alpha Squad"
        assert games[0].court_num == 2
        assert games[1].start_time == "09:25"

    def test_load_games_missing_file(self):
        with pytest.raises(FileNotFoundError):
            load_games(SCHEDULE_DIR, "2026-06-20", [99])


class TestBuildExpectedEvents:
    @pytest.fixture
    def games(self) -> list[Game]:
        return load_games(SCHEDULE_DIR, "2026-06-20", [2])

    def test_builds_venue_wide_and_court_events(self, games: list[Game]):
        events = build_expected_events(games, "09:00", skip_ranges=[])
        venue = [e for e in events if e.venue_wide]
        court = [e for e in events if not e.venue_wide]
        assert len(venue) > 0
        assert len(court) > 0
        assert all(e.wav_offset_seconds >= 0 for e in events if not e.skipped)

    def test_skip_before_marks_early_events_skipped(self, games: list[Game]):
        events = build_expected_events(games, "09:00", skip_ranges=[], skip_before="09:10")
        skipped = [e for e in events if e.skipped]
        active = [e for e in events if not e.skipped]
        assert skipped
        assert active
        assert all(e.wall_seconds >= time_to_seconds("09:10") for e in active)


class TestClassifySpeechRole:
    def test_play_start(self):
        role = classify_speech_role(
            {"text": "Players line up, here we go", "offset_seconds": 240, "cues": ["play_start"]},
            round_idx=1,
        )
        assert role == "play_start"

    def test_no_blocking(self):
        role = classify_speech_role(
            {"text": "Three minutes, no blocking", "offset_seconds": 900, "cues": []},
            round_idx=1,
        )
        assert role == "no_blocking"

    def test_countdown_play_end_vs_boundary(self):
        play_end = classify_speech_role(
            {"text": "Ten, nine, eight", "offset_seconds": 1350, "cues": ["countdown"]},
            round_idx=1,
        )
        boundary = classify_speech_role(
            {"text": "Ten, nine, eight", "offset_seconds": 1600, "cues": ["countdown"]},
            round_idx=1,
        )
        assert play_end == "countdown_play_end"
        assert boundary == "countdown_round_boundary"

    def test_prior_round_tail_negative_offset(self):
        role = classify_speech_role(
            {"text": "Three, two, one", "offset_seconds": -30, "cues": []},
            round_idx=2,
        )
        assert role == "prior_round_tail"


class TestMatching:
    def test_score_segment_court_call(self):
        event = ExpectedEvent(
            wall_time="09:00",
            wall_seconds=time_to_seconds("09:00"),
            wav_offset_seconds=0,
            event_type="court_announcement",
            court_num=2,
            court="Court 2",
            home_team="Alpha Squad",
            away_team="Beta Brawlers",
            round="Round 1",
        )
        segment = TranscriptSegment(
            start=5.0,
            end=12.0,
            text="Court two, Alpha Squad versus Beta Brawlers, home team Alpha Squad",
        )
        assert score_segment(event, segment) >= 0.55

    def test_match_events_to_transcript_finds_play_start(self):
        slot_start = time_to_seconds("09:00")
        anchor = slot_start
        events = [
            ExpectedEvent(
                wall_time="09:04",
                wall_seconds=slot_start + 240,
                wav_offset_seconds=240.0,
                event_type="play_start",
                court_num=0,
                court="ALL",
                home_team="",
                away_team="",
                round="Round 1",
                venue_wide=True,
                label="Players line up / here we go",
            )
        ]
        segments = [
            TranscriptSegment(start=238.0, end=244.0, text="Players line up, here we go")
        ]
        results = match_events_to_transcript(events, segments, tolerance=90, min_confidence=0.55)
        assert len(results) == 1
        assert results[0].matched
        assert results[0].matched_text == segments[0].text
