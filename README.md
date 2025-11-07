# GoPro Video Editor

A collection of scripts for processing GoPro videos, including automated workflows and portable SD card processing.

## 🆕 New: Portable SD Card Processing System

Turn any regular SD card into a "processing hub" that can handle GoPro footage from micro SD cards! This creates a completely portable video processing solution.

### Quick Start for Portable Processing:
```bash
# Set up a processing hub (one time)
./src/bash/portable_helper.sh setup

# Process videos (each time)
# 1. Insert both SD cards (processing hub + GoPro micro SD)
# 2. Navigate to processing hub: cd /Volumes/YOUR_PROCESSING_HUB
# 3. Run: ./processing_scripts/run_portable.sh
```

See [PORTABLE_README.md](PORTABLE_README.md) for full documentation.

## Traditional Setup
Create a virtualenv using your preferred method. For example, using `virtualenv` and `virtualenvwrapper`:
```bash
mkvirtualenv -p python3.6 myenv
```
Install the requirements:
```bash
pip install -r requirements.txt
```
You'll also need ffmpeg installed on your system. On macOS, you can install it using Homebrew:
```bash
brew install ffmpeg
```

## Usage
See individual scripts in the `src/scripts` directory for usage instructions.