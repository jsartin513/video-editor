# June 2026 Tournament Runbook

Processing guide for **Throw Down 5th Edition** (June 20–21). Court 1 streams both days — only courts **2–4** on Saturday and **2–3** on Sunday need GoPro post-processing.

## One-time setup

```bash
cd src/bash && ./install.sh && ./install.sh --verify-only

cd ../..   # repo root
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

./src/bash/setup_tournament.sh src/output/June2026Tournament
./src/bash/validate_tournament_setup.sh --dry-run
```

## Folder layout

```
src/output/June2026Tournament/
├── schedule/
│   ├── master_schedule.xlsx
│   └── generated/              # {date}_court{N}.jsonl
├── 2026-06-20/
│   ├── court2/                 # raw GX*.MP4 + merged_videos/ + split_videos/
│   ├── court3/
│   └── court4/
├── 2026-06-21/
│   ├── court2/
│   └── court3/
└── deliverables/               # flat upload folder (symlinks)
```

Paths must **not contain spaces**.

## Schedule → JSONL

Drop the Excel file at `schedule/master_schedule.xlsx`, then:

```bash
.venv/bin/python src/scripts/excel_schedule_to_jsonl.py \
  src/output/June2026Tournament/schedule/master_schedule.xlsx \
  --output-dir src/output/June2026Tournament/schedule/generated \
  --date 2026-06-20 --minutes 25 --skip-courts 1
```

This parses Throw Down **team sheets** (`PLAYING : Court N (HOME) vs. ...`) and skips Court 1 (stream).

**Current schedule coverage:** Saturday round robin only (30 games, courts 2–4). Re-run the converter when bracket and Sunday matchups are added to the spreadsheet.

## Overhead audio verification

The venue-wide overhead `.wav` (PA announcements for matchups, no blocking, time calls, etc.) can be checked against the generated JSONL schedule before or after GoPro splitting.

The schedule JSONL only defines **`start_time`** and **`minutes`** per game (25-minute slots, back-to-back). Verification expects announcements at each **game start** and **game end** derived from those fields — not countdown warnings unless you opt in with `--warning-minutes`.

One-time extra deps:

```bash
pip install -r requirements-transcribe.txt
```

**Step 1 — preview expected announcement times** (no transcription):

```bash
./src/bash/verify_overhead_schedule.sh \
  --wav /path/to/overhead_2026-06-20.wav \
  --schedule-dir src/output/June2026Tournament/schedule/generated \
  --date 2026-06-20 \
  --courts 2,3,4 \
  --wav-start-time 09:00 \
  --timeline-only
```

Scrub the `.wav` at offset `0:00` — you should hear the first round's start announcements. Adjust `--wav-start-time` if the anchor is wrong.

**Step 2 — full verification** (transcribes with faster-whisper; caches transcript beside the `.wav`):

```bash
./src/bash/verify_overhead_schedule.sh \
  --wav /path/to/overhead_2026-06-20.wav \
  --schedule-dir src/output/June2026Tournament/schedule/generated \
  --date 2026-06-20 \
  --courts 2,3,4 \
  --wav-start-time 09:00 \
  --tolerance 90
```

**Per-round check** (recommended — anchors each round independently, re-transcribes bundled Whisper segments with 8s sub-chunks):

```bash
./src/bash/verify_overhead_schedule.sh \
  --wav "/Users/jessicasartin/Downloads/BDL Throwdown 5 Full Timeline.wav" \
  --schedule-dir src/output/June2026Tournament/schedule/generated \
  --date 2026-06-20 \
  --courts 2,3,4 \
  --wav-start-time 09:00 \
  --by-round

# Detail for one round:
  --by-round --round 3

# Skip slow refinement (uses full-file transcript only):
  --by-round --no-refine-bundled
```

Refined bundled segments are cached beside the transcript as `{wav}.transcript.refined.json`.

**Output files** (written beside the `.wav`):

| File | Contents |
|------|----------|
| `{wav_stem}_overhead_by_round_report.json` | Full structured report: match results, per-round speech with wav timestamp + slot offset |
| `{wav_stem}_overhead_by_round_phrases.txt` | Human-readable phrase list (WAV time, offset from round anchor, wall time, text) |
| `{wav_stem}.transcript.json` | Cached full-file Whisper transcript |
| `{wav_stem}.transcript.refined.json` | Cached bundled-segment refinements |

Each speech item in the JSON report includes:

- `wav_timestamp` — position in the `.wav` (e.g. `04:00:48`)
- `offset` / `offset_seconds` — seconds from that round's inferred anchor (e.g. `+4:00`)
- `wall_time` — tournament wall clock (from `--wav-start-time`)
- `text` — exact Whisper phrase

The script writes `{wav_stem}_overhead_verification_report.json` next to the `.wav`. Exit code 0 when match rate ≥ 80% and max drift ≤ 120s.

**Lunch break:** skip the gap when PA was silent:

```bash
  --skip-ranges 12:05-13:30
```

**Afternoon bracket only:**

```bash
  --skip-before 13:30 --wav-start-time 13:30
```

