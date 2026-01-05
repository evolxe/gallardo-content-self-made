# Video Processing API - Comprehensive Endpoint

## Overview

The comprehensive video processing endpoint (`POST /api/v1/videos/process`) allows you to apply multiple video transformations in a single request. All operations are executed sequentially to produce a fully processed video output.

## Endpoint

```
POST /api/v1/videos/process
```

## Features

This endpoint combines all video processing capabilities:
- ✅ **Audio Management**: Remove or merge audio tracks
- ✅ **Color Grading**: Apply various color grading presets
- ✅ **Crop & Zoom**: Crop to center 1:1 square aspect ratio
- ✅ **Re-encoding**: Re-encode with custom codec, bitrate, and FPS settings

## Processing Order

Operations are applied in this sequence:
1. **Merge Audio** (if `merge_audio=true` and audio file provided)
2. **Remove Audio** (if `remove_audio=true` - overrides merge_audio)
3. **Color Grading** (if `color_grading=true`)
4. **Crop & Zoom** (if `crop_zoom=true`)
5. **Re-encode** (if `reencode=true` or always at the end to finalize)

## Request Format

**Content-Type:** `multipart/form-data`

### Required Files
- **Video file**: At least one video file (any field name)
- **Audio file**: Required only if `merge_audio=true` (any field name)

### Boolean Parameters (All default to `false`)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `remove_audio` | boolean | `false` | Remove audio track from video |
| `merge_audio` | boolean | `false` | Merge audio file with video (requires audio file upload) |
| `color_grading` | boolean | `false` | Apply color grading to video |
| `crop_zoom` | boolean | `false` | Crop to center 1:1 square aspect ratio |
| `reencode` | boolean | `false` | Re-encode video with specified codec/bitrate/fps |

### Color Grading Parameters (Required if `color_grading=true`)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `color_preset` | string | `"cinematic"` | Color grading preset: `cinematic`, `warm`, `cool`, `vintage`, `vivid`, `bw`, `natural`, `random` |
| `color_brightness` | float | `0.0` | Brightness adjustment (-1.0 to 1.0) |
| `color_contrast` | float | `1.0` | Contrast adjustment (0.0 to 2.0) |
| `color_saturation` | float | `1.0` | Saturation adjustment (0.0 to 2.0) |

### Crop & Zoom Parameters (Required if `crop_zoom=true`)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `crop_output_size` | integer | `1080` | Output square size in pixels (e.g., 1080 = 1080x1080) |

### Re-encode Parameters (Required if `reencode=true`)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `codec` | string | `"libx264"` | Video codec (e.g., `libx264`, `libx265`) |
| `bitrate` | string | `None` | Target bitrate in kbps format (e.g., `"5000k"`) |
| `fps` | float | `None` | Target FPS (uses original if not specified) |

## Response

**Immediate Response:**
```json
{
  "job_id": "f03759ca-2f9f-4c1f-b684-54c17d990e59",
  "status": "pending",
  "message": "Video upload successful. Processing started.",
  "status_url": "/api/v1/jobs/f03759ca-2f9f-4c1f-b684-54c17d990e59",
  "download_url": "/api/v1/videos/f03759ca-2f9f-4c1f-b684-54c17d990e59/download",
  "applied_operations": [
    "merge_audio",
    "color_grading(cinematic)",
    "crop_zoom(1080x1080)",
    "reencode(libx264)"
  ]
}
```

## Workflow

1. **Upload** - Send POST request with video file(s) and processing parameters
2. **Poll** - Check job status using `GET /api/v1/jobs/{job_id}`
3. **Download** - Download processed video using `GET /api/v1/videos/{job_id}/download`

## Usage Examples

### Example 1: Color Grading + Crop to Square

```bash
curl -X POST "http://localhost:8000/api/v1/videos/process" \
  -F "video=@your_video.mp4" \
  -F "color_grading=true" \
  -F "color_preset=cinematic" \
  -F "crop_zoom=true" \
  -F "crop_output_size=1080"
```

### Example 2: Merge Audio + Color Grading + Crop

```bash
curl -X POST "http://localhost:8000/api/v1/videos/process" \
  -F "video=@your_video.mp4" \
  -F "audio=@your_audio.mp3" \
  -F "merge_audio=true" \
  -F "color_grading=true" \
  -F "color_preset=warm" \
  -F "crop_zoom=true" \
  -F "crop_output_size=1080"
```

### Example 3: All Operations Combined

```bash
curl -X POST "http://localhost:8000/api/v1/videos/process" \
  -F "video=@your_video.mp4" \
  -F "audio=@your_audio.mp3" \
  -F "merge_audio=true" \
  -F "color_grading=true" \
  -F "color_preset=random" \
  -F "color_brightness=0.1" \
  -F "color_contrast=1.2" \
  -F "color_saturation=1.1" \
  -F "crop_zoom=true" \
  -F "crop_output_size=1080" \
  -F "reencode=true" \
  -F "codec=libx264" \
  -F "bitrate=5000k" \
  -F "fps=30"
```

### Example 4: Remove Audio + Color Grading

