<div align="center">

# 🎬 Video Processing API

**A powerful, production-ready FastAPI service for comprehensive video manipulation and processing**

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![FFmpeg](https://img.shields.io/badge/FFmpeg-Powered-007808?style=for-the-badge&logo=ffmpeg&logoColor=white)](https://ffmpeg.org/)

*Transform, enhance, and process videos with ease*

[Features](#-features) • [Quick Start](#-quick-start) • [API Documentation](#-api-endpoints) • [Examples](#-usage-examples) • [Deployment](#-deployment)

</div>

---

## ✨ Features

### 🎥 Core Video Operations
- **📥 Video Download** - Download videos from YouTube, Instagram, and 1000+ platforms via `yt-dlp`
- **🔇 Audio Removal** - Strip audio tracks from videos
- **🎵 Audio Merging** - Combine separate audio files with videos
- **🎨 Color Grading** - Apply cinematic color presets (cinematic, warm, cool, vintage, vivid, B&W, natural, random)
- **✂️ Smart Cropping** - Crop to any aspect ratio with customizable background padding
- **🔄 Re-encoding** - Convert videos with custom codecs, bitrates, and frame rates
- **🎬 Scene Detection** - Automatically detect scene changes in videos

### 🚀 Advanced Capabilities
- **⚡ Background Processing** - Asynchronous job-based processing with real-time status tracking
- **🎯 Comprehensive Processing** - Apply multiple transformations in a single request
- **🌐 URL Support** - Process videos directly from URLs (no upload required)
- **🍪 Cookie Authentication** - Support for authenticated downloads with cookie files
- **📊 Job Management** - Track processing jobs with status, progress, and error reporting
- **💾 Smart File Handling** - Automatic format detection and extension guessing

### 🎨 Color Grading Presets
| Preset | Description | Effect |
|--------|-------------|--------|
| 🎬 **Cinematic** | Cool tones, enhanced contrast | Professional film look |
| 🔥 **Warm** | Golden, sunset vibes | Cozy, inviting atmosphere |
| ❄️ **Cool** | Blue tones, crisp | Fresh, modern aesthetic |
| 📸 **Vintage** | Warm, desaturated | Retro, nostalgic feel |
| 🌈 **Vivid** | High saturation, punchy | Bold, eye-catching colors |
| ⚫ **B&W** | Classic monochrome | Timeless black & white |
| 🌿 **Natural** | Balanced, true-to-life | Clean, authentic look |
| 🎲 **Random** | Surprise me! | Randomized creative preset |

---

## 🚀 Quick Start

### Prerequisites

- Python 3.8+ or Docker
- FFmpeg installed system-wide
- Node.js (for yt-dlp JavaScript runtime)

### Installation

#### Option 1: Docker (Recommended)

```bash
# Build and run with Docker
docker-compose up --build
```

#### Option 2: Local Installation

```bash
# Clone the repository
git clone <repository-url>
cd gallardo-content-self-made

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration

# Run the API
python run_api.py
```

The API will be available at `http://localhost:8000`

### Verify Installation

```bash
# Test FFmpeg availability
python tests/test_ffmpeg.py

# Check API health
curl http://localhost:8000/api/v1/health
```

---

## 📚 API Endpoints

### 🏥 Health & Status

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/health` | API health check |
| `GET` | `/api/v1/jobs/{job_id}` | Get job status and progress |
| `GET` | `/api/v1/jobs` | List all jobs |

### 🎬 Video Processing Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/videos/download-from-url` | Download video from URL (YouTube, Instagram, etc.) |
| `POST` | `/api/v1/videos/download-audio-from-url` | Download audio only from URL |
| `POST` | `/api/v1/videos/remove-audio` | Remove audio track from video |
| `POST` | `/api/v1/videos/merge-audio-video` | Merge audio file with video |
| `POST` | `/api/v1/videos/color-grade` | Apply color grading presets |
| `POST` | `/api/v1/videos/crop-zoom` | Crop video to aspect ratio with background padding |
| `POST` | `/api/v1/videos/reencode` | Re-encode video with custom settings |
| `POST` | `/api/v1/videos/detect-scenes` | Detect scene changes in video |
| `POST` | `/api/v1/videos/process` | **Comprehensive processing** (all operations) |

### 📥 Download Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/videos/{job_id}/download` | Download processed video |
| `GET` | `/api/v1/videos/{job_id}/scenes` | Get scene detection results (JSON) |
| `GET` | `/api/v1/videos/{job_id}/scenes/download` | Download scene detection results (CSV) |

---

## 💡 Usage Examples

### Example 1: Download Video from YouTube

```bash
curl -X POST "http://localhost:8000/api/v1/videos/download-from-url" \
  -F "video_url=https://www.youtube.com/watch?v=VIDEO_ID" \
  -F "cookies_file=@cookies.txt"  # Optional: for private videos
```

### Example 2: Remove Audio from Video

```bash
curl -X POST "http://localhost:8000/api/v1/videos/remove-audio" \
  -F "video=@my_video.mp4"
```

### Example 3: Apply Color Grading

```bash
curl -X POST "http://localhost:8000/api/v1/videos/color-grade" \
  -F "video=@my_video.mp4" \
  -F "color_preset=cinematic" \
  -F "color_brightness=0.1" \
  -F "color_contrast=1.2" \
  -F "color_saturation=1.1"
```

### Example 4: Crop to Square with Custom Background

```bash
curl -X POST "http://localhost:8000/api/v1/videos/crop-zoom" \
  -F "video=@my_video.mp4" \
  -F "aspect_ratio=1:1" \
  -F "background_color=#FF5733"
```

### Example 5: Comprehensive Processing (All-in-One)

```bash
curl -X POST "http://localhost:8000/api/v1/videos/process" \
  -F "video=@my_video.mp4" \
  -F "audio=@my_audio.mp3" \
  -F "merge_audio=true" \
  -F "color_grading=true" \
  -F "color_preset=vintage" \
  -F "crop_zoom=true" \
  -F "crop_aspect_ratio=16:9" \
  -F "crop_background_color=black" \
  -F "reencode=true" \
  -F "codec=libx264" \
  -F "bitrate=5000k" \
  -F "fps=30"
```

### Example 6: Check Job Status

```bash
# Get job status
curl "http://localhost:8000/api/v1/jobs/{job_id}"

# Response:
# {
#   "id": "job-id",
#   "status": "processing",
#   "progress": 65,
#   "message": "Applying color grading..."
# }
```

### Example 7: Download Processed Video

```bash
curl -O "http://localhost:8000/api/v1/videos/{job_id}/download"
```

---

## 🎯 Comprehensive Processing

The `/api/v1/videos/process` endpoint allows you to apply multiple transformations in a single request:

### Processing Order
1. **Merge Audio** (if `merge_audio=true`)
2. **Remove Audio** (if `remove_audio=true`, overrides merge)
3. **Color Grading** (if `color_grading=true`)
4. **Crop & Zoom** (if `crop_zoom=true`)
5. **Re-encode** (if `reencode=true`)

### Parameters

#### Boolean Flags
- `remove_audio` - Remove audio track
- `merge_audio` - Merge audio file (requires audio upload)
- `color_grading` - Apply color grading
- `crop_zoom` - Crop to aspect ratio with padding
- `reencode` - Re-encode video

#### Color Grading
- `color_preset` - `cinematic`, `warm`, `cool`, `vintage`, `vivid`, `bw`, `natural`, `random`
- `color_brightness` - `-1.0` to `1.0`
- `color_contrast` - `0.0` to `2.0`
- `color_saturation` - `0.0` to `2.0`

#### Crop & Zoom
- `crop_aspect_ratio` - Format: `"W:H"` (e.g., `"16:9"`, `"1:1"`, `"4:3"`)
- `crop_background_color` - Hex (`#000000`) or named color (`black`, `white`, etc.)
- Output: Always `9:16` (1080x1920) with background padding

#### Re-encoding
- `codec` - Video codec (default: `libx264`)
- `bitrate` - Target bitrate (e.g., `"5000k"`)
- `fps` - Target frame rate

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Application                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Routes     │  │   Services   │  │   Core       │     │
│  │              │  │              │  │              │     │
│  │ • video.py   │→ │ • video_     │  │ • job_       │     │
│  │ • status.py  │  │   processor  │  │   manager    │     │
│  │              │  │ • ytdlp_     │  │              │     │
│  │              │  │   service    │  │              │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │           Background Task Processing                  │  │
│  │  • Asynchronous job execution                        │  │
│  │  • Progress tracking                                 │  │
│  │  • Error handling                                    │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │           External Tools                              │  │
│  │  • FFmpeg (video processing)                          │  │
│  │  • yt-dlp (video download)                             │  │
│  │  • MoviePy (Python video library)                      │  │
│  │  • SceneDetect (scene detection)                      │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Key Components

- **FastAPI Router** - RESTful API endpoints
- **VideoProcessor** - Core video manipulation logic
- **YTDLPService** - YouTube/download service integration
- **JobManager** - Background job tracking and management
- **Background Tasks** - Asynchronous processing

---

## 🔧 Configuration

### Environment Variables

Create a `.env` file in the root directory:

```env
# API Configuration
API_HOST=0.0.0.0
API_PORT=8000

# Google Sheets (if using)
GOOGLE_SHEET_URL=your_sheet_url
GOOGLE_SERVICE_ACCOUNT_PATH=path/to/service_account.json

# NextCloud (if using)
NEXTCLOUD_URL=your_nextcloud_url
NEXTCLOUD_USERNAME=your_username
NEXTCLOUD_PASSWORD=your_password

# Webhooks (if using)
WEBHOOK_URL=your_webhook_url
```

### FFmpeg Setup

FFmpeg must be installed system-wide:

```bash
# Linux
sudo apt-get install ffmpeg

# macOS
brew install ffmpeg

# Windows
# Download from https://ffmpeg.org/download.html
```

### Node.js Setup (for yt-dlp)

```bash
# Linux/macOS
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs

# Or via package manager
brew install nodejs  # macOS
```

---

## 🐳 Docker Deployment

### Build and Run

```bash
# Build image
docker build -t video-processing-api .

# Run container
docker run -p 8000:8000 \
  -v $(pwd)/temp_videos:/app/temp_videos \
  video-processing-api
```

### Docker Compose

```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

---

## 📖 Documentation

- **API Documentation**: Available at `http://localhost:8000/docs` (Swagger UI)
- **Alternative Docs**: `http://localhost:8000/redoc` (ReDoc)
- **Video Processing Guide**: See `docs/README_VIDEO_PROCESSING.md`
- **Cookie Setup**: See `cookies/COOKIES_FILE_INSTRUCTIONS.md`

---

## 🧪 Testing

```bash
# Run FFmpeg availability test
python tests/test_ffmpeg.py

# Test API endpoints (using Postman collection)
# Import Video_Processing_API.postman_collection.json
```

---

## 🛠️ Development

### Project Structure

```
gallardo-content-self-made/
├── api/
│   ├── core/           # Core functionality (job manager)
│   ├── routes/         # API endpoints
│   └── services/       # Business logic (video processor, yt-dlp)
├── tests/              # Test files
├── temp_videos/        # Temporary video storage
├── docs/               # Documentation
├── cookies/            # Cookie files for authentication
└── requirements.txt    # Python dependencies
```

### Adding New Features

1. Add endpoint in `api/routes/video.py`
2. Implement logic in `api/services/video_processor.py`
3. Add tests in `tests/`
4. Update documentation

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📝 License

This project is proprietary software. All rights reserved.

---

## 🙏 Acknowledgments

- **FastAPI** - Modern, fast web framework
- **MoviePy** - Video editing library
- **yt-dlp** - YouTube downloader
- **FFmpeg** - Multimedia framework
- **SceneDetect** - Scene detection library

---

## 📞 Support

For issues, questions, or contributions, please open an issue on the repository.

---

<div align="center">

**Built with ❤️ for video content creators**

[⬆ Back to Top](#-video-processing-api)

</div>
