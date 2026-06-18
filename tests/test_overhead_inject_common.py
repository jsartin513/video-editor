from __future__ import annotations

from pathlib import Path

import pytest

from overhead_inject_common import build_ffmpeg_command, seconds_to_hms


class TestSecondsToHms:
    def test_formats_hours(self):
        assert seconds_to_hms(3661) == "01:01:01"


class TestBuildFfmpegCommand:
    def test_single_insert_includes_filter_complex(self, tmp_path: Path):
        wav = tmp_path / "source.wav"
        clip = tmp_path / "clip.wav"
        out = tmp_path / "out.wav"
        wav.touch()
        clip.touch()

        cmd = build_ffmpeg_command(wav, clip, out, [120.5], sample_rate=48000, channels=2)
        assert cmd[0] == "ffmpeg"
        assert "-filter_complex" in cmd
        filter_complex = cmd[cmd.index("-filter_complex") + 1]
        assert "asplit=1" in filter_complex
        assert "adelay=120500|120500" in filter_complex
        assert "amix=inputs=2" in filter_complex

    def test_multiple_inserts_split_clip(self, tmp_path: Path):
        wav = tmp_path / "source.wav"
        clip = tmp_path / "clip.wav"
        out = tmp_path / "out.wav"
        wav.touch()
        clip.touch()

        cmd = build_ffmpeg_command(
            wav, clip, out, [10.0, 20.0, 30.0], sample_rate=44100, channels=1
        )
        filter_complex = cmd[cmd.index("-filter_complex") + 1]
        assert "asplit=3" in filter_complex
        assert "channel_layouts=mono" in filter_complex
        assert "amix=inputs=4" in filter_complex

    def test_rejects_empty_insert_list(self, tmp_path: Path):
        with pytest.raises(ValueError, match="No insertion timestamps"):
            build_ffmpeg_command(
                tmp_path / "a.wav",
                tmp_path / "b.wav",
                tmp_path / "c.wav",
                [],
                sample_rate=48000,
                channels=2,
            )
