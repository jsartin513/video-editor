#!/usr/bin/env python3
"""
Verify that a venue-wide overhead .wav aligns with per-court schedule JSONL files.

Builds an expected announcement timeline from the Throw Down PA template
(measured from BDL Throwdown 5 Full Timeline.wav): court calls, transition
warnings, play start, halfway, 90s/30s warnings, and countdown within each
25-minute JSONL slot.

Usage:
  python verify_overhead_schedule.py \\
    --wav /path/to/overhead.wav \\
    --schedule-dir src/output/June2026Tournament/schedule/generated \\
    --date 2026-06-20 \\
    --courts 2,3,4 \\
    --wav-start-time 09:00 \\
    --timeline-only
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

COURT_WORDS = {
    1: ("one", "1"),
    2: ("two", "2"),
    3: ("three", "3"),
    4: ("four", "4"),
    5: ("five", "5"),
    6: ("six", "6"),
}

# Offsets from JSONL slot start_time, derived from BDL Throwdown 5 Full Timeline.wav.
THROWDOWN_25MIN_MARKERS: list[tuple[str, int, bool, str]] = [
    ("court_announcement", 0, False, "Court matchup call"),
    ("transition_2min", 121, True, "Two minutes to get to your next court"),
    ("transition_1min", 173, True, "One minute to get to your court"),
    ("transition_30sec", 202, True, "30 seconds to get to your court"),
    ("play_start", 240, True, "Players line up / here we go"),
    ("halfway", 780, True, "Halfway through"),
    ("ninety_seconds", 1235, True, "90 seconds remaining"),
    ("thirty_seconds", 1294, True, "30 seconds remaining"),
    ("countdown", 1496, True, "Countdown (10→1 or 9→1)"),
]

EVENT_CUES: dict[str, list[str]] = {
    "court_announcement": [
        r"versus",
        r"vs\.?",
        r"home team",
        r"away team",
        r"referee",
    ],
    "transition_2min": [
        r"two minutes to get",
        r"next court",
    ],
    "transition_1min": [
        r"one minute to get",
        r"your court",
    ],
    "transition_30sec": [
        r"30 seconds to get",
        r"30 seconds.*court",
    ],
    "play_start": [
        r"players line up",
        r"here we go",
    ],
    "halfway": [
        r"halfway",
        r"way through",
    ],
    "ninety_seconds": [
        r"90 seconds",
        r"ninety seconds",
    ],
    "thirty_seconds": [
        r"30 seconds",
    ],
    "countdown": [
        r"\b10\b.*\b9\b",
        r"\b9\b.*\b8\b.*\b7\b",
        r"\b8\b.*\b7\b.*\b6\b",
        r"five, four",
        r"four, three",
        r"\b3, 2, 1\b",
        r"\b2, 1\b",
    ],
}

VENUE_WIDE_EVENTS = {m[0] for m in THROWDOWN_25MIN_MARKERS if m[2]}

VENUE_BUNDLE_CUE_TYPES = [
    "transition_2min",
    "transition_1min",
    "transition_30sec",
    "play_start",
    "halfway",
    "ninety_seconds",
    "thirty_seconds",
    "countdown",
]

_refine_model_cache: dict[str, Any] = {}


@dataclass
class Game:
    home_team: str
    away_team: str
    start_time: str
    minutes: int
    court: str
    court_num: int
    round: str = ""
    type: str = ""


@dataclass
class ExpectedEvent:
    wall_time: str
    wall_seconds: int
    wav_offset_seconds: float
    event_type: str
    court_num: int
    court: str
    home_team: str
    away_team: str
    round: str
    venue_wide: bool = False
    label: str = ""
    skipped: bool = False
    skip_reason: str = ""


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str


@dataclass
class MatchResult:
    expected: ExpectedEvent
    matched: bool
    actual_start: float | None = None
    drift_seconds: float | None = None
    confidence: float = 0.0
    matched_text: str = ""
    status: str = "missed"


@dataclass
class VerificationReport:
    wav_path: str
    schedule_date: str
    wav_start_time: str
    round_template: str = "throwdown_25min"
    inferred_wav_start_time: str | None = None
    wav_duration_seconds: float | None = None
    tolerance_seconds: int = 90
    skip_ranges: list[tuple[str, str]] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)
    summary: dict = field(default_factory=dict)
    orphan_segments: list[dict] = field(default_factory=list)


def time_to_seconds(time_str: str) -> int:
    time_str = time_str.strip()
    if re.match(r"^\d{1,2}:\d{2}:\d{2}$", time_str):
        h, m, s = (int(x) for x in time_str.split(":"))
        return h * 3600 + m * 60 + s
    if re.match(r"^\d{1,2}:\d{2}$", time_str):
        h, m = (int(x) for x in time_str.split(":"))
        return h * 3600 + m * 60
    raise ValueError(f"Invalid time format: {time_str!r}")


def seconds_to_hms(total_seconds: float) -> str:
    total = max(0, int(round(total_seconds)))
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def seconds_to_hm(total_seconds: int) -> str:
    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    return f"{h:02d}:{m:02d}"


def normalize_team(name: str) -> str:
    text = name.lower().strip()
    text = re.sub(r"^the\s+", "", text)
    text = re.sub(r"[^\w\s]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_skip_ranges(ranges: Iterable[str]) -> list[tuple[int, int]]:
    parsed: list[tuple[int, int]] = []
    for item in ranges:
        if "-" not in item:
            raise ValueError(f"Invalid skip range (expected HH:MM-HH:MM): {item!r}")
        start_str, end_str = item.split("-", 1)
        parsed.append((time_to_seconds(start_str.strip()), time_to_seconds(end_str.strip())))
    return parsed


def in_skip_range(wall_seconds: int, skip_ranges: list[tuple[int, int]]) -> bool:
    for start, end in skip_ranges:
        if start <= wall_seconds < end:
            return True
    return False


def load_games(schedule_dir: Path, date: str, courts: list[int]) -> list[Game]:
    games: list[Game] = []
    for court_num in courts:
        jsonl_path = schedule_dir / f"{date}_court{court_num}.jsonl"
        if not jsonl_path.exists():
            raise FileNotFoundError(f"Schedule file not found: {jsonl_path}")
        with jsonl_path.open(encoding="utf-8") as handle:
            for line_num, line in enumerate(handle, start=1):
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                start_time = data["start_time"]
                if re.match(r"^\d{1,2}:\d{2}:\d{2}$", start_time):
                    raise ValueError(
                        f"{jsonl_path}:{line_num}: offset-mode start_time not supported "
                        f"for overhead verification ({start_time!r})"
                    )
                court_label = data.get("court") or f"Court {court_num}"
                games.append(
                    Game(
                        home_team=data["home_team"],
                        away_team=data["away_team"],
                        start_time=start_time,
                        minutes=int(data["minutes"]),
                        court=court_label,
                        court_num=court_num,
                        round=data.get("round", ""),
                        type=data.get("type", ""),
                    )
                )
    games.sort(key=lambda g: (time_to_seconds(g.start_time), g.court_num))
    return games


def build_expected_events(
    games: list[Game],
    wav_start_time: str,
    skip_ranges: list[tuple[int, int]],
    skip_before: str | None = None,
) -> list[ExpectedEvent]:
    anchor_seconds = time_to_seconds(wav_start_time)
    skip_before_seconds = time_to_seconds(skip_before) if skip_before else None
    events: list[ExpectedEvent] = []

    slots: dict[int, list[Game]] = {}
    for game in games:
        slots.setdefault(time_to_seconds(game.start_time), []).append(game)

    for slot_start, slot_games in sorted(slots.items()):
        for event_type, offset, venue_wide, label in THROWDOWN_25MIN_MARKERS:
            wall_seconds = slot_start + offset
            skipped = False
            skip_reason = ""
            if skip_before_seconds is not None and wall_seconds < skip_before_seconds:
                skipped = True
                skip_reason = f"before --skip-before {skip_before}"
            elif in_skip_range(wall_seconds, skip_ranges):
                skipped = True
                skip_reason = "in --skip-ranges"

            if venue_wide:
                ref = slot_games[0]
                events.append(
                    ExpectedEvent(
                        wall_time=seconds_to_hm(wall_seconds),
                        wall_seconds=wall_seconds,
                        wav_offset_seconds=float(wall_seconds - anchor_seconds),
                        event_type=event_type,
                        court_num=0,
                        court="ALL",
                        home_team="",
                        away_team="",
                        round=ref.round,
                        venue_wide=True,
                        label=label,
                        skipped=skipped,
                        skip_reason=skip_reason,
                    )
                )
                continue

            for game in slot_games:
                events.append(
                    ExpectedEvent(
                        wall_time=seconds_to_hm(wall_seconds),
                        wall_seconds=wall_seconds,
                        wav_offset_seconds=float(wall_seconds - anchor_seconds),
                        event_type=event_type,
                        court_num=game.court_num,
                        court=game.court,
                        home_team=game.home_team,
                        away_team=game.away_team,
                        round=game.round,
                        venue_wide=False,
                        label=label,
                        skipped=skipped,
                        skip_reason=skip_reason,
                    )
                )

    events.sort(key=lambda e: (e.wall_seconds, e.venue_wide, e.court_num, e.event_type))
    return events


def group_games_by_slot(games: list[Game]) -> list[tuple[int, list[Game]]]:
    slots: dict[int, list[Game]] = {}
    for game in games:
        slots.setdefault(time_to_seconds(game.start_time), []).append(game)
    return sorted(slots.items())


def build_slot_events(
    slot_games: list[Game],
    slot_start_seconds: int,
    slot_anchor_wav: float,
    skip_ranges: list[tuple[int, int]],
    skip_before: str | None = None,
) -> list[ExpectedEvent]:
    skip_before_seconds = time_to_seconds(skip_before) if skip_before else None
    events: list[ExpectedEvent] = []

    for event_type, offset, venue_wide, label in THROWDOWN_25MIN_MARKERS:
        wall_seconds = slot_start_seconds + offset
        skipped = False
        skip_reason = ""
        if skip_before_seconds is not None and wall_seconds < skip_before_seconds:
            skipped = True
            skip_reason = f"before --skip-before {skip_before}"
        elif in_skip_range(wall_seconds, skip_ranges):
            skipped = True
            skip_reason = "in --skip-ranges"

        wav_offset = slot_anchor_wav + offset

        if venue_wide:
            ref = slot_games[0]
            events.append(
                ExpectedEvent(
                    wall_time=seconds_to_hm(wall_seconds),
                    wall_seconds=wall_seconds,
                    wav_offset_seconds=wav_offset,
                    event_type=event_type,
                    court_num=0,
                    court="ALL",
                    home_team="",
                    away_team="",
                    round=ref.round,
                    venue_wide=True,
                    label=label,
                    skipped=skipped,
                    skip_reason=skip_reason,
                )
            )
            continue

        for game in slot_games:
            events.append(
                ExpectedEvent(
                    wall_time=seconds_to_hm(wall_seconds),
                    wall_seconds=wall_seconds,
                    wav_offset_seconds=wav_offset,
                    event_type=event_type,
                    court_num=game.court_num,
                    court=game.court,
                    home_team=game.home_team,
                    away_team=game.away_team,
                    round=game.round,
                    venue_wide=False,
                    label=label,
                    skipped=skipped,
                    skip_reason=skip_reason,
                )
            )

    events.sort(key=lambda e: (e.venue_wide, e.court_num, e.event_type))
    return events


def infer_slot_anchor_wav(
    slot_games: list[Game],
    segments: list[TranscriptSegment],
    hint_wav: float,
    tolerance: int,
    min_confidence: float,
) -> float | None:
    search_start = max(0, hint_wav - tolerance * 2)
    search_end = hint_wav + tolerance * 2 + 300

    for offset, pattern in [
        (240, r"here we go|players line up"),
        (0, r"versus|vs\.?|home team"),
    ]:
        target = hint_wav + offset
        best_start: float | None = None
        best_score = 0.0
        for segment in segments:
            if segment.start < search_start or segment.start > search_end:
                continue
            if abs(segment.start - target) > tolerance * 2 + (120 if offset == 0 else 60):
                continue
            text = segment.text.lower()
            if not re.search(pattern, text):
                continue
            if offset == 240:
                return segment.start - 240
            for game in slot_games:
                probe = ExpectedEvent(
                    wall_time="",
                    wall_seconds=0,
                    wav_offset_seconds=0,
                    event_type="court_announcement",
                    court_num=game.court_num,
                    court=game.court,
                    home_team=game.home_team,
                    away_team=game.away_team,
                    round=game.round,
                )
                score = score_segment(probe, segment)
                if score >= min_confidence and score > best_score:
                    best_score = score
                    best_start = segment.start
        if best_start is not None:
            return best_start

    return None


def match_slot_events(
    events: list[ExpectedEvent],
    segments: list[TranscriptSegment],
    tolerance: int,
    min_confidence: float,
) -> list[MatchResult]:
    results: list[MatchResult] = []
    used_venue_segments: set[int] = set()

    court_events = [e for e in events if e.event_type == "court_announcement" and not e.skipped]
    venue_events = [e for e in events if e.event_type != "court_announcement"]

    for event in court_events:
        if event.skipped:
            results.append(MatchResult(expected=event, matched=False, status="skipped"))
            continue
        window_start = max(0, event.wav_offset_seconds - tolerance)
        window_end = event.wav_offset_seconds + tolerance + 120

        best_idx: int | None = None
        best_score = 0.0
        for idx, segment in enumerate(segments):
            if segment.start < window_start or segment.start > window_end:
                continue
            score = score_segment(event, segment)
            if score > best_score:
                best_score = score
                best_idx = idx

        if best_idx is None or best_score < min_confidence:
            results.append(
                MatchResult(expected=event, matched=False, confidence=best_score, status="missed")
            )
            continue

        segment = segments[best_idx]
        results.append(
            MatchResult(
                expected=event,
                matched=True,
                actual_start=segment.start,
                drift_seconds=segment.start - event.wav_offset_seconds,
                confidence=best_score,
                matched_text=segment.text.strip(),
                status="matched",
            )
        )

    for event in venue_events:
        if event.skipped:
            results.append(MatchResult(expected=event, matched=False, status="skipped"))
            continue

        threshold = 0.35
        window_start = event.wav_offset_seconds - tolerance
        window_end = event.wav_offset_seconds + tolerance

        best_idx: int | None = None
        best_score = 0.0
        for idx, segment in enumerate(segments):
            if idx in used_venue_segments:
                continue
            if segment.start < window_start or segment.start > window_end:
                continue
            score = score_segment(event, segment)
            if score > best_score:
                best_score = score
                best_idx = idx

        if best_idx is None or best_score < threshold:
            results.append(
                MatchResult(
                    expected=event,
                    matched=False,
                    confidence=best_score,
                    status="missed",
                )
            )
            continue

        segment = segments[best_idx]
        used_venue_segments.add(best_idx)
        results.append(
            MatchResult(
                expected=event,
                matched=True,
                actual_start=segment.start,
                drift_seconds=segment.start - event.wav_offset_seconds,
                confidence=best_score,
                matched_text=segment.text.strip(),
                status="matched",
            )
        )

    results.sort(
        key=lambda r: (
            r.expected.venue_wide,
            r.expected.court_num,
            r.expected.event_type,
        )
    )
    return results


def format_anchor_offset(offset_seconds: float) -> str:
    sign = "+" if offset_seconds >= 0 else "-"
    rel_m, rel_s = divmod(abs(int(round(offset_seconds))), 60)
    return f"{sign}{rel_m}:{rel_s:02d}"


def collect_slot_speech(
    segments: list[TranscriptSegment],
    slot_anchor: float,
    wav_start_seconds: int,
    pre_seconds: int = 30,
    post_seconds: int = 26 * 60,
) -> list[dict]:
    window_start = slot_anchor - pre_seconds
    window_end = slot_anchor + post_seconds
    items: list[dict] = []

    for segment in segments:
        if segment.start < window_start or segment.start > window_end:
            continue
        text = segment.text.strip()
        if not text:
            continue
        offset = segment.start - slot_anchor
        wall_seconds = wav_start_seconds + int(segment.start)
        items.append(
            {
                "wav_seconds": round(segment.start, 2),
                "wav_timestamp": seconds_to_hms(segment.start),
                "wall_time": seconds_to_hm(wall_seconds),
                "offset_seconds": round(offset, 1),
                "offset": format_anchor_offset(offset),
                "text": text,
                "cues": venue_cues_in_text(text),
            }
        )

    items.sort(key=lambda item: item["wav_seconds"])
    return items


def print_slot_transcript(
    speech_items: list[dict],
) -> None:
    print("  --- exact phrases in audio ---")
    if not speech_items:
        print("  (no speech detected in this window)")
    else:
        for item in speech_items:
            cue_str = f"  [{', '.join(item['cues'])}]" if item["cues"] else ""
            print(
                f"  {item['wav_timestamp']}  ({item['offset']}){cue_str}  {item['text']}"
            )
    print()


def serialize_refinements(refinements: list[dict], wav_start_seconds: int, slot_anchor: float) -> list[dict]:
    serialized: list[dict] = []
    for item in refinements:
        refined_speech = collect_slot_speech(
            item["refined"],
            slot_anchor=slot_anchor,
            wav_start_seconds=wav_start_seconds,
            pre_seconds=0,
            post_seconds=26 * 60,
        )
        serialized.append(
            {
                "original_wav_seconds": round(item["original_start"], 2),
                "original_wav_timestamp": seconds_to_hms(item["original_start"]),
                "original_text": item["original_text"],
                "bundled_cues": item["cues"],
                "refined": refined_speech,
            }
        )
    return serialized


def serialize_match_results(results: list[MatchResult]) -> list[dict]:
    serialized: list[dict] = []
    for result in results:
        serialized.append(
            {
                "expected": asdict(result.expected),
                "matched": result.matched,
                "actual_start": result.actual_start,
                "actual_wav_timestamp": (
                    seconds_to_hms(result.actual_start) if result.actual_start is not None else None
                ),
                "drift_seconds": result.drift_seconds,
                "confidence": round(result.confidence, 3),
                "matched_text": result.matched_text,
                "status": result.status,
            }
        )
    return serialized


def write_by_round_phrases_file(reports: list[dict], output_path: Path) -> None:
    lines: list[str] = []
    for report in reports:
        lines.append(
            f"Round {report['round']} ({report['schedule_label']}, wall {report['wall_start']})  "
            f"anchor {seconds_to_hms(report['slot_anchor_wav'])}"
        )
        lines.append(f"{'WAV':<12} {'OFFSET':<8} {'WALL':<8} {'TEXT'}")
        lines.append("-" * 90)
        for item in report["speech"]:
            cue_note = f"  [{', '.join(item['cues'])}]" if item["cues"] else ""
            lines.append(
                f"{item['wav_timestamp']:<12} {item['offset']:<8} {item['wall_time']:<8} "
                f"{item['text']}{cue_note}"
            )
        lines.append("")
    output_path.write_text("\n".join(lines), encoding="utf-8")


def write_by_round_report(
    reports: list[dict],
    output_path: Path,
    wav_path: Path,
    wav_start_time: str,
    tolerance: int,
    refine_bundled: bool,
) -> None:
    passed = sum(1 for report in reports if report["summary"]["match_rate"] >= 0.8)
    payload = {
        "wav_path": str(wav_path),
        "wav_start_time": wav_start_time,
        "mode": "by_round",
        "tolerance_seconds": tolerance,
        "refine_bundled": refine_bundled,
        "rounds_passed": passed,
        "rounds_total": len(reports),
        "rounds": [
            {
                "round": report["round"],
                "schedule_label": report["schedule_label"],
                "wall_start": report["wall_start"],
                "slot_anchor_wav_seconds": report["slot_anchor_wav"],
                "slot_anchor_wav_timestamp": seconds_to_hms(report["slot_anchor_wav"]),
                "anchor_source": report["anchor_source"],
                "schedule_hint_wav_seconds": report["schedule_hint_wav"],
                "anchor_drift_seconds": report["anchor_drift"],
                "bundled_segments_refined": report["bundled_segments_refined"],
                "matchups": report["matchups"],
                "summary": report["summary"],
                "speech": report["speech"],
                "refined_bundles": report.get("refined_bundles", []),
                "matches": report["matches"],
            }
            for report in reports
        ],
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"By-round report: {output_path}", file=sys.stderr)


def verify_by_round(
    games: list[Game],
    segments: list[TranscriptSegment],
    wav_path: Path,
    wav_start_time: str,
    tolerance: int,
    min_confidence: float,
    skip_ranges: list[tuple[int, int]],
    skip_before: str | None,
    refine_bundled: bool = True,
    refine_model: str = "base",
    refine_chunk_sec: int = 8,
    refine_cache: dict | None = None,
    round_filter: int | None = None,
    verbose: bool = False,
) -> list[dict]:
    global_anchor = time_to_seconds(wav_start_time)
    round_reports: list[dict] = []

    for round_idx, (slot_start, slot_games) in enumerate(group_games_by_slot(games), start=1):
        if round_filter is not None and round_idx != round_filter:
            continue

        slot_games.sort(key=lambda g: g.court_num)
        ref = slot_games[0]
        hint_wav = float(slot_start - global_anchor)
        slot_anchor = infer_slot_anchor_wav(
            slot_games, segments, hint_wav, tolerance, min_confidence
        )
        anchor_source = "inferred"
        if slot_anchor is None:
            slot_anchor = hint_wav
            anchor_source = "schedule_hint"

        events = build_slot_events(
            slot_games, slot_start, slot_anchor, skip_ranges, skip_before
        )
        slot_segments = segments
        refinements: list[dict] = []
        if refine_bundled:
            slot_segments, refinements = augment_slot_segments(
                segments,
                slot_anchor,
                wav_path,
                refine_model,
                refine_chunk_sec,
                refine_cache,
            )

        results = match_slot_events(events, slot_segments, tolerance, min_confidence)
        summary = build_summary(results, sorted({g.court_num for g in slot_games}))
        speech = collect_slot_speech(
            slot_segments,
            slot_anchor,
            global_anchor,
        )
        refined_bundles = serialize_refinements(refinements, global_anchor, slot_anchor)

        report = {
            "round": round_idx,
            "schedule_label": ref.round,
            "wall_start": seconds_to_hm(slot_start),
            "slot_anchor_wav": round(slot_anchor, 1),
            "anchor_source": anchor_source,
            "schedule_hint_wav": hint_wav,
            "anchor_drift": round(slot_anchor - hint_wav, 1),
            "bundled_segments_refined": len(refinements),
            "matchups": {
                g.court_num: f"{g.home_team} vs {g.away_team}" for g in slot_games
            },
            "summary": summary,
            "speech": speech,
            "refined_bundles": refined_bundles,
            "matches": serialize_match_results(results),
            "results": results,
        }
        round_reports.append(report)

        status = "PASS" if summary["match_rate"] >= 0.8 else "FAIL"
        print(
            f"Round {round_idx:2d} ({ref.round}, {seconds_to_hm(slot_start)})  "
            f"anchor {seconds_to_hms(slot_anchor)} ({anchor_source}, drift {slot_anchor - hint_wav:+.0f}s)  "
            f"{summary['matched']}/{summary['total_events']} matched ({summary['match_rate']:.0%})  {status}"
        )

        if verbose or round_filter is not None:
            print(f"  Matchups: " + ", ".join(
                f"C{n} {m}" for n, m in sorted(report["matchups"].items())
            ))
            print_slot_transcript(speech)
            if refinements:
                print_refined_bundles(refinements, refine_chunk_sec)
            for result in results:
                event = result.expected
                if result.status in ("skipped",):
                    continue
                court = "ALL" if event.venue_wide else f"C{event.court_num}"
                if result.matched:
                    drift = f"{result.drift_seconds:+.0f}s"
                    print(
                        f"  {event.event_type:<20} {court:<4} "
                        f"{seconds_to_hms(result.actual_start)} ({drift})  {result.matched_text.strip()}"
                    )
                else:
                    print(f"  {event.event_type:<20} {court:<4}  MISSED")
            print()

    return round_reports


def court_regex(court_num: int) -> re.Pattern[str]:
    word, digit = COURT_WORDS.get(court_num, (str(court_num), str(court_num)))
    return re.compile(rf"\bcourt\s*(?:{word}|{digit})\b", re.I)


def score_segment(event: ExpectedEvent, segment: TranscriptSegment) -> float:
    try:
        from rapidfuzz import fuzz
    except ImportError:
        print(
            "Error: rapidfuzz is required. Install with: pip install -r requirements-transcribe.txt",
            file=sys.stderr,
        )
        sys.exit(1)

    text = segment.text.lower()
    cue_patterns = EVENT_CUES.get(event.event_type, [])
    cue_hits = sum(1 for pattern in cue_patterns if re.search(pattern, text, re.I))

    if event.venue_wide:
        if cue_hits == 0:
            return 0.0
        return min(0.5 + 0.15 * cue_hits, 1.0)

    score = 0.0
    if court_regex(event.court_num).search(text):
        score += 0.35

    home_norm = normalize_team(event.home_team)
    away_norm = normalize_team(event.away_team)
    score += 0.25 * (fuzz.partial_ratio(home_norm, text) / 100.0)
    score += 0.25 * (fuzz.partial_ratio(away_norm, text) / 100.0)

    if cue_hits:
        score += min(0.25, 0.1 * cue_hits)

    return min(score, 1.0)


def match_events_to_transcript(
    events: list[ExpectedEvent],
    segments: list[TranscriptSegment],
    tolerance: int,
    min_confidence: float,
) -> list[MatchResult]:
    results: list[MatchResult] = []
    used_segment_indices: set[int] = set()

    for event in events:
        if event.skipped:
            results.append(MatchResult(expected=event, matched=False, status="skipped"))
            continue

        if event.wav_offset_seconds < 0:
            results.append(MatchResult(expected=event, matched=False, status="before_wav_start"))
            continue

        threshold = 0.35 if event.venue_wide else min_confidence
        window_start = event.wav_offset_seconds - tolerance
        window_end = event.wav_offset_seconds + tolerance

        best_idx: int | None = None
        best_score = 0.0
        for idx, segment in enumerate(segments):
            if idx in used_segment_indices:
                continue
            if segment.start < window_start or segment.start > window_end:
                continue
            score = score_segment(event, segment)
            if score > best_score:
                best_score = score
                best_idx = idx

        if best_idx is None or best_score < threshold:
            results.append(
                MatchResult(
                    expected=event,
                    matched=False,
                    confidence=best_score,
                    status="missed",
                )
            )
            continue

        segment = segments[best_idx]
        used_segment_indices.add(best_idx)
        drift = segment.start - event.wav_offset_seconds
        results.append(
            MatchResult(
                expected=event,
                matched=True,
                actual_start=segment.start,
                drift_seconds=drift,
                confidence=best_score,
                matched_text=segment.text.strip(),
                status="matched",
            )
        )

    return results


def infer_wav_start_time(
    events: list[ExpectedEvent],
    segments: list[TranscriptSegment],
    tolerance: int,
    min_confidence: float,
) -> str | None:
    start_events = [
        e for e in events if e.event_type == "court_announcement" and not e.skipped
    ]
    if not start_events or not segments:
        return None

    best_anchor: int | None = None
    best_score = 0.0

    for event in start_events[:12]:
        for segment in segments:
            if segment.start > 3600:
                break
            score = score_segment(event, segment)
            if score >= min_confidence and score > best_score:
                inferred_anchor = event.wall_seconds - int(round(segment.start))
                best_score = score
                best_anchor = inferred_anchor

    if best_anchor is None:
        return None
    return seconds_to_hm(best_anchor)


def get_wav_duration(wav_path: Path) -> float:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(wav_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(result.stdout.strip())


def transcribe_wav(
    wav_path: Path,
    model_name: str,
    cache_path: Path | None,
    force_retranscribe: bool,
) -> list[TranscriptSegment]:
    if cache_path and cache_path.exists() and not force_retranscribe:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        return [TranscriptSegment(**item) for item in data["segments"]]

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print(
            "Error: faster-whisper is required. Install with: pip install -r requirements-transcribe.txt",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Transcribing {wav_path} with model={model_name} ...", file=sys.stderr)
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segments_iter, _info = model.transcribe(str(wav_path), vad_filter=True)

    segments: list[TranscriptSegment] = []
    for segment in segments_iter:
        text = segment.text.strip()
        if text:
            segments.append(
                TranscriptSegment(start=segment.start, end=segment.end, text=text)
            )

    if cache_path:
        cache_path.write_text(
            json.dumps(
                {
                    "wav_path": str(wav_path),
                    "model": model_name,
                    "segments": [asdict(s) for s in segments],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"Cached transcript: {cache_path}", file=sys.stderr)

    return segments


def venue_cues_in_text(text: str) -> list[str]:
    text_lower = text.lower()
    hits: list[str] = []
    for event_type in VENUE_BUNDLE_CUE_TYPES:
        patterns = EVENT_CUES.get(event_type, [])
        if any(re.search(pattern, text_lower, re.I) for pattern in patterns):
            hits.append(event_type)
    return hits


def is_bundled_segment(segment: TranscriptSegment) -> bool:
    hits = venue_cues_in_text(segment.text)
    if len(set(hits)) >= 2:
        return True
    return bool(hits and len(segment.text) > 120)


def get_refinement_model(model_name: str) -> Any:
    if model_name not in _refine_model_cache:
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            print(
                "Error: faster-whisper is required. Install with: pip install -r requirements-transcribe.txt",
                file=sys.stderr,
            )
            sys.exit(1)
        print(f"Loading bundled-cue refinement model={model_name} ...", file=sys.stderr)
        _refine_model_cache[model_name] = WhisperModel(
            model_name, device="cpu", compute_type="int8"
        )
    return _refine_model_cache[model_name]


def load_refinement_cache(path: Path | None) -> dict:
    if path and path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"chunk_sec": None, "refine_model": None, "entries": {}}


def save_refinement_cache(path: Path | None, data: dict) -> None:
    if path:
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def refine_bundled_segment(
    wav_path: Path,
    segment: TranscriptSegment,
    model: Any,
    chunk_sec: int,
    workdir: Path,
) -> list[TranscriptSegment]:
    start = max(0.0, segment.start - 1.0)
    end = max(segment.end, segment.start + 2.0)
    duration = max(end - start, 3.0)

    clip = workdir / f"clip_{int(segment.start * 10)}.wav"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            str(start),
            "-t",
            str(duration),
            "-i",
            str(wav_path),
            "-ac",
            "1",
            "-ar",
            "16000",
            str(clip),
        ],
        capture_output=True,
        check=True,
    )

    refined: list[TranscriptSegment] = []
    sub_starts = list(range(0, int(duration), chunk_sec)) if duration > chunk_sec else [0]

    for sub_off in sub_starts:
        sub_dur = min(float(chunk_sec), duration - sub_off)
        if sub_dur < 1.5:
            continue
        sub_clip = workdir / f"sub_{int(segment.start * 10)}_{sub_off}.wav"
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-ss",
                str(sub_off),
                "-t",
                str(sub_dur),
                "-i",
                str(clip),
                "-ac",
                "1",
                "-ar",
                "16000",
                str(sub_clip),
            ],
            capture_output=True,
            check=True,
        )
        segments_iter, _info = model.transcribe(str(sub_clip), vad_filter=True)
        for piece in segments_iter:
            text = piece.text.strip()
            if not text:
                continue
            abs_start = start + sub_off + piece.start
            abs_end = start + sub_off + piece.end
            refined.append(TranscriptSegment(start=abs_start, end=abs_end, text=text))

    return refined


def augment_slot_segments(
    segments: list[TranscriptSegment],
    slot_anchor: float,
    wav_path: Path,
    refine_model: str,
    chunk_sec: int,
    refine_cache: dict | None,
    pre_seconds: int = 30,
    post_seconds: int = 26 * 60,
) -> tuple[list[TranscriptSegment], list[dict]]:
    window_start = slot_anchor - pre_seconds
    window_end = slot_anchor + post_seconds

    bundled_indices = [
        idx
        for idx, segment in enumerate(segments)
        if window_start <= segment.start <= window_end and is_bundled_segment(segment)
    ]
    if not bundled_indices:
        return segments, []

    model = get_refinement_model(refine_model)
    cache_entries = refine_cache.setdefault("entries", {}) if refine_cache is not None else {}
    refinements: list[dict] = []

    with tempfile.TemporaryDirectory(prefix="overhead_refine_") as tmp:
        workdir = Path(tmp)
        for idx in bundled_indices:
            segment = segments[idx]
            cache_key = f"{segment.start:.1f}"
            if refine_cache is not None and cache_key in cache_entries:
                refined = [
                    TranscriptSegment(**item) for item in cache_entries[cache_key]["segments"]
                ]
            else:
                refined = refine_bundled_segment(
                    wav_path, segment, model, chunk_sec, workdir
                )
                if refine_cache is not None:
                    cache_entries[cache_key] = {
                        "original_text": segment.text,
                        "segments": [asdict(item) for item in refined],
                    }

            refinements.append(
                {
                    "original_start": segment.start,
                    "original_text": segment.text.strip(),
                    "cues": venue_cues_in_text(segment.text),
                    "refined": refined,
                }
            )

    if refine_cache is not None:
        refine_cache["chunk_sec"] = chunk_sec
        refine_cache["refine_model"] = refine_model

    bundled_set = set(bundled_indices)
    merged = [segment for idx, segment in enumerate(segments) if idx not in bundled_set]
    for item in refinements:
        merged.extend(item["refined"])
    merged.sort(key=lambda segment: segment.start)
    return merged, refinements


def print_refined_bundles(refinements: list[dict], chunk_sec: int) -> None:
    if not refinements:
        return
    print(f"  --- refined bundled cues ({chunk_sec}s sub-chunks) ---")
    for item in refinements:
        cue_label = ", ".join(item["cues"]) if item["cues"] else "?"
        print(
            f"  {seconds_to_hms(item['original_start'])}  "
            f"(was bundled: {cue_label})"
        )
        print(f"    ORIG: {item['original_text'][:100]}{'…' if len(item['original_text']) > 100 else ''}")
        for segment in item["refined"]:
            cues = venue_cues_in_text(segment.text)
            cue_str = f" [{', '.join(cues)}]" if cues else ""
            print(f"    {seconds_to_hms(segment.start)}{cue_str}  {segment.text.strip()}")
    print()


def find_orphan_segments(
    segments: list[TranscriptSegment],
    results: list[MatchResult],
) -> list[dict]:
    matched_texts = {r.matched_text.lower() for r in results if r.matched and r.matched_text}
    orphans: list[dict] = []
    for segment in segments:
        text_lower = segment.text.lower()
        if text_lower in matched_texts:
            continue
        if not re.search(
            r"\b(court\s*(?:one|two|three|four|[1-4])|halfway|here we go|seconds remaining|countdown)\b",
            text_lower,
        ):
            continue
        orphans.append(
            {
                "start": segment.start,
                "start_hms": seconds_to_hms(segment.start),
                "text": segment.text.strip(),
            }
        )
    return orphans


def build_summary(results: list[MatchResult], courts: list[int]) -> dict:
    active = [r for r in results if r.status not in ("skipped", "before_wav_start")]
    matched = [r for r in active if r.matched]
    missed = [r for r in active if not r.matched]
    drifts = [abs(r.drift_seconds) for r in matched if r.drift_seconds is not None]

    per_court: dict[str, dict] = {}
    for court_num in courts:
        court_results = [
            r for r in active if not r.expected.venue_wide and r.expected.court_num == court_num
        ]
        court_matched = [r for r in court_results if r.matched]
        per_court[str(court_num)] = {
            "total": len(court_results),
            "matched": len(court_matched),
            "missed": len(court_results) - len(court_matched),
        }

    venue_results = [r for r in active if r.expected.venue_wide]
    venue_matched = [r for r in venue_results if r.matched]

    match_rate = (len(matched) / len(active)) if active else 0.0
    return {
        "total_events": len(active),
        "matched": len(matched),
        "missed": len(missed),
        "skipped": len([r for r in results if r.status == "skipped"]),
        "before_wav_start": len([r for r in results if r.status == "before_wav_start"]),
        "match_rate": round(match_rate, 3),
        "max_drift_seconds": round(max(drifts), 1) if drifts else None,
        "median_drift_seconds": round(statistics.median(drifts), 1) if drifts else None,
        "venue_wide": {
            "total": len(venue_results),
            "matched": len(venue_matched),
            "missed": len(venue_results) - len(venue_matched),
        },
        "per_court": per_court,
        "missed_events": [
            {
                "wall_time": r.expected.wall_time,
                "court": r.expected.court,
                "event_type": r.expected.event_type,
                "label": r.expected.label,
                "home_team": r.expected.home_team,
                "away_team": r.expected.away_team,
                "round": r.expected.round,
                "confidence": round(r.confidence, 3),
            }
            for r in missed
        ],
    }


def print_timeline(events: list[ExpectedEvent], wav_start_time: str) -> None:
    print(f"Expected announcement timeline (wav anchor: {wav_start_time}, throwdown_25min template)")
    print(f"{'WALL':<8} {'WAV':<10} {'COURT':<8} {'TYPE':<20} {'DETAIL'}")
    print("-" * 90)
    for event in events:
        if event.skipped:
            marker = f" [skipped: {event.skip_reason}]"
        elif event.wav_offset_seconds < 0:
            marker = " [before wav start]"
        else:
            marker = ""
        court = "ALL" if event.venue_wide else str(event.court_num)
        detail = event.label if event.venue_wide else f"{event.home_team} vs {event.away_team}"
        print(
            f"{event.wall_time:<8} "
            f"{seconds_to_hms(event.wav_offset_seconds):<10} "
            f"{court:<8} "
            f"{event.event_type:<20} "
            f"{detail}{marker}"
        )


def print_results_table(results: list[MatchResult]) -> None:
    print()
    print(f"{'EXPECTED':<22} {'WAV':<10} {'DRIFT':<8} {'CONF':<6} {'STATUS':<10} MATCH")
    print("-" * 110)
    for result in results:
        event = result.expected
        court = "ALL" if event.venue_wide else f"C{event.court_num}"
        label = f"{event.wall_time} {court} {event.event_type[:8]}"
        if result.status in ("skipped", "before_wav_start"):
            print(f"{label:<22} {'—':<10} {'—':<8} {'—':<6} {result.status:<10}")
            continue
        wav = seconds_to_hms(result.actual_start) if result.actual_start is not None else "—"
        drift = f"{result.drift_seconds:+.0f}s" if result.drift_seconds is not None else "—"
        conf = f"{result.confidence:.2f}" if result.confidence else "—"
        snippet = result.matched_text[:60] + ("…" if len(result.matched_text) > 60 else "")
        print(f"{label:<22} {wav:<10} {drift:<8} {conf:<6} {result.status:<10} {snippet}")


def write_report(report: VerificationReport, output_path: Path) -> None:
    output_path.write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")
    print(f"\nReport written: {output_path}", file=sys.stderr)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify overhead .wav announcements against schedule JSONL files."
    )
    parser.add_argument("--wav", type=Path, required=True, help="Path to venue-wide overhead .wav")
    parser.add_argument(
        "--schedule-dir",
        type=Path,
        required=True,
        help="Directory containing {date}_courtN.jsonl files",
    )
    parser.add_argument("--date", required=True, help="Schedule date (YYYY-MM-DD)")
    parser.add_argument(
        "--courts",
        default="2,3,4",
        help="Comma-separated court numbers to include (default: 2,3,4)",
    )
    parser.add_argument(
        "--wav-start-time",
        help="Wall-clock time when .wav offset 0:00 begins (HH:MM). Omit to auto-infer.",
    )
    parser.add_argument(
        "--tolerance",
        type=int,
        default=90,
        help="Search window +/- seconds around expected wav offset (default: 90)",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.55,
        help="Minimum match score for court announcements (default: 0.55)",
    )
    parser.add_argument(
        "--match-rate-threshold",
        type=float,
        default=0.80,
        help="Required match rate for exit code 0 (default: 0.80)",
    )
    parser.add_argument(
        "--max-drift",
        type=int,
        default=120,
        help="Maximum allowed abs drift in seconds for exit code 0 (default: 120)",
    )
    parser.add_argument(
        "--skip-ranges",
        action="append",
        default=[],
        help="Wall-clock ranges to skip, e.g. 12:05-13:30 (repeatable)",
    )
    parser.add_argument(
        "--skip-before",
        help="Skip events before this wall-clock time (HH:MM), e.g. afternoon bracket only",
    )
    parser.add_argument(
        "--model",
        default="small",
        help="faster-whisper model size (default: small)",
    )
    parser.add_argument(
        "--transcript-cache",
        type=Path,
        help="Path to transcript JSON cache (default: {wav}.transcript.json)",
    )
    parser.add_argument(
        "--retranscribe",
        action="store_true",
        help="Ignore cached transcript and re-run whisper",
    )
    parser.add_argument(
        "--output-report",
        type=Path,
        help="Write JSON report to this path (default: beside .wav)",
    )
    parser.add_argument(
        "--timeline-only",
        action="store_true",
        help="Print expected timeline only; do not transcribe",
    )
    parser.add_argument(
        "--by-round",
        action="store_true",
        help="Verify each schedule round independently with per-slot audio anchoring",
    )
    parser.add_argument(
        "--round",
        type=int,
        metavar="N",
        help="With --by-round, show full detail for round N only (1-based)",
    )
    parser.add_argument(
        "--no-refine-bundled",
        action="store_true",
        help="With --by-round, skip 8s-chunk re-transcription of bundled Whisper segments",
    )
    parser.add_argument(
        "--refine-model",
        default="base",
        help="faster-whisper model for bundled-cue refinement (default: base)",
    )
    parser.add_argument(
        "--refine-chunk-sec",
        type=int,
        default=8,
        help="Sub-chunk size in seconds for bundled-cue refinement (default: 8)",
    )
    parser.add_argument(
        "--refine-cache",
        type=Path,
        help="Cache refined bundled segments (default: {transcript}.refined.json)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.timeline_only and not args.wav.exists():
        print(f"Error: WAV file not found: {args.wav}", file=sys.stderr)
        return 1

    courts = [int(c.strip()) for c in args.courts.split(",") if c.strip()]
    skip_ranges = parse_skip_ranges(args.skip_ranges)

    try:
        games = load_games(args.schedule_dir, args.date, courts)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    wav_start_time = args.wav_start_time
    if args.timeline_only and not wav_start_time:
        print("Error: --timeline-only requires --wav-start-time", file=sys.stderr)
        return 1

    if not wav_start_time:
        wav_start_time = "09:00"
        print(
            f"Warning: --wav-start-time not set; using {wav_start_time} for initial pass "
            "(will auto-infer if possible)",
            file=sys.stderr,
        )

    events = build_expected_events(
        games,
        wav_start_time=wav_start_time,
        skip_ranges=skip_ranges,
        skip_before=args.skip_before,
    )

    if args.timeline_only:
        print_timeline(events, wav_start_time)
        return 0

    cache_path = args.transcript_cache or args.wav.with_suffix(args.wav.suffix + ".transcript.json")

    if args.by_round:
        if not cache_path.exists() and not args.wav.exists():
            print(f"Error: WAV file not found: {args.wav}", file=sys.stderr)
            return 1
        segments = transcribe_wav(args.wav, args.model, cache_path, args.retranscribe)
        if not wav_start_time:
            print("Error: --by-round requires --wav-start-time", file=sys.stderr)
            return 1
        print(
            f"Per-round verification (tolerance ±{args.tolerance}s, full phrases"
            f"{'' if args.no_refine_bundled else ', bundled-cue refinement'})"
            f"\n{'RND':<4} {'SCHEDULE':<12} {'WALL':<6} {'ANCHOR':<10} {'DRIFT':<8} {'MATCHED':<12} {'STATUS'}"
        )
        print("-" * 72)
        refine_cache_path = args.refine_cache or cache_path.with_name(
            f"{cache_path.stem}.refined.json"
        )
        refine_cache = load_refinement_cache(refine_cache_path)
        reports = verify_by_round(
            games,
            segments,
            args.wav,
            wav_start_time,
            args.tolerance,
            args.min_confidence,
            skip_ranges,
            args.skip_before,
            refine_bundled=not args.no_refine_bundled,
            refine_model=args.refine_model,
            refine_chunk_sec=args.refine_chunk_sec,
            refine_cache=refine_cache if not args.no_refine_bundled else None,
            round_filter=args.round,
            verbose=True,
        )
        if not args.no_refine_bundled:
            save_refinement_cache(refine_cache_path, refine_cache)
            print(f"Refinement cache: {refine_cache_path}", file=sys.stderr)
        if not reports:
            print("No rounds matched filter.", file=sys.stderr)
            return 1
        output_report = args.output_report or args.wav.with_name(
            f"{args.wav.stem}_overhead_by_round_report.json"
        )
        phrases_path = output_report.with_name(f"{args.wav.stem}_overhead_by_round_phrases.txt")
        write_by_round_report(
            reports,
            output_report,
            args.wav,
            wav_start_time,
            args.tolerance,
            refine_bundled=not args.no_refine_bundled,
        )
        write_by_round_phrases_file(reports, phrases_path)
        print(f"Phrases file: {phrases_path}", file=sys.stderr)
        passed = sum(1 for r in reports if r["summary"]["match_rate"] >= args.match_rate_threshold)
        print("-" * 72)
        print(f"Rounds passed: {passed}/{len(reports)}")
        return 0 if passed == len(reports) else 1

    try:
        wav_duration = get_wav_duration(args.wav)
    except (subprocess.CalledProcessError, ValueError) as exc:
        print(f"Error reading wav duration via ffprobe: {exc}", file=sys.stderr)
        return 1

    last_event = max(
        (e for e in events if not e.skipped and e.wav_offset_seconds >= 0),
        key=lambda e: e.wav_offset_seconds,
        default=None,
    )
    if last_event and last_event.wav_offset_seconds > wav_duration + args.tolerance:
        print(
            f"Warning: WAV duration ({seconds_to_hms(wav_duration)}) may not cover last "
            f"scheduled event at wav offset {seconds_to_hms(last_event.wav_offset_seconds)} "
            f"({last_event.wall_time} {last_event.label or last_event.court})",
            file=sys.stderr,
        )

    cache_path = args.transcript_cache or args.wav.with_suffix(args.wav.suffix + ".transcript.json")
    segments = transcribe_wav(args.wav, args.model, cache_path, args.retranscribe)

    inferred_start: str | None = None
    if not args.wav_start_time:
        inferred_start = infer_wav_start_time(
            events, segments, args.tolerance, args.min_confidence
        )
        if inferred_start:
            print(f"Inferred --wav-start-time: {inferred_start}", file=sys.stderr)
            wav_start_time = inferred_start
            events = build_expected_events(
                games,
                wav_start_time=wav_start_time,
                skip_ranges=skip_ranges,
                skip_before=args.skip_before,
            )
        else:
            print(
                "Warning: Could not infer wav start time; results use default anchor",
                file=sys.stderr,
            )

    results = match_events_to_transcript(
        events, segments, args.tolerance, args.min_confidence
    )
    summary = build_summary(results, courts)
    orphans = find_orphan_segments(segments, results)

    print_results_table(results)
    print()
    print("Summary")
    print(f"  Match rate: {summary['match_rate']:.1%} ({summary['matched']}/{summary['total_events']})")
    if summary["max_drift_seconds"] is not None:
        print(f"  Max drift: {summary['max_drift_seconds']}s")
        print(f"  Median drift: {summary['median_drift_seconds']}s")
    print(f"  Skipped: {summary['skipped']}, before wav start: {summary['before_wav_start']}")
    vw = summary["venue_wide"]
    print(f"  Venue-wide: {vw['matched']}/{vw['total']} matched")
    for court_num, stats in summary["per_court"].items():
        print(f"  Court {court_num} announcements: {stats['matched']}/{stats['total']} matched")

    if summary["missed_events"]:
        print(f"\nMissed announcements ({len(summary['missed_events'])}):")
        for item in summary["missed_events"][:20]:
            who = item["home_team"] or item["label"]
            print(
                f"  {item['wall_time']} {item['court']} {item['event_type']}: {who}"
            )
        if len(summary["missed_events"]) > 20:
            print(f"  ... and {len(summary['missed_events']) - 20} more")

    if orphans:
        print(f"\nOrphan announcements ({len(orphans)}) — heard but not matched to schedule:")
        for item in orphans[:15]:
            print(f"  {item['start_hms']}: {item['text'][:80]}")
        if len(orphans) > 15:
            print(f"  ... and {len(orphans) - 15} more")

    report = VerificationReport(
        wav_path=str(args.wav),
        schedule_date=args.date,
        wav_start_time=wav_start_time,
        inferred_wav_start_time=inferred_start,
        wav_duration_seconds=wav_duration,
        tolerance_seconds=args.tolerance,
        skip_ranges=[(seconds_to_hm(a), seconds_to_hm(b)) for a, b in skip_ranges],
        events=[
            {
                "wall_time": r.expected.wall_time,
                "wav_offset_seconds": r.expected.wav_offset_seconds,
                "court": r.expected.court,
                "event_type": r.expected.event_type,
                "label": r.expected.label,
                "venue_wide": r.expected.venue_wide,
                "home_team": r.expected.home_team,
                "away_team": r.expected.away_team,
                "round": r.expected.round,
                "status": r.status,
                "actual_start": r.actual_start,
                "drift_seconds": r.drift_seconds,
                "confidence": round(r.confidence, 3),
                "matched_text": r.matched_text,
            }
            for r in results
        ],
        summary=summary,
        orphan_segments=orphans,
    )

    output_report = args.output_report or args.wav.with_name(
        args.wav.stem + "_overhead_verification_report.json"
    )
    write_report(report, output_report)

    passed = True
    if summary["total_events"] == 0:
        print("\nVerification failed: no events to check.", file=sys.stderr)
        passed = False
    elif summary["match_rate"] < args.match_rate_threshold:
        print(
            f"\nVerification failed: match rate {summary['match_rate']:.1%} "
            f"< threshold {args.match_rate_threshold:.1%}",
            file=sys.stderr,
        )
        passed = False
    elif summary["max_drift_seconds"] is not None and summary["max_drift_seconds"] > args.max_drift:
        print(
            f"\nVerification failed: max drift {summary['max_drift_seconds']}s "
            f"> limit {args.max_drift}s",
            file=sys.stderr,
        )
        passed = False

    if passed:
        print("\nVerification passed.", file=sys.stderr)
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
