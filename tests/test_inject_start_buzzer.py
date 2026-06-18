from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from inject_start_buzzer import (
    estimate_phrase_end_from_report,
    find_play_start_cues,
    play_start_phrase_end_from_transcript,
    segment_play_start_end,
    speech_overlap_before_insert,
    validate_insert_point,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load_round(round_num: int) -> dict:
    report = json.loads((FIXTURES / "minimal_by_round_report.json").read_text(encoding="utf-8"))
    return next(item for item in report["rounds"] if item["round"] == round_num)


class TestSegmentPlayStartEnd:
    def test_caps_long_bundled_segment(self):
        segment = {
            "start": 1000.0,
            "end": 1010.0,
            "text": "Players line up, here we go, court two",
        }
        assert segment_play_start_end(segment) == 1004.5

    def test_caps_here_we_go_only(self):
        segment = {"start": 1000.0, "end": 1005.0, "text": "Here we go"}
        assert segment_play_start_end(segment) == 1002.5


class TestPhraseEndEstimation:
    def test_single_play_start_cue(self):
        cues = [{"wav_seconds": 1000.0}]
        assert estimate_phrase_end_from_report(cues) == 1004.0

    def test_split_phrase_uses_last_cue(self):
        cues = [{"wav_seconds": 1000.0}, {"wav_seconds": 1002.5}]
        assert estimate_phrase_end_from_report(cues) == 1004.5


class TestPlayStartPhraseEndFromTranscript:
    def test_finds_phrase_end_in_window(self):
        transcript = {
            "segments": [
                {"start": 999.5, "end": 1004.0, "text": "Players line up, here we go"},
                {"start": 1540.0, "end": 1543.0, "text": "Halfway through"},
            ]
        }
        end = play_start_phrase_end_from_transcript(transcript, first_play_start=1000.0)
        assert end == 1004.0


class TestFindPlayStartCues:
    def test_filters_play_start_roles(self):
        cues = find_play_start_cues(load_round(1))
        assert len(cues) == 1
        assert cues[0]["role"] == "play_start"


class TestSpeechOverlapBeforeInsert:
    def test_finds_halfway_between_phrase_and_insert(self):
        overlap = speech_overlap_before_insert(
            load_round(1),
            first_play_start=1000.0,
            insert_at=1550.0,
        )
        assert overlap is not None
        assert overlap["role"] == "halfway"


class TestValidateInsertPoint:
    @patch("inject_start_buzzer.max_volume_db", return_value=-40.0)
    def test_high_confidence_when_clear(self, _mock_volume):
        result = validate_insert_point(
            wav_path=Path("/tmp/unused.wav"),
            round_data=load_round(1),
            first_play_start=1000.0,
            insert_at=1004.0,
            phrase_end=1004.0,
        )
        assert result["insert_confidence"] == "high"
        assert result["insert_phrase_clear"]
        assert result["insert_speech_overlap"] is None

    @patch("inject_start_buzzer.max_volume_db", return_value=-40.0)
    def test_low_confidence_when_before_phrase_end(self, _mock_volume):
        result = validate_insert_point(
            wav_path=Path("/tmp/unused.wav"),
            round_data=load_round(1),
            first_play_start=1000.0,
            insert_at=1002.0,
            phrase_end=1004.0,
        )
        assert result["insert_confidence"] == "low"
        assert not result["insert_phrase_clear"]
