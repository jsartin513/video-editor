#!/usr/bin/env python3
"""
Insert no-blocking PA clips into a venue-wide overhead .wav after each play-end countdown.

Uses play-end countdown timestamps from a by-round overhead verification report and
overlays a short clip (default: Dance Vocal#31 "three minutes no blocking") at the
start of each round's silent no-blocking window.

Usage:
  python inject_no_blocking.py \\
    --wav "/path/to/BDL Throwdown 5 Full Timeline.wav" \\
    --report "/path/to/BDL Throwdown 5 Full Timeline_overhead_by_round_report.json"

  python inject_no_blocking.py --wav ... --report ... --dry-run
"""

from __future__ import annotations

import argparse
import json
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


def compute_insertions(
    report: dict,
    offset_after_play_end: float,
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

        insert_at = countdown["wav_seconds"] + offset_after_play_end
        insertions.append(
            {
                "round": round_data["round"],
                "schedule_label": round_data["schedule_label"],
                "play_end_countdown_wav": countdown["wav_timestamp"],
                "play_end_countdown_seconds": countdown["wav_seconds"],
                "insert_seconds": round(insert_at, 3),
                "insert_wav_timestamp": seconds_to_hms(insert_at),
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
    print(f"{'RND':<4} {'PLAY-END CD':<12} {'INSERT AT':<12} {'COUNTDOWN TEXT'}")
    print("-" * 90)
    for item in insertions:
        if item["insert_seconds"] is None:
            print(f"{item['round']:<4}  SKIP — {item['reason']}")
            continue
        text = item["countdown_text"][:50]
        if len(item["countdown_text"]) > 50:
            text += "…"
        print(
            f"{item['round']:<4} "
            f"{item['play_end_countdown_wav']:<12} "
            f"{item['insert_wav_timestamp']:<12} "
            f"{text}"
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
        description="Insert no-blocking PA clips after each play-end countdown in an overhead .wav."
    )
    parser.add_argument("--wav", type=Path, required=True, help="Source overhead .wav")
    parser.add_argument(
        "--report",
        type=Path,
        help="By-round report JSON (default: {wav_stem}_overhead_by_round_report.json beside wav)",
    )
    parser.add_argument(
        "--clip",
        type=Path,
        help="No-blocking clip .wav to insert",
    )
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
        "--offset-after-play-end",
        type=float,
        default=20.0,
        help="Seconds after play-end countdown start to place clip (default: 20)",
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
    insertions = compute_insertions(report, args.offset_after_play_end)
    valid = [item for item in insertions if item["insert_seconds"] is not None]
    if not valid:
        print("Error: no insertion points found in report.", file=sys.stderr)
        return 1

    print_insertion_plan(insertions, clip_path)

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
                "offset_after_play_end": args.offset_after_play_end,
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