```bash
curl -X POST "http://localhost:8000/api/v1/videos/process" \
  -F "video=@your_video.mp4" \
  -F "remove_audio=true" \
  -F "color_grading=true" \
  -F "color_preset=vintage"
```

### Example 5: Re-encode Only

```bash
curl -X POST "http://localhost:8000/api/v1/videos/process" \
  -F "video=@your_video.mp4" \
  -F "reencode=true" \
  -F "codec=libx264" \
  -F "bitrate=8000k" \
  -F "fps=60"
```

### Example 6: Complete Workflow (Bash)

```bash
# Step 1: Upload and process
RESPONSE=$(curl -X POST "http://localhost:8000/api/v1/videos/process" \
  -F "video=@my_video.mp4" \
  -F "audio=@my_audio.mp3" \
  -F "merge_audio=true" \
  -F "color_grading=true" \
  -F "color_preset=cinematic" \
  -F "crop_zoom=true" \
  -F "crop_output_size=1080" \
  -F "reencode=true" \
  -F "codec=libx264")

# Extract job_id (requires jq)
JOB_ID=$(echo $RESPONSE | jq -r '.job_id')

# Step 2: Poll for status (repeat until status is "completed")
curl "http://localhost:8000/api/v1/jobs/$JOB_ID"

# Step 3: Download when completed
curl "http://localhost:8000/api/v1/videos/$JOB_ID/download" \
  --output processed_video.mp4
```

### Example 7: Complete Workflow (Python)

```python
import requests
import time
import json

# Step 1: Upload and process
url = "http://localhost:8000/api/v1/videos/process"
files = {
    'video': open('my_video.mp4', 'rb'),
    'audio': open('my_audio.mp3', 'rb')
}
data = {
    'merge_audio': True,
    'color_grading': True,
    'color_preset': 'cinematic',
    'crop_zoom': True,
    'crop_output_size': 1080,
    'reencode': True,
    'codec': 'libx264',
    'bitrate': '5000k',
    'fps': 30.0
}

response = requests.post(url, files=files, data=data)
job_id = response.json()['job_id']
files['video'].close()
files['audio'].close()

# Step 2: Poll for status
while True:
    status_response = requests.get(f"http://localhost:8000/api/v1/jobs/{job_id}")
    job = status_response.json()
    print(f"Status: {job['status']}, Progress: {job['progress']}%")
    
    if job['status'] == 'completed':
        break
    elif job['status'] == 'failed':
        print(f"Error: {job.get('error', 'Unknown error')}")
        break
    
    time.sleep(2)  # Wait 2 seconds before next poll

# Step 3: Download when completed
if job['status'] == 'completed':
    download_response = requests.get(f"http://localhost:8000/api/v1/videos/{job_id}/download")
    with open('processed_video.mp4', 'wb') as f:
        f.write(download_response.content)
    print("Video downloaded successfully!")
```

## Color Grading Presets

| Preset | Description |
|--------|-------------|
| `cinematic` | Cool tones, higher contrast, cinematic look |
| `warm` | Warmer tones (orange/red), higher saturation |
| `cool` | Cooler tones (blue/cyan), balanced |
| `vintage` | Sepia-like, reduced saturation, warm tones |
| `vivid` | High contrast and saturation, vibrant colors |
| `bw` | Black and white, enhanced contrast |
| `natural` | Minimal adjustments, natural look |
| `random` | Randomly selects preset and adjustments |

## File Format Support

### Video Formats
- `.mp4`, `.avi`, `.mov`, `.mkv`, `.webm`, `.flv`, `.wmv`

### Audio Formats
- `.mp3`, `.wav`, `.aac`, `.m4a`, `.ogg`, `.flac`, `.wma`

## Important Notes

1. **Field Names**: File field names can be anything (e.g., `video`, `file`, `upload`, `file1`, etc.)
2. **Audio Conflict**: If both `remove_audio=true` and `merge_audio=true` are set, `remove_audio` takes precedence
3. **Random Color Grading**: Set `color_preset=random` for randomly generated color grading
4. **Default Re-encoding**: Even if `reencode=false`, the final video is always encoded with the specified codec (default: `libx264`)
5. **Processing Time**: Processing time depends on video length, resolution, and number of operations
6. **File Cleanup**: Input files are automatically cleaned up after processing

## Error Handling

The API returns detailed error messages if:
- Required files are missing
- Invalid parameter values are provided
- Processing fails during execution

Check the job status endpoint for error details:
```bash
curl "http://localhost:8000/api/v1/jobs/{job_id}"
```

## Related Endpoints

For individual operations, you can also use:
- `POST /api/v1/videos/remove-audio` - Remove audio only
- `POST /api/v1/videos/color-grade` - Color grading only
- `POST /api/v1/videos/crop-zoom` - Crop and zoom only
- `POST /api/v1/videos/reencode` - Re-encode only
- `POST /api/v1/videos/merge-audio-video` - Merge audio and video only

## Server Setup

Make sure the FastAPI server is running:
```bash
python run_api.py
```

The API will be available at `http://localhost:8000` by default.

## API Documentation

Interactive API documentation is available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

