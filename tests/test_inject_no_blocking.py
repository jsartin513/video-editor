from __future__ import annotations

import json
from pathlib import Path

from inject_no_blocking import (
    find_play_end_countdown,
    in_silence_search_window,
    list_no_blocking_silence_candidates,
    looks_like_countdown,
    speech_before_insert,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load_round(round_num: int) -> dict:
    report = json.loads((FIXTURES / "minimal_by_round_report.json").read_text(encoding="utf-8"))
    return next(item for item in report["rounds"] if item["round"] == round_num)


class TestFindPlayEndCountdown:
    def test_picks_last_play_end_before_boundary(self):
        countdown = find_play_end_countdown(load_round(1))
        assert countdown is not None
        assert countdown["role"] == "countdown_play_end"
        assert countdown["wav_seconds"] == 1996.0

    def test_returns_only_play_end_when_no_boundary(self):
        countdown = find_play_end_countdown(load_round(2))
        assert countdown is not None
        assert countdown["wav_seconds"] == 3496.0


class TestLooksLikeCountdown:
    def test_matches_common_patterns(self):
        assert looks_like_countdown("Ten, nine, eight, seven")
        assert looks_like_countdown("Three, two, one")
        assert not looks_like_countdown("Players line up")


class TestSilenceSearchWindow:
    def test_accepts_long_silence_after_countdown(self):
        silence = {"start": 2010.0, "end": 2030.0, "duration": 20.0}
        assert in_silence_search_window(
            silence,
            countdown_start=1996.0,
            min_after_countdown=3.0,
            max_offset=120.0,
            min_no_blocking_silence=15.0,
        )

    def test_rejects_silence_too_early_and_short(self):
        silence = {"start": 1997.0, "end": 1999.0, "duration": 2.0}
        assert not in_silence_search_window(
            silence,
            countdown_start=1996.0,
            min_after_countdown=3.0,
            max_offset=120.0,
            min_no_blocking_silence=15.0,
        )


class TestListNoBlockingSilenceCandidates:
    def test_orders_earliest_first(self):
        silences = [
            {"start": 2050.0, "end": 2070.0, "duration": 20.0},
            {"start": 2010.0, "end": 2030.0, "duration": 20.0},
        ]
        candidates = list_no_blocking_silence_candidates(
            silences,
            countdown_start=1996.0,
            min_after_countdown=3.0,
            min_no_blocking_silence=15.0,
        )
        assert [item["start"] for item in candidates] == [2010.0, 2050.0]


class TestSpeechBeforeInsert:
    def test_detects_blocking_speech(self):
        round_data = load_round(1)
        overlap = speech_before_insert(round_data, countdown_start=1996.0, insert_at=2110.0)
        assert overlap is not None
        assert overlap["role"] == "countdown_round_boundary"

    def test_ignores_play_end_countdown_itself(self):
        round_data = {
            "speech": [
                {
                    "wav_seconds": 1996.0,
                    "wav_timestamp": "00:33:16",
                    "role": "countdown_play_end",
                    "text": "three two one",
                }
            ]
        }
        assert speech_before_insert(round_data, countdown_start=1996.0, insert_at=2010.0) is None
