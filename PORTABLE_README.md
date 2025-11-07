# Portable SD Card Video Processing System

This system allows you to use a regular SD card as a "processing hub" that can automatically process GoPro footage from micro SD cards. The result is a completely portable video processing solution that works anywhere!

## 🎯 The Concept

**Two SD Cards, One Workflow:**
- **Regular SD Card**: Acts as the "processing hub" with all scripts and dependencies
- **Micro SD Card**: Contains raw GoPro footage from your camera
- **Processing**: Happens entirely on the regular SD card, creating organized, upload-ready videos

## 🚀 Quick Start

### 1. Set Up Your Processing Hub

```bash
# Auto-detect and set up a processing hub
./portable_helper.sh setup

# Or manually specify an SD card
./portable_setup.sh /Volumes/YOUR_SD_CARD
```

### 2. Use Your Processing Hub

1. Insert **both SD cards** into your computer:
   - Regular SD card (processing hub)
   - Micro SD card (GoPro footage)

2. Run the processing script:
   ```bash
   # Navigate to the processing hub
   cd /Volumes/YOUR_PROCESSING_HUB
   
   # Run the portable processor
   ./processing_scripts/run_portable.sh
   ```

3. Follow the prompts and wait for processing to complete!

### 3. Get Your Videos

- Processed videos will be in `workspace/output/` on the processing hub
- Videos are organized, merged, and ready for upload
- Safely eject both SD cards when done

## 📂 What Gets Installed on the Processing Hub

```
PROCESSING_HUB_SD_CARD/
├── processing_scripts/         # All video processing tools
│   ├── run_portable.sh        # Main launcher script
│   ├── combine_gopro_videos.sh
│   ├── interactive_gopro_processor.sh
│   └── ... (all other scripts)
├── workspace/                 # Working area
│   ├── input/                 # Temporary input files
│   ├── output/               # Final processed videos
│   └── temp/                 # Processing scratch space
├── config/                   # Configuration files
│   └── portable_config.conf
├── logs/                     # Processing logs
└── README_PROCESSING.txt     # Instructions
```

## 🛠️ System Requirements

### On the Host Computer:
- **ffmpeg**: Video processing
- **jq**: JSON file handling
- **mediainfo**: Video metadata (optional but recommended)

### SD Card Requirements:
- **Regular SD Card**: At least 4GB free space (for processing hub)
- **Micro SD Card**: GoPro footage with standard DCIM/100GOPRO structure

### Installation:
```bash
# macOS
brew install ffmpeg jq mediainfo

# Ubuntu/Debian
sudo apt install ffmpeg jq mediainfo

# Or use the main install script
./install.sh
```

## 📖 How It Works

### 1. Dual Card Detection
The system automatically:
- Identifies the processing hub (regular SD card)
- Finds GoPro source cards (micro SD cards with DCIM structure)
- Separates them to avoid confusion

### 2. Smart Processing
- Copies only necessary files to avoid filling up the processing hub
- Processes videos directly on the regular SD card
- Creates organized output ready for upload

### 3. Portable Operation
- All scripts run from the SD card (no installation needed on host)
- Self-contained environment
- Works on any computer with basic dependencies

## 🔧 Advanced Usage

### Manual Processing with Options

```bash
# Run with pre-configured options
./processing_scripts/portable_interactive_processor.sh \
    --source-card /Volumes/GOPRO_CARD \
    --output-dir /Volumes/PROCESSING_HUB/workspace/output/my_event \
    --event-name "league_night" \
    --date-id "sept_17_2025" \
    --court-num "2"
```

### Testing Your Setup

```bash
# Check what cards are available
./portable_helper.sh list-cards

# Test the complete system
./portable_helper.sh test
```

### Force Setup on Existing Card

```bash
# Overwrite existing setup
./portable_setup.sh /Volumes/YOUR_CARD --force
```

## 🎥 Typical Workflow

1. **At the Event:**
   - Record games with GoPro
   - Remove micro SD card from camera

2. **Processing:**
   - Insert both SD cards into computer
   - Run processing script
   - Wait for completion (usually 5-15 minutes)

3. **Upload:**
   - Find processed videos in `workspace/output/`
   - Upload directly to YouTube, etc.
   - Archive or delete files as needed

## 🐛 Troubleshooting

### "No GoPro cards found"
- Make sure micro SD card has DCIM/100GOPRO structure
- Check that GoPro files are .MP4 format
- Ensure card is properly mounted

### "No processing hub found"
- Run `./portable_setup.sh` to create one
- Make sure regular SD card has enough space (4GB+)
- Check write permissions on SD card

### "Missing dependencies"
- Install ffmpeg: `brew install ffmpeg` (macOS) or `sudo apt install ffmpeg` (Linux)
- Install jq: `brew install jq` (macOS) or `sudo apt install jq` (Linux)

### Processing Fails
- Check `logs/` directory on processing hub for details
- Ensure enough space on processing hub
- Try with fewer/smaller video files

## 🔄 Updating Your Processing Hub

To update the scripts on an existing processing hub:

```bash
# Re-run setup (will update scripts)
./portable_setup.sh /Volumes/YOUR_PROCESSING_HUB --force
```

## 📊 Benefits of This Approach

### ✅ Advantages:
- **Truly Portable**: Works on any computer
- **No Installation**: Host computer only needs basic tools
- **Organized Output**: Videos ready for upload
- **Dual Card Safety**: Source footage stays on original card
- **Reusable**: Set up once, use forever

### ⚠️ Considerations:
- **SD Card Speed**: Processing speed depends on SD card performance
- **Space Requirements**: Need enough space on processing hub for merged videos
- **Host Dependencies**: Still requires ffmpeg/jq on host computer

## 🚀 Future Enhancements

Possible improvements:
- **Standalone Binaries**: Include portable ffmpeg for truly standalone operation
- **Multiple Formats**: Support for different camera types
- **Batch Processing**: Handle multiple events at once
- **Cloud Integration**: Direct upload to cloud services
- **GUI Interface**: Graphical interface for easier use

---

## 🎯 Example Complete Workflow

```bash
# 1. Initial setup (one time)
./portable_helper.sh setup

# 2. Each time you process videos:
#    - Insert both SD cards
#    - Navigate to processing hub
cd /Volumes/PROCESSING_HUB

#    - Run processing
./processing_scripts/run_portable.sh

# 3. Find your processed videos:
ls workspace/output/

# 4. Upload and enjoy! 🎉
```

This system gives you a professional video processing workflow that fits in your pocket!
