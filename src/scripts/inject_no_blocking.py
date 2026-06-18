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
import re
import subprocess
import sys
from pathlib import Path

from overhead_inject_common import (
    build_ffmpeg_command,
    load_report,
    load_transcript,
    max_volume_db,
    probe_audio,
    run_verification,
    seconds_to_hms,
    write_injections_sidecar,
)

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


def silence_duration(silence: dict) -> float:
    return float(silence.get("duration") or 0.0)


def in_silence_search_window(
    silence: dict,
    countdown_start: float,
    min_after_countdown: float,
    max_offset: float,
    min_no_blocking_silence: float,
) -> bool:
    """True when silence plausibly begins after the play-end countdown/buzzer."""
    rel = silence["start"] - countdown_start
    if rel < 0 or rel > max_offset:
        return False
    if silence_duration(silence) >= min_no_blocking_silence:
        return True
    return rel >= min_after_countdown


def list_no_blocking_silence_candidates(
    silences: list[dict],
    countdown_start: float,
    min_after_countdown: float,
    min_no_blocking_silence: float,
    early_window: float = 45.0,
    late_window: float = 120.0,
) -> list[dict]:
    """Return silence windows earliest-first (first post-buzzer gap, not longest)."""
    seen: set[tuple[float, float | None]] = set()
    ordered: list[dict] = []

    for max_offset, min_duration in (
        (early_window, min_no_blocking_silence),
        (early_window, 2.0),
        (late_window, min_no_blocking_silence),
        (late_window, 2.0),
    ):
        for silence in silences:
            if silence_duration(silence) < min_duration:
                continue
            if not in_silence_search_window(
                silence,
                countdown_start,
                min_after_countdown,
                max_offset,
                min_no_blocking_silence,
            ):
                continue
            key = (silence["start"], silence.get("duration"))
            if key in seen:
                continue
            seen.add(key)
            ordered.append(silence)

    ordered.sort(key=lambda silence: silence["start"])
    return ordered


def speech_before_insert(
    round_data: dict,
    countdown_start: float,
    insert_at: float,
) -> dict | None:
    """Return report speech between countdown and insert (excluding the countdown cue itself)."""
    for item in round_data["speech"]:
        speech_at = float(item["wav_seconds"])
        if speech_at <= countdown_start + 0.5 or speech_at >= insert_at:
            continue
        if item["role"] == "countdown_play_end":
            continue
        return item
    return None


