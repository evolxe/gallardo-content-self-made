# Temporary File Management

## Overview

The system automatically manages temporary video files based on the execution environment:
- **Local Development**: Files saved to `temp_videos/` folder (relative to script)
- **SSH/Server Environment**: Files saved to `/tmp/gallardo-video-pipeline/` for better performance

## Automatic Environment Detection

The system detects the execution environment using these indicators:

1. **SSH Environment Variables**:
   - `SSH_CONNECTION`
   - `SSH_CLIENT`
   - `SSH_TTY`

2. **Working Directory Patterns**:
   - Paths starting with `/home/`, `/var/`, or `/opt/`

If any of these conditions are met, the system uses `/tmp`; otherwise, it uses the local `temp_videos/` folder.

## Directory Structure

### Local Development
```
project-root/
├── sheet.py
├── merge.py
└── temp_videos/          ← Temporary files stored here
    ├── intro.mp4
    ├── boat2.mov
    └── boat2_merged.mp4
```

### SSH/Server Environment
```
/tmp/
└── gallardo-video-pipeline/  ← Temporary files stored here
    ├── intro.mp4
    ├── boat2.mov
    └── boat2_merged.mp4
```

## File Locations

### Downloaded Videos
- **Source**: Nextcloud URLs or external URLs
- **Destination**: `TEMP_DIR` (automatically determined)
- **Function**: `download_from_url()`, `download_nextcloud_public_file()`

### Merged Videos
- **Source**: Output from `merge.py`
- **Destination**: `TEMP_DIR/{filename}_merged.mp4`
- **Function**: Created in main workflow loop

### File Search Order
When resolving local file paths, the system searches in this order:
1. `TEMP_DIR` (where downloads are stored)
2. Current working directory (`os.getcwd()`)
3. Script directory (`SCRIPT_DIR`)
4. `videos/` subdirectory (`SCRIPT_DIR/videos`)

## Benefits of `/tmp` on Servers

1. **Performance**: `/tmp` is often on faster storage (RAM disk or SSD)
2. **Automatic Cleanup**: System can clean `/tmp` on reboot
3. **Isolation**: Separate from application code
4. **Permissions**: Typically has write permissions for all users

## Manual Override

If you need to force a specific temp directory, you can modify the `get_temp_dir()` function in `sheet.py`:

```python
def get_temp_dir() -> str:
    # Force local temp_videos even on server
    temp_dir = os.path.join(SCRIPT_DIR, "temp_videos")
    os.makedirs(temp_dir, exist_ok=True)
    return temp_dir
```

Or set an environment variable and check for it:

```python
def get_temp_dir() -> str:
    # Check for manual override
    manual_temp = os.environ.get("GALLARDO_TEMP_DIR")
    if manual_temp:
        os.makedirs(manual_temp, exist_ok=True)
        return manual_temp
    
    # ... rest of detection logic
```

## Cleanup

### Local Development
- Files in `temp_videos/` persist between runs
- Manually delete when no longer needed
- Can be added to `.gitignore` (already done)

### Server Environment
- Files in `/tmp/gallardo-video-pipeline/` may be cleaned on reboot
- Consider adding cleanup logic for old files
- Files are automatically removed after successful upload to Nextcloud

## Troubleshooting

### Files Not Found in temp_videos/
**Problem**: Local files not being found

**Solution**: 
- Check that files are in the correct `temp_videos/` directory
- Verify `TEMP_DIR` is set correctly (check startup logs)
- Ensure file permissions allow reading

### Files Saved to Wrong Location
**Problem**: Files appearing in project root instead of temp directory

**Solution**:
- Verify `output_file` uses `os.path.join(TEMP_DIR, filename)`
- Check that `TEMP_DIR` is set before creating output files
- Review logs for `[Config] Using temp directory:` message

### Permission Errors on Server
**Problem**: Cannot write to `/tmp/gallardo-video-pipeline/`

**Solution**:
- Check directory permissions: `ls -ld /tmp/gallardo-video-pipeline/`
- Verify user has write access
- May need to create directory manually: `sudo mkdir -p /tmp/gallardo-video-pipeline && sudo chmod 777 /tmp/gallardo-video-pipeline`

## Code Reference

### Key Functions

**`get_temp_dir()`** - Determines temp directory based on environment
- Location: `sheet.py` lines 27-51
- Returns: Absolute path to temp directory

**`download_from_url()`** - Downloads files to TEMP_DIR
- Location: `sheet.py` lines 114-144
- Uses: `TEMP_DIR` constant

**`download_nextcloud_public_file()`** - Downloads Nextcloud files to TEMP_DIR
- Location: `sheet.py` lines 72-111
- Uses: `TEMP_DIR` constant

### Configuration

**`TEMP_DIR`** - Global constant set at module load
- Determined by: `get_temp_dir()`
- Used by: All download and file operations

**`VIDEO_SEARCH_DIRS`** - Search paths for local files
- Includes: `TEMP_DIR` as first search location
- Location: `sheet.py` lines 57-62

---

**Last Updated**: Based on current implementation
**Related Files**: `sheet.py`, `.gitignore`

