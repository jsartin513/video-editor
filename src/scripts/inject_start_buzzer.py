#!/usr/bin/env python3
"""
Insert Start buzzer clips into a venue-wide overhead .wav at each round's play start.

Uses play_start times from a by-round overhead verification report, then transcript
phrase-end detection to place the buzzer immediately after "Players line up / here we go".

Usage:
  python inject_start_buzzer.py \\
    --wav "/path/to/BDL Throwdown 5 Full Timeline_with_no_blocking.wav" \\
    --report "/path/to/..._overhead_by_round_report.json" \\
    --transcript "/path/to/BDL Throwdown 5 Full Timeline.wav.transcript.json"

  python inject_start_buzzer.py --wav ... --report ... --dry-run
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

DEFAULT_BAND_DIR = Path(
    "/Users/jessicasartin/Downloads/15 min round - foam NS 8.5 (no time limit on NB).band"
)
DEFAULT_CLIP = DEFAULT_BAND_DIR / "Media/Audio Files/Start buzzer"

PLAY_START_TEXT_RE = re.compile(r"players line up|here we go", re.I)

MAX_PHRASE_DURATION_FROM_ANCHOR = 7.0


def segment_play_start_end(segment: dict) -> float:
    """Return a plausible end time for a play-start transcript segment."""
    start = float(segment["start"])
    end = float(segment.get("end", start))
    text = segment.get("text", "").lower()
    has_line_up = "players line up" in text or "line up" in text
    has_here_we_go = "here we go" in text

    if has_line_up and has_here_we_go:
        max_duration = 4.5
    elif has_here_we_go:
        max_duration = 2.5
    elif has_line_up:
        max_duration = 3.0
    else:
        max_duration = 4.0

    if end - start > max_duration:
        end = start + max_duration
    return end


def estimate_phrase_end_from_report(play_start_cues: list[dict]) -> float:
    first = min(play_start_cues, key=lambda item: item["wav_seconds"])
    last = max(play_start_cues, key=lambda item: item["wav_seconds"])
    anchor = float(first["wav_seconds"])
    if len(play_start_cues) == 1:
        return anchor + 4.0
    return float(last["wav_seconds"]) + 2.0


def find_play_start_cues(round_data: dict) -> list[dict]:
    return [item for item in round_data["speech"] if item["role"] == "play_start"]


def find_halfway(round_data: dict) -> dict | None:
    candidates = [item for item in round_data["speech"] if item["role"] == "halfway"]
    if not candidates:
        return None
    return min(candidates, key=lambda item: item["wav_seconds"])


def looks_like_play_start(text: str) -> bool:
    return bool(PLAY_START_TEXT_RE.search(text.lower()))


def play_start_phrase_end_from_transcript(
    transcript: dict | None,
    first_play_start: float,
    search_seconds: float = 12.0,
) -> float | None:
    if not transcript:
        return None

    end: float | None = None
    window_start = first_play_start - 0.5
    window_end = first_play_start + search_seconds
    for segment in transcript.get("segments", []):
        start = float(segment["start"])
        if start < window_start or start > window_end:
            continue
        if not looks_like_play_start(segment.get("text", "")):
            continue
        segment_end = segment_play_start_end(segment)
        end = segment_end if end is None else max(end, segment_end)
    return end


def speech_overlap_before_insert(
    round_data: dict,
    first_play_start: float,
    insert_at: float,
) -> dict | None:
    """Return non-play_start speech between play_start anchor and insert."""
    for item in round_data["speech"]:
        speech_at = float(item["wav_seconds"])
        if speech_at <= first_play_start + 0.5 or speech_at >= insert_at:
            continue
        if item["role"] == "play_start":
            continue
        return item
    return None


def validate_insert_point(
    wav_path: Path,
    round_data: dict,
    first_play_start: float,
    insert_at: float,
    phrase_end: float | None,
    max_loud_volume_db: float = -20.0,
) -> dict:
    max_volume = max_volume_db(wav_path, insert_at)
    blocking_speech = speech_overlap_before_insert(round_data, first_play_start, insert_at)
    phrase_clear = phrase_end is None or insert_at >= phrase_end - 0.1
    speech_ok = blocking_speech is None
    volume_ok = max_volume is None or max_volume <= max_loud_volume_db
    halfway = find_halfway(round_data)
    before_halfway = (
        halfway is None or insert_at < float(halfway["wav_seconds"])
    )
    confidence = "high" if phrase_clear and speech_ok and before_halfway else "low"

    return {
        "insert_max_volume_db": max_volume,
        "insert_volume_ok": volume_ok,
        "insert_speech_overlap": blocking_speech,
        "insert_phrase_clear": phrase_clear,
        "insert_before_halfway": before_halfway,
        "insert_confidence": confidence,
    }


def compute_insertions(
    wav_path: Path,
    report: dict,
    transcript: dict | None,
    offset_after_phrase_end: float,
    fallback_offset_after_play_start: float,
    search_seconds: float,
) -> list[dict]:
    insertions: list[dict] = []

    for round_data in report["rounds"]:
        play_start_cues = find_play_start_cues(round_data)
        if not play_start_cues:
            insertions.append(
                {
                    "round": round_data["round"],
                    "insert_seconds": None,
                    "reason": "no play_start found in report speech",
                }
            )
            continue

        first_play_start = min(play_start_cues, key=lambda item: item["wav_seconds"])
        last_play_start = max(play_start_cues, key=lambda item: item["wav_seconds"])
        anchor_seconds = float(first_play_start["wav_seconds"])
        transcript_end = play_start_phrase_end_from_transcript(
            transcript,
            anchor_seconds,
            search_seconds,
        )
        report_end = estimate_phrase_end_from_report(play_start_cues)

        if transcript_end is not None and (
            transcript_end - anchor_seconds <= MAX_PHRASE_DURATION_FROM_ANCHOR
        ):
            phrase_end = transcript_end
            method = "transcript_phrase_end"
        elif transcript is not None:
            phrase_end = report_end
            method = "report_estimate"
        else:
            phrase_end = anchor_seconds + fallback_offset_after_play_start
            method = "play_start_fallback"

        insert_at = phrase_end + offset_after_phrase_end

        validation = validate_insert_point(
            wav_path,
            round_data,
            anchor_seconds,
            insert_at,
            phrase_end,
        )

        insertions.append(
            {
                "round": round_data["round"],
                "schedule_label": round_data["schedule_label"],
                "play_start_wav": first_play_start["wav_timestamp"],
                "play_start_seconds": anchor_seconds,
                "play_start_text": first_play_start["text"],
                "play_start_segments": len(play_start_cues),
                "last_play_start_wav": last_play_start["wav_timestamp"],
                "last_play_start_seconds": float(last_play_start["wav_seconds"]),
                "last_play_start_text": last_play_start["text"],
                "phrase_end_transcript": phrase_end,
                "phrase_end_transcript_hms": (
                    seconds_to_hms(phrase_end) if phrase_end is not None else None
                ),
                "insert_seconds": round(insert_at, 3),
                "insert_wav_timestamp": seconds_to_hms(insert_at),
                "insert_method": method,
                "insert_max_volume_db": validation.get("insert_max_volume_db"),
                "insert_volume_ok": validation.get("insert_volume_ok"),
                "insert_speech_overlap": validation.get("insert_speech_overlap"),
                "insert_phrase_clear": validation.get("insert_phrase_clear"),
                "insert_before_halfway": validation.get("insert_before_halfway"),
                "insert_confidence": validation.get("insert_confidence", "low"),
            }
        )
    return insertions


def resolve_clip_path(args: argparse.Namespace) -> Path:
    if args.clip:
        return args.clip.expanduser()
    return args.band_dir.expanduser() / "Media/Audio Files/Start buzzer"


def resolve_transcript_path(args: argparse.Namespace) -> Path | None:
    if args.transcript:
        return args.transcript.expanduser()
    # Original export transcript (timestamps unchanged after no-blocking overlay).
    stem = args.wav.stem.replace("_with_no_blocking", "")
    candidate = args.wav.with_name(f"{stem}.transcript.json")
    return candidate if candidate.exists() else None


def resolve_upstream_injections(args: argparse.Namespace) -> Path | None:
    if args.upstream_injections:
        path = args.upstream_injections.expanduser()
        return path if path.exists() else None
    candidate = args.wav.with_suffix(args.wav.suffix + ".injections.json")
    return candidate if candidate.exists() else None


def print_insertion_plan(insertions: list[dict], clip_path: Path) -> None:
    clip_info = probe_audio(clip_path)
    print(f"Clip: {clip_path}")
    print(f"  duration={clip_info['duration']:.1f}s")
    print()
    print(
        f"{'RND':<4} {'PLAY START':<10} {'PHRASE END':<10} {'INSERT':<10} "
        f"{'CONF':<5} {'MAX dB':<8} {'METHOD'}"
    )
    print("-" * 85)
    for item in insertions:
        if item["insert_seconds"] is None:
            print(f"{item['round']:<4}  SKIP — {item['reason']}")
            continue
        phrase_end = item.get("phrase_end_transcript_hms") or "—"
        conf = item.get("insert_confidence", "?")
        max_db = item.get("insert_max_volume_db")
        max_db_str = f"{max_db:.1f}" if max_db is not None else "—"
        print(
            f"{item['round']:<4} "
            f"{item['play_start_wav']:<10} "
            f"{phrase_end:<10} "
            f"{item['insert_wav_timestamp']:<10} "
            f"{conf:<5} "
            f"{max_db_str:<8} "
            f"{item['insert_method']}"
        )
        if item.get("play_start_segments", 1) > 1:
            print(
                f"     split phrase: {item['play_start_text']!r} → "
                f"{item['last_play_start_text']!r}"
            )
        overlap = item.get("insert_speech_overlap")
        if overlap:
            print(
                f"     speech before insert: {overlap['wav_timestamp']} "
                f"[{overlap['role']}] {overlap['text'][:45]}"
            )
        if not item.get("insert_before_halfway", True):
            print("     warning: insert at or after halfway cue")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Overlay Start buzzer clips at each round's play start, immediately after "
            "'Players line up / here we go'."
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
        help="Transcript JSON (default: original {stem}.transcript.json beside wav dir)",
    )
    parser.add_argument("--clip", type=Path, help="Start buzzer clip to insert")
    parser.add_argument(
        "--band-dir",
        type=Path,
        default=DEFAULT_BAND_DIR,
        help="GarageBand .band directory containing Media/Audio Files",
    )
    parser.add_argument(
        "--offset-after-phrase-end",
        type=float,
        default=0.0,
        help="Seconds after detected phrase end to place clip (default: 0)",
    )
    parser.add_argument(
        "--fallback-offset-after-play-start",
        type=float,
        default=4.0,
        help="Seconds after play_start when transcript unavailable (default: 4)",
    )
    parser.add_argument(
        "--search-seconds",
        type=float,
        default=12.0,
        help="Seconds after play_start to search transcript (default: 12)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output .wav path (default: {wav_stem}_with_no_blocking_and_start_buzzer.wav)",
    )
    parser.add_argument(
        "--upstream-injections",
        type=Path,
        help="Prior injections sidecar (default: {wav}.injections.json)",
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
        "--require-phrase-clear",
        action="store_true",
        help="Fail if any insertion overlaps speech or lands before phrase end",
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
    transcript_path = resolve_transcript_path(args)
    transcript = load_transcript(args.wav, transcript_path) if transcript_path else None
    if transcript is None and transcript_path is None:
        print(
            "Warning: no transcript found; using play_start + fallback offset.",
            file=sys.stderr,
        )

    insertions = compute_insertions(
        args.wav,
        report,
        transcript,
        args.offset_after_phrase_end,
        args.fallback_offset_after_play_start,
        args.search_seconds,
    )
    valid = [item for item in insertions if item["insert_seconds"] is not None]
    if not valid:
        print("Error: no insertion points found in report.", file=sys.stderr)
        return 1

    print_insertion_plan(insertions, clip_path)

    unclear = [
        item
        for item in valid
        if not item.get("insert_phrase_clear") or item.get("insert_speech_overlap")
    ]
    if unclear:
        print(
            f"\nWarning: {len(unclear)} insertion point(s) have speech overlap or unclear phrase end.",
            file=sys.stderr,
        )
        if args.require_phrase_clear:
            return 1

    if args.dry_run:
        print(f"\nDry run: would insert {len(valid)} clip(s).")
        return 0

    output_path = args.output
    if output_path is None:
        stem = args.wav.stem
        if stem.endswith("_with_no_blocking"):
            out_stem = stem + "_and_start_buzzer"
        else:
            out_stem = f"{stem}_with_no_blocking_and_start_buzzer"
        output_path = args.wav.with_name(f"{out_stem}.wav")
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

    upstream = resolve_upstream_injections(args)
    sidecar = output_path.with_suffix(output_path.suffix + ".injections.json")
    payload: dict = {
        "source_wav": str(args.wav),
        "clip": str(clip_path),
        "injection_type": "start_buzzer",
        "offset_after_phrase_end": args.offset_after_phrase_end,
        "fallback_offset_after_play_start": args.fallback_offset_after_play_start,
        "insertions": insertions,
    }
    if upstream:
        payload["upstream_injections"] = str(upstream)
    write_injections_sidecar(sidecar, payload)
    print(f"Insertion log: {sidecar}", file=sys.stderr)
    print(f"Done: {output_path}", file=sys.stderr)

    if args.verify:
        return run_verification(output_path, report, Path(__file__).resolve().parents[2])
    return 0


if __name__ == "__main__":
    sys.exit(main())
