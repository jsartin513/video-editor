#!/usr/bin/env python3
"""
Insert no-blocking PA clips into a venue-wide overhead .wav after each play-end buzzer.

Uses play-end countdown times from a by-round overhead verification report, then
ffmpeg silencedetect to find the start of the post-buzzer silent window. Overlays
the clip a few seconds into that silence (same duration as the source wav).

Usage:
  python inject_no_blocking.py \\
    --wav "/path/to/BDL Throwdown 5 Full Timeline.wav" \\
    --report "/path/to/BDL Throwdown 5 Full Timeline_overhead_by_round_report.json"

  python inject_no_blocking.py --wav ... --report ... --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_CLIP = Path(
    "/Users/jessicasartin/Downloads/15 min round - foam NS 8.5 (no time limit on NB).band"
    "/Media/Audio Files/Dance Vocal#31.wav"
)

CLIP_PRESETS: dict[str, str] = {
    "three_minutes_no_blocking": "Dance Vocal#31.wav",
    "no_blocking": "Dance Vocal#28.wav",
    "three_minutes_remaining": "Dance Vocal#29.wav",
}

COUNTDOWN_TEXT_RE = re.compile(
    r"\b(10|ten)\b.*\b(9|nine)\b|"
    r"\b7,\s*6,\s*5|"
    r"\bfive,\s*four|"
    r"three,\s*two,\s*one|"
    r"\b2,\s*1\b|"
    r"seven,\s*six,\s*five",
    re.I,
)


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


def find_play_end_countdown(round_data: dict) -> dict | None:
    candidates = [item for item in round_data["speech"] if item["role"] == "countdown_play_end"]
    if not candidates:
        return None

    boundary = next(
        (item for item in round_data["speech"] if item["role"] == "countdown_round_boundary"),
        None,
    )
    boundary_wav = boundary["wav_seconds"] if boundary else float("inf")
    in_window = [item for item in candidates if item["wav_seconds"] < boundary_wav]
    pool = in_window or candidates
    return max(pool, key=lambda item: item["wav_seconds"])


def looks_like_countdown(text: str) -> bool:
    return bool(COUNTDOWN_TEXT_RE.search(text.lower()))


def countdown_end_from_transcript(
    transcript: dict | None,
    countdown_start: float,
    search_seconds: float = 35.0,
) -> float | None:
    if not transcript:
        return None

    end: float | None = None
    window_end = countdown_start + search_seconds
    for segment in transcript.get("segments", []):
        start = float(segment["start"])
        if start < countdown_start - 1.0 or start > window_end:
            continue
        if not looks_like_countdown(segment.get("text", "")):
            continue
        segment_end = float(segment.get("end", start))
        segment_duration = segment_end - start
        if segment_duration > 30.0:
            segment_end = start + 20.0
        end = segment_end if end is None else max(end, segment_end)
    return end


def detect_silences(
    wav_path: Path,
    start: float,
    duration: float,
    noise_db: float,
    min_silence: float,
) -> list[dict]:
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-ss",
        str(max(0.0, start)),
        "-t",
        str(max(0.1, duration)),
        "-i",
        str(wav_path),
        "-af",
        f"silencedetect=noise={noise_db}dB:d={min_silence}",
        "-f",
        "null",
        "-",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    stderr = result.stderr

    silences: list[dict] = []
    current_start: float | None = None
    for line in stderr.splitlines():
        if "silence_start:" in line:
            value = line.split("silence_start:")[-1].strip()
            current_start = start + float(value)
        elif "silence_end:" in line and current_start is not None:
            tail = line.split("silence_end:")[-1].strip()
            relative_end = float(tail.split("|")[0].strip())
            duration_match = re.search(r"silence_duration:\s*([0-9.]+)", line)
            silence_duration = float(duration_match.group(1)) if duration_match else None
            silences.append(
                {
                    "start": current_start,
                    "end": start + relative_end,
                    "duration": silence_duration,
                }
            )
            current_start = None

    if current_start is not None:
        silences.append(
            {
                "start": current_start,
                "end": start + duration,
                "duration": (start + duration) - current_start,
            }
        )
    return silences


def is_silent_at(
    wav_path: Path,
    timestamp: float,
    window_seconds: float,
    noise_db: float,
    min_silence: float,
) -> tuple[bool, dict | None]:
    """Return True if timestamp falls inside a detected silence window."""
    search_start = max(0.0, timestamp - window_seconds)
    search_duration = window_seconds * 2
    silences = detect_silences(wav_path, search_start, search_duration, noise_db, min_silence)
    for silence in silences:
        if silence["start"] <= timestamp <= silence["end"]:
            return True, silence
    return False, None


def choose_no_blocking_silence(
    silences: list[dict],
    countdown_start: float,
    min_after_countdown: float,
    min_no_blocking_silence: float,
    early_window: float = 45.0,
    late_window: float = 120.0,
) -> dict | None:
    def in_early(silence: dict) -> bool:
        return countdown_start + min_after_countdown <= silence["start"] <= countdown_start + early_window

    def in_late(silence: dict) -> bool:
        return countdown_start + min_after_countdown <= silence["start"] <= countdown_start + late_window

    def duration(silence: dict) -> float:
        return float(silence.get("duration") or 0.0)

    for predicate, min_duration in (
        (in_early, min_no_blocking_silence),
        (in_early, 2.0),
        (in_late, min_no_blocking_silence),
        (in_late, 2.0),
    ):
        candidates = [silence for silence in silences if predicate(silence) and duration(silence) >= min_duration]
        if candidates:
            return max(candidates, key=duration)
    return None


def compute_insertions(
    wav_path: Path,
    report: dict,
    transcript: dict | None,
    offset_after_silence: float,
    search_window: float,
    noise_db: float,
    min_silence_detect: float,
    min_after_countdown: float,
    min_no_blocking_silence: float,
    fallback_after_countdown_end: float,
) -> list[dict]:
    insertions: list[dict] = []

    for round_data in report["rounds"]:
        countdown = find_play_end_countdown(round_data)
        if countdown is None:
            insertions.append(
                {
                    "round": round_data["round"],
                    "insert_seconds": None,
                    "reason": "no play-end countdown found in report speech",
                }
            )
            continue

        countdown_start = float(countdown["wav_seconds"])
        transcript_end = countdown_end_from_transcript(transcript, countdown_start)
        silences = detect_silences(
            wav_path,
            countdown_start,
            search_window,
            noise_db,
            min_silence_detect,
        )
        chosen_silence = choose_no_blocking_silence(
            silences,
            countdown_start,
            min_after_countdown,
            min_no_blocking_silence,
        )

        method = "silencedetect"
        if chosen_silence is not None:
            insert_at = chosen_silence["start"] + offset_after_silence
            silence_start = chosen_silence["start"]
            silence_duration = chosen_silence.get("duration")
        elif transcript_end is not None:
            method = "transcript_end_fallback"
            silence_start = None
            silence_duration = None
            insert_at = transcript_end + fallback_after_countdown_end
        else:
            method = "countdown_start_fallback"
            silence_start = None
            silence_duration = None
            insert_at = countdown_start + min_after_countdown + fallback_after_countdown_end

        verified, verify_silence = is_silent_at(
            wav_path,
            insert_at,
            window_seconds=6.0,
            noise_db=noise_db,
            min_silence=min_silence_detect,
        )

        insertions.append(
            {
                "round": round_data["round"],
                "schedule_label": round_data["schedule_label"],
                "play_end_countdown_wav": countdown["wav_timestamp"],
                "play_end_countdown_seconds": countdown_start,
                "countdown_end_transcript": transcript_end,
                "countdown_end_transcript_hms": (
                    seconds_to_hms(transcript_end) if transcript_end is not None else None
                ),
                "silence_start_seconds": silence_start,
                "silence_start_hms": (
                    seconds_to_hms(silence_start) if silence_start is not None else None
                ),
                "silence_duration_seconds": silence_duration,
                "insert_seconds": round(insert_at, 3),
                "insert_wav_timestamp": seconds_to_hms(insert_at),
                "insert_method": method,
                "insert_verified_silent": verified,
                "verify_silence_window": verify_silence,
                "countdown_text": countdown["text"],
            }
        )
    return insertions


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


def resolve_clip_path(args: argparse.Namespace) -> Path:
    if args.clip:
        return args.clip.expanduser()
    if args.clip_preset:
        band_dir = args.band_dir.expanduser()
        filename = CLIP_PRESETS[args.clip_preset]
        return band_dir / "Media/Audio Files" / filename
    return DEFAULT_CLIP


def print_insertion_plan(insertions: list[dict], clip_path: Path) -> None:
    clip_info = probe_audio(clip_path)
    print(f"Clip: {clip_path}")
    print(f"  duration={clip_info['duration']:.1f}s")
    print()
    print(
        f"{'RND':<4} {'CD START':<10} {'CD END':<10} {'SILENCE':<10} "
        f"{'INSERT':<10} {'SILENT?':<7} {'METHOD'}"
    )
    print("-" * 95)
    for item in insertions:
        if item["insert_seconds"] is None:
            print(f"{item['round']:<4}  SKIP — {item['reason']}")
            continue
        cd_end = item.get("countdown_end_transcript_hms") or "—"
        silence = item.get("silence_start_hms") or "—"
        silent = "yes" if item.get("insert_verified_silent") else "NO"
        print(
            f"{item['round']:<4} "
            f"{item['play_end_countdown_wav']:<10} "
            f"{cd_end:<10} "
            f"{silence:<10} "
            f"{item['insert_wav_timestamp']:<10} "
            f"{silent:<7} "
            f"{item['insert_method']}"
        )
        if item.get("silence_duration_seconds") is not None:
            print(
                f"     silence_duration={item['silence_duration_seconds']:.1f}s  "
                f"countdown={item['countdown_text'][:55]}"
            )


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Overlay no-blocking PA clips after each play-end buzzer using silencedetect "
            "to locate the post-countdown silent window."
        )
    )
    parser.add_argument("--wav", type=Path, required=True, help="Source overhead .wav")
    parser.add_argument(
        "--report",
        type=Path,
        help="By-round report JSON (default: {wav_stem}_overhead_by_round_report.json beside wav)",
    )
    parser.add_argument(
        "--transcript",
        type=Path,
        help="Transcript JSON for countdown end times (default: {wav}.transcript.json)",
    )
    parser.add_argument("--clip", type=Path, help="No-blocking clip .wav to insert")
    parser.add_argument(
        "--clip-preset",
        choices=sorted(CLIP_PRESETS),
        default="three_minutes_no_blocking",
        help="Clip from --band-dir (default: three_minutes_no_blocking / Dance Vocal#31)",
    )
    parser.add_argument(
        "--band-dir",
        type=Path,
        default=DEFAULT_CLIP.parent.parent.parent,
        help="GarageBand .band directory containing Media/Audio Files",
    )
    parser.add_argument(
        "--offset-after-silence",
        type=float,
        default=3.0,
        help="Seconds after detected silence start to place clip (default: 3)",
    )
    parser.add_argument(
        "--search-window",
        type=float,
        default=180.0,
        help="Seconds after play-end countdown to search for silence (default: 180)",
    )
    parser.add_argument(
        "--silence-noise-db",
        type=float,
        default=-35.0,
        help="silencedetect noise threshold in dB (default: -35)",
    )
    parser.add_argument(
        "--min-silence-detect",
        type=float,
        default=0.3,
        help="Minimum silence duration for silencedetect in seconds (default: 0.3)",
    )
    parser.add_argument(
        "--min-after-countdown",
        type=float,
        default=3.0,
        help="Ignore silence earlier than this many seconds after countdown start (default: 3)",
    )
    parser.add_argument(
        "--min-no-blocking-silence",
        type=float,
        default=15.0,
        help="Prefer silence at least this long for the no-blocking window (default: 15)",
    )
    parser.add_argument(
        "--fallback-after-countdown-end",
        type=float,
        default=3.0,
        help="If silencedetect fails, seconds after transcript countdown end (default: 3)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output .wav path (default: {wav_stem}_with_no_blocking.wav)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print insertion plan only; do not write output",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Run verify_overhead_schedule.py --by-round on the output wav",
    )
    parser.add_argument(
        "--require-silence-verify",
        action="store_true",
        help="Fail if any insertion point is not verified silent",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.wav.exists():
        print(f"Error: WAV not found: {args.wav}", file=sys.stderr)
        return 1

    report_path = args.report or args.wav.with_name(
        f"{args.wav.stem}_overhead_by_round_report.json"
    )
    if not report_path.exists():
        print(
            f"Error: report not found: {report_path}\n"
            "Run verify_overhead_schedule.py --by-round first.",
            file=sys.stderr,
        )
        return 1

    clip_path = resolve_clip_path(args)
    if not clip_path.exists():
        print(f"Error: clip not found: {clip_path}", file=sys.stderr)
        return 1

    report = load_report(report_path)
    transcript = load_transcript(args.wav, args.transcript)
    insertions = compute_insertions(
        args.wav,
        report,
        transcript,
        args.offset_after_silence,
        args.search_window,
        args.silence_noise_db,
        args.min_silence_detect,
        args.min_after_countdown,
        args.min_no_blocking_silence,
        args.fallback_after_countdown_end,
    )
    valid = [item for item in insertions if item["insert_seconds"] is not None]
    if not valid:
        print("Error: no insertion points found in report.", file=sys.stderr)
        return 1

    print_insertion_plan(insertions, clip_path)

    unverified = [item for item in valid if not item.get("insert_verified_silent")]
    if unverified:
        print(f"\nWarning: {len(unverified)} insertion point(s) not verified silent.", file=sys.stderr)
        if args.require_silence_verify:
            return 1

    if args.dry_run:
        print(f"\nDry run: would insert {len(valid)} clip(s).")
        return 0

    output_path = args.output or args.wav.with_name(f"{args.wav.stem}_with_no_blocking.wav")
    wav_info = probe_audio(args.wav)
    insert_seconds = [item["insert_seconds"] for item in valid]

    cmd = build_ffmpeg_command(
        args.wav,
        clip_path,
        output_path,
        insert_seconds,
        wav_info["sample_rate"],
        wav_info["channels"],
    )
    print(f"\nWriting: {output_path}", file=sys.stderr)
    print(f"Inserting {len(insert_seconds)} clip(s) with ffmpeg ...", file=sys.stderr)
    subprocess.run(cmd, check=True)

    sidecar = output_path.with_suffix(output_path.suffix + ".injections.json")
    sidecar.write_text(
        json.dumps(
            {
                "source_wav": str(args.wav),
                "clip": str(clip_path),
                "offset_after_silence": args.offset_after_silence,
                "silence_noise_db": args.silence_noise_db,
                "insertions": insertions,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Insertion log: {sidecar}", file=sys.stderr)
    print(f"Done: {output_path}", file=sys.stderr)

    if args.verify:
        return run_verification(output_path, report, Path(__file__).resolve().parents[2])
    return 0


if __name__ == "__main__":
    sys.exit(main())