**Manual spot-check:** After running the script, listen to one early, one mid-morning, and one post-lunch game per court. Confirm team names at game start and the end-of-game call land within ~1 minute of JSONL times.

## Field day

### Hardware

| Label   | Court | Day       |
|---------|-------|-----------|
| Sat-C2  | 2     | Saturday  |
| Sat-C3  | 3     | Saturday  |
| Sat-C4  | 4     | Saturday  |
| Sun-C2  | 2     | Sunday    |
| Sun-C3  | 3     | Sunday    |

Keep each SD card with its camera all day. Log every stop/start in `recording_notes.txt` inside each court folder:

```
09:00 — Round robin recording started
12:05 — Stopped for lunch
13:30 — Bracket recording started
14:15 — Battery swap (~2 min gap)
```

The first `HH:MM —` line is used as the recording start when camera metadata is wrong.

### Ideal recording pattern

- Round robin: power on once per court  
- Lunch: power off  
- Bracket: power on again  

Battery swaps and angle adjustments are fine — log them in `recording_notes.txt`.

## After each day

### 1. Import SD cards

```bash
./src/bash/import_tournament_sd.sh \
  --dest src/output/June2026Tournament/2026-06-20/court2 \
  --card Sat-C2
```

Repeat for each card. Use `--dry-run` to preview. Add `--source /Volumes/CARD_NAME` if auto-detect picks the wrong volume.

### 2. Merge + split

```bash
# Saturday
./src/bash/process_tournament_day.sh \
  src/output/June2026Tournament/2026-06-20 \
  --courts 2,3,4 --dry-run

./src/bash/process_tournament_day.sh \
  src/output/June2026Tournament/2026-06-20 \
  --courts 2,3,4

# Sunday
./src/bash/process_tournament_day.sh \
  src/output/June2026Tournament/2026-06-21 \
  --courts 2,3
```

Per court this runs `combine_gopro_videos.sh` (one `PROCESSED*.MP4` per power-on session) then `split_multi_source_videos.sh`.

### 3. Spot-check and fix timing

Output files land in `courtN/split_videos/` with names like:

```
Round Robin Round 1: Court 2: Fresh Prince vs Family Matters.mp4
```

Watch 2–3 games per court. If offsets are wrong, see **Timing modes** below and re-run split for that court.

### 4. Collect for upload

```bash
./src/bash/collect_deliverables.sh src/output/June2026Tournament
# or --copy to duplicate files instead of symlinking
```

## Timing modes

The splitter reads `start_time` from each court's JSONL:

| Format   | Example   | When to use |
|----------|-----------|-------------|
| `HH:MM`  | `09:00`   | Camera clock is correct, or first line of `recording_notes.txt` has the real start time |
| `HH:MM:SS` | `00:15:30` | Camera clock is wrong — offset from merged video start |

### Lunch break (important)

Wall-clock times (`09:00`, `14:00`, …) assume a **continuous** timeline from recording start. If cameras were **off during lunch**, afternoon games will not align.

Options:

1. **Process morning and afternoon separately** — import bracket footage into a subfolder or re-import only afternoon clips, with a bracket-only JSONL using offset times.  
2. **Use offset mode** for afternoon games — set `start_time` as `HH:MM:SS` from the start of the afternoon `PROCESSED` file.  
3. **Split sessions manually** — run merge/split per recording session instead of the full day at once.

## Scripts reference

| Script | Purpose |
|--------|---------|
| `setup_tournament.sh` | Create folder tree, check deps |
| `import_tournament_sd.sh` | SD card → court folder |
| `process_tournament_day.sh` | Merge + split all courts for one day |
| `collect_deliverables.sh` | Symlink/copy all matchups to `deliverables/` |
| `validate_tournament_setup.sh` | Test pipeline on sample Week2 footage |
| `verify_overhead_schedule.sh` | Verify overhead .wav vs schedule JSONL |
| `excel_schedule_to_jsonl.py` | Excel → per-court `games.jsonl` |

Lower-level scripts (called automatically): `combine_gopro_videos.sh`, `split_multi_source_videos.sh`.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| No games split / all skipped | Check `recording_notes.txt` start time or switch JSONL to `HH:MM:SS` offsets |
| Game spans multiple videos | Game crosses a battery-swap gap — shorten `minutes` or split sessions |
| Wrong team names in filename | Re-run Excel converter; team names come from sheet names |
| Duplicate deliverable names | `collect_deliverables.sh` prefixes with court/date when names collide |
| `find` misses symlinked GX files | Import with `cp`, not symlinks (`import_tournament_sd.sh` copies by default) |

## Pre-tournament checklist

- [ ] `install.sh --verify-only` passes  
- [ ] `validate_tournament_setup.sh --dry-run` passes  
- [ ] Real schedule in `master_schedule.xlsx`; JSONL regenerated  
- [ ] SD cards and cameras labeled  
- [ ] One real court dry-run (import → process → spot-check)  
- [ ] Bracket JSONL ready before Saturday afternoon (re-convert Excel when filled in)  
- [ ] Sunday JSONL ready before Sunday (re-convert Excel when filled in)