def validate_insert_point(
    wav_path: Path,
    round_data: dict,
    countdown_start: float,
    insert_at: float,
    noise_db: float,
    min_silence_detect: float,
    max_insert_volume_db: float = -45.0,
) -> dict:
    verified, verify_silence = is_silent_at(
        wav_path,
        insert_at,
        window_seconds=6.0,
        noise_db=noise_db,
        min_silence=min_silence_detect,
    )
    max_volume = max_volume_db(wav_path, insert_at)
    blocking_speech = speech_before_insert(round_data, countdown_start, insert_at)
    volume_ok = max_volume is not None and max_volume <= max_insert_volume_db
    speech_ok = blocking_speech is None
    confidence = "high" if verified and volume_ok and speech_ok else "low"

    return {
        "insert_verified_silent": verified,
        "verify_silence_window": verify_silence,
        "insert_max_volume_db": max_volume,
        "insert_volume_ok": volume_ok,
        "insert_speech_overlap": blocking_speech,
        "insert_confidence": confidence,
    }


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
        candidates = list_no_blocking_silence_candidates(
            silences,
            countdown_start,
            min_after_countdown,
            min_no_blocking_silence,
        )

        chosen_silence: dict | None = None
        insert_at: float
        method = "silencedetect"
        validation: dict = {}

        for candidate in candidates:
            candidate_insert = candidate["start"] + offset_after_silence
            validation = validate_insert_point(
                wav_path,
                round_data,
                countdown_start,
                candidate_insert,
                noise_db,
                min_silence_detect,
            )
            if validation["insert_confidence"] == "high":
                chosen_silence = candidate
                insert_at = candidate_insert
                break

        if chosen_silence is None and candidates:
            chosen_silence = candidates[0]
            insert_at = chosen_silence["start"] + offset_after_silence
            validation = validate_insert_point(
                wav_path,
                round_data,
                countdown_start,
                insert_at,
                noise_db,
                min_silence_detect,
            )
        elif chosen_silence is not None:
            pass
        elif transcript_end is not None:
            method = "transcript_end_fallback"
            chosen_silence = None
            insert_at = transcript_end + fallback_after_countdown_end
            validation = validate_insert_point(
                wav_path,
                round_data,
                countdown_start,
                insert_at,
                noise_db,
                min_silence_detect,
            )
        else:
            method = "countdown_start_fallback"
            chosen_silence = None
            insert_at = countdown_start + min_after_countdown + fallback_after_countdown_end
            validation = validate_insert_point(
                wav_path,
                round_data,
                countdown_start,
                insert_at,
                noise_db,
                min_silence_detect,
            )

        if chosen_silence is not None:
            silence_start = chosen_silence["start"]
            silence_duration_val = chosen_silence.get("duration")
        else:
            silence_start = None
            silence_duration_val = None

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
                "silence_duration_seconds": silence_duration_val,
                "insert_seconds": round(insert_at, 3),
                "insert_wav_timestamp": seconds_to_hms(insert_at),
                "insert_method": method,
                "insert_verified_silent": validation.get("insert_verified_silent", False),
                "verify_silence_window": validation.get("verify_silence_window"),
                "insert_max_volume_db": validation.get("insert_max_volume_db"),
                "insert_volume_ok": validation.get("insert_volume_ok"),
                "insert_speech_overlap": validation.get("insert_speech_overlap"),
                "insert_confidence": validation.get("insert_confidence", "low"),
                "countdown_text": countdown["text"],
            }
        )
    return insertions


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
        f"{'RND':<4} {'CD START':<10} {'SILENCE':<10} {'INSERT':<10} "
        f"{'CONF':<5} {'MAX dB':<8} {'METHOD'}"
    )
    print("-" * 85)
    for item in insertions:
        if item["insert_seconds"] is None:
            print(f"{item['round']:<4}  SKIP — {item['reason']}")
            continue
        silence = item.get("silence_start_hms") or "—"
        conf = item.get("insert_confidence", "?")
        max_db = item.get("insert_max_volume_db")
        max_db_str = f"{max_db:.1f}" if max_db is not None else "—"
        print(
            f"{item['round']:<4} "
            f"{item['play_end_countdown_wav']:<10} "
            f"{silence:<10} "
            f"{item['insert_wav_timestamp']:<10} "
            f"{conf:<5} "
            f"{max_db_str:<8} "
            f"{item['insert_method']}"
        )
        overlap = item.get("insert_speech_overlap")
        if overlap:
            print(
                f"     speech before insert: {overlap['wav_timestamp']} "
                f"[{overlap['role']}] {overlap['text'][:45]}"
            )
        elif item.get("silence_duration_seconds") is not None:
            cd_rel = item["silence_start_seconds"] - item["play_end_countdown_seconds"]
            print(
                f"     silence +{cd_rel:.1f}s after countdown, "
                f"duration={item['silence_duration_seconds']:.1f}s"
            )


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
    write_injections_sidecar(
        sidecar,
        {
            "source_wav": str(args.wav),
            "clip": str(clip_path),
            "offset_after_silence": args.offset_after_silence,
            "silence_noise_db": args.silence_noise_db,
            "insertions": insertions,
        },
    )
    print(f"Insertion log: {sidecar}", file=sys.stderr)
    print(f"Done: {output_path}", file=sys.stderr)

    if args.verify:
        return run_verification(output_path, report, Path(__file__).resolve().parents[2])
    return 0


if __name__ == "__main__":
    sys.exit(main())
