---
name: merge-event-videos
description: >-
  Merges all videos in a folder (GoPro-aware order), names outputs with event and
  date, defaults to an untrimmed merged file, then trims to timestamps as a
  follow-up. Use when the user wants to concat a folder of clips, merge event or
  gym footage, produce untrimmed then trimmed exports, or name outputs by event
  and date.
---

# Merge event videos (folder → untrimmed → trim)

## When to apply

Use this workflow whenever the user supplies a **directory of video files** (especially GoPro `GX`/`GP`/`GOPR` `.MP4`) and wants a **merged file**, a **clear naming scheme**, and a **two-phase** process: merge first, trim second.

## Naming convention (required)

Slugs for filenames: ASCII, replace spaces with underscores, strip unsafe characters (`/ \ : * ? " < > |`).

| Stage | Pattern | Example |
|--------|---------|---------|
| **Merged, not yet trimmed** | `{EventSlug}_{YYYY-MM-DD}_untrimmed.MP4` | `SheThey_League_2026-03-29_untrimmed.MP4` |
| **After trim (deliverable)** | `{EventSlug}_{YYYY-MM-DD}_trimmed.MP4` | `SheThey_League_2026-03-29_trimmed.MP4` |

- If the user prefers a single final name without `_trimmed`, use `{EventSlug}_{YYYY-MM-DD}.MP4` **only** for the trimmed export (and keep `_untrimmed` for the first merge).
- **Event** and **date** must appear in **both** untrimmed and trimmed outputs unless the user explicitly opts out.

Derive **date** from: user-provided date → folder name → filesystem dates on the clips → `YYYY-MM-DD`.

## Phase 1 — Merge (default: untrimmed)

1. **List** `.mp4` / `.MP4` in the folder; exclude zero-byte or obvious junk if noted.
2. **Order** clips:
   - **GoPro**: group by session id (last 4 digits of `GXnnSSSS` / `GPnnSSSS`, or `GOPRSSSS`), sessions sorted numerically; within a session, sort by full basename (`GX010010` before `GX020010`). For project code, prefer `python src/scripts/simple_concat_gopro_video.py list <dir>` then `concat` if the repo is available.
   - **Non-GoPro**: sort by name or modification time as the user specifies; default = lexicographic basename.
3. **Compatibility**: Stream-copy concat (`-c copy`) requires **same codec, resolution, and timebase** across segments. If sessions differ (e.g. 1080p vs 4K), **do not** produce one concat with copy; split into separate merges or re-encode (state this explicitly).
4. **Write** the merged file to the **same folder** (or path the user gave) using the **`_untrimmed`** pattern above.
5. **ffmpeg concat** (when not using the project script):

```bash
# concat_list.txt: one line per file, absolute paths, safe 0
# file '/path/to/clip1.MP4'
ffmpeg -y -f concat -safe 0 -i concat_list.txt -c copy "/path/to/Event_YYYY-MM-DD_untrimmed.MP4"
```

6. Tell the user the untrimmed file is **full length** and ready for **trim decisions**.

## Phase 2 — Trim (next step)

Run only after the user provides **trim rules** or **absolute/relative timestamps**.

**Seconds from start/end** (stream copy, keyframe-aligned):

```bash
ffmpeg -y -ss START_SEC -i "…_untrimmed.MP4" -t DURATION_SEC -c copy "…_trimmed.MP4"
# or --skip-start / --skip-end via project helper:
# python src/scripts/simple_concat_gopro_video.py trim input.mp4 output.mp4 --skip-start SEC --skip-end SEC
```

**Time-of-day or wall-clock** (if user gives e.g. `01:15:30`–`02:40:00`): use **re-encode** or `-ss` after `-i` for frame accuracy; note tradeoffs (speed vs precision).

Rename output to **`{EventSlug}_{YYYY-MM-DD}_trimmed.MP4`** (or `{EventSlug}_{YYYY-MM-DD}.MP4` if that is the agreed final name).

## Multi-session / multi-event folders

If the folder mixes **distinct sessions or events** (different GoPro session ids or clear time gaps), produce **separate** concat lists and **separate** `_untrimmed` files, each with its own **event slug** (or `EventPart2`), same date if same day.

## Checklist for the agent

- [ ] Confirm event name and date for slugs.
- [ ] Order clips correctly (GoPro session + chapter rules).
- [ ] Verify concat compatibility or split/re-encode.
- [ ] Output **`*_untrimmed.MP4`** first.
- [ ] Trim only when timestamps are known; output **`*_trimmed.MP4`** or final dated name.
- [ ] Warn about disk space for large merges and long `ffmpeg` runs.

## Optional reference

If the repository includes `src/scripts/simple_concat_gopro_video.py`, prefer its `list` and `concat` subcommands for ordering and concatenation, and `trim` for edge trims.
