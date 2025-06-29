# GoPro Video Processing Workflow

This workflow automates the process of converting raw GoPro video segments into individual game videos with proper naming and metadata.

## Quick Start

### First Time Setup
```bash
# Install all required dependencies
./install.sh

# Verify installation
./install.sh --verify-only
```

### Running the Workflow
```bash
# Run the complete workflow
./gopro_workflow.sh /path/to/your/gopro/videos

# Or with configuration
./gopro_workflow.sh --config  # Edit configuration first
./gopro_workflow.sh /path/to/your/gopro/videos
```

## Workflow Steps

The automated workflow handles:

1. **Directory Preparation** - Automatically fixes spaces in folder/file names
2. **Game List Creation** - Interactive creation of games JSONL file
3. **Video Combination** - Combines GoPro segments using `combine_gopro_videos.sh`  
4. **Video Splitting** - Splits combined videos into individual games using `split_game_videos.sh`
5. **File Renaming** - Renames videos with tournament/round/court information
6. **Metadata Addition** - Adds tournament, round, court information to video metadata
7. **Post-processing** - Optional cleanup

## Scripts Overview

### Core Workflow
- `install.sh` - Install all required dependencies (run this first)
- `gopro_workflow.sh` - Main workflow script (recommended)
- `combine_gopro_videos.sh` - Combines GoPro video segments
- `split_game_videos.sh` - Splits videos based on game schedule

### Utilities
- `batch_rename_videos.sh` - Standalone batch rename utility (now integrated into main workflow)
- `generate_games_template.sh` - Generate JSONL template for game scheduling
- `gopro_config.conf` - Configuration file for workflow defaults

## Usage Examples

### Complete Workflow
```bash
# Basic usage
./gopro_workflow.sh ~/Videos/Tournament_2025

# With debug output
./gopro_workflow.sh --debug ~/Videos/Tournament_2025
```

### Individual Steps
```bash
# Fix directory names only
./gopro_workflow.sh --fix-names ~/Videos/Tournament_2025

# Generate games template with rounds
./generate_games_template.sh -n 8 -s 09:00 -i 75 --start-round 1 games.jsonl

# Generate with custom round names
./generate_games_template.sh -r 1 --round-name "Match" games.jsonl

# Batch rename with tournament info
./batch_rename_videos.sh -t "Summer_Tournament" -r "Finals" -c "Court_1" ~/Videos/split_videos
```

## Configuration

Edit `gopro_config.conf` to customize:
- Default tournament/court/round names
- Auto-metadata addition
- Auto-file renaming
- File cleanup options
- Video processing settings

## Games JSONL Format

The games schedule uses JSONL format (one JSON object per line):

```json
{"home_team":"Team_A","away_team":"Team_B","start_time":"09:00","minutes":60,"round":"Game 1"}
{"home_team":"Team_C","away_team":"Team_D","start_time":"10:30","minutes":60,"round":"Game 2"}
```

### Fields:
- `home_team` - Home team name
- `away_team` - Away team name  
- `start_time` - Game start time (HH:MM format)
- `minutes` - Game duration in minutes
- `round` - (Optional) Round/game identifier. If not provided, will auto-increment from 1

## Directory Structure

After processing, your directory will look like:
```
your_gopro_videos/
├── GX*.MP4                 # Original GoPro files
├── games.jsonl             # Game schedule
├── merged_videos/          # Combined GoPro segments
│   └── PROCESSED*.MP4
└── split_videos/           # Individual game videos
    ├── Team_A_vs_Team_B.mp4
    └── Team_C_vs_Team_D.mp4
```

## Tips

1. **Installation**: Run `./install.sh` first to install all dependencies
2. **Preparation**: Copy videos from SD card to a folder with no spaces in the name
3. **Timing**: Ensure your games JSONL has accurate start times relative to video start
4. **Naming**: Team names in JSONL will be used for filenames (spaces become underscores)
5. **Metadata**: Enable metadata addition for better video organization
6. **Testing**: Use `--dry-run` with batch rename to preview changes

## Troubleshooting

### Common Issues

1. **"Video start time not found"**
   - GoPro didn't record metadata properly
   - Try using a different video file or manually specify start time

2. **"Invalid JSON"**
   - Check your games.jsonl file for syntax errors
   - Use `jq` to validate: `jq empty games.jsonl`

3. **"Files not found"**
   - Ensure directory paths have no spaces
   - Check that GoPro files follow naming pattern `GX??????.MP4`

4. **"Command not found" (ffmpeg, jq, etc.)**
   - Run `./install.sh` to install all required dependencies
   - Or run `./install.sh --verify-only` to check what's missing

### Getting Help

Run any script with `--help` for detailed usage information:
```bash
./install.sh --help
./gopro_workflow.sh --help
./batch_rename_videos.sh --help
./generate_games_template.sh --help
```

## Dependencies

The workflow requires these tools (installed automatically by `install.sh`):
- **ffmpeg** - Video processing and conversion
- **ffprobe** - Video metadata extraction  
- **jq** - JSON parsing and validation
- **mediainfo** - Detailed video information (optional)

### Manual Installation
If you prefer to install manually:

**macOS (Homebrew):**
```bash
brew install ffmpeg jq mediainfo
```

**Linux (Debian/Ubuntu):**
```bash
sudo apt update
sudo apt install ffmpeg jq mediainfo
```

**Linux (Red Hat/CentOS/Fedora):**
```bash
sudo dnf install ffmpeg jq mediainfo
# or: sudo yum install ffmpeg jq mediainfo
```
