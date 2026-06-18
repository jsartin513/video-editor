"""Shared utilities for overlaying PA clips into venue-wide overhead .wav files."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def seconds_to_hms(total_seconds: float) -> str:
    total = max(0, int(round(total_seconds)))
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def probe_audio(path: Path) -> dict:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "a:0",
        "-show_entries",
        "stream=sample_rate,channels,codec_name",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)
    stream = data["streams"][0]
    return {
        "sample_rate": int(stream["sample_rate"]),
        "channels": int(stream["channels"]),
        "codec": stream["codec_name"],
        "duration": float(data["format"]["duration"]),
    }


def load_report(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_transcript(wav_path: Path, transcript_path: Path | None) -> dict | None:
    path = transcript_path or wav_path.with_suffix(wav_path.suffix + ".transcript.json")
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def max_volume_db(wav_path: Path, timestamp: float, window_seconds: float = 0.5) -> float | None:
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-ss",
        str(max(0.0, timestamp)),
        "-t",
        str(max(0.05, window_seconds)),
        "-i",
        str(wav_path),
        "-af",
        "volumedetect",
        "-f",
        "null",
        "-",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    for line in result.stderr.splitlines():
        if "max_volume:" in line:
            value = line.split("max_volume:")[-1].strip().split()[0]
            return float(value.replace("dB", ""))
    return None


def build_ffmpeg_command(
    wav_path: Path,
    clip_path: Path,
    output_path: Path,
    insert_seconds: list[float],
    sample_rate: int,
    channels: int,
) -> list[str]:
    if not insert_seconds:
        raise ValueError("No insertion timestamps provided")

    n = len(insert_seconds)
    filter_parts: list[str] = []
    filter_parts.append(f"[1:a]asplit={n}" + "".join(f"[c{i}]" for i in range(n)))

    layout = "stereo" if channels == 2 else "mono"
    for i, start in enumerate(insert_seconds):
        delay_ms = int(round(start * 1000))
        filter_parts.append(
            f"[c{i}]aresample={sample_rate},aformat=sample_rates={sample_rate}:"
            f"channel_layouts={layout},adelay={delay_ms}|{delay_ms}[ins{i}]"
        )

    mix_inputs = "[0:a]" + "".join(f"[ins{i}]" for i in range(n))
    filter_parts.append(
        f"{mix_inputs}amix=inputs={n + 1}:duration=first:dropout_transition=0[out]"
    )
    filter_complex = ";".join(filter_parts)

    return [
        "ffmpeg",
        "-y",
        "-i",
        str(wav_path),
        "-i",
        str(clip_path),
        "-filter_complex",
        filter_complex,
        "-map",
        "[out]",
        "-c:a",
        "pcm_s16le",
        str(output_path),
    ]


def run_verification(wav_path: Path, report: dict, repo_root: Path) -> int:
    verify_script = repo_root / "src/scripts/verify_overhead_schedule.py"
    if not verify_script.exists():
        print(f"Warning: verification script not found: {verify_script}", file=sys.stderr)
        return 0

    schedule_dir = repo_root / "src/output/June2026Tournament/schedule/generated"
    if not schedule_dir.exists():
        print(
            "Warning: default schedule dir not found; skipping verification",
            file=sys.stderr,
        )
        return 0

    wav_start = report.get("wav_start_time", "09:00")
    python = repo_root / ".venv/bin/python"
    if not python.exists():
        python = Path(sys.executable)

    cmd = [
        str(python),
        str(verify_script),
        "--wav",
        str(wav_path),
        "--schedule-dir",
        str(schedule_dir),
        "--date",
        "2026-06-20",
        "--courts",
        "2,3,4",
        "--wav-start-time",
        wav_start,
        "--by-round",
    ]
    print("\nRe-running overhead verification on output wav ...", file=sys.stderr)
    result = subprocess.run(cmd)
    return result.returncode


def write_injections_sidecar(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
