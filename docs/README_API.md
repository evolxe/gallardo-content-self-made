# FastAPI Video Processing Service

A FastAPI-based service for video processing with job-based processing and polling.

## Features

- **Audio Removal**: Upload a video and remove its audio track
- **Scene Detection**: Upload a video and detect scene cuts with timestamps
- **Job-Based Processing**: Submit job and poll for status
- **Background Processing**: Long-running video processing tasks run in background
- **Job Tracking**: Track job status and download completed videos
- **Organized Storage**: Outputs organized by use case in separate folders

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Ensure you have the required environment variables set (see your `.env` file)

## Running the Service

### Development Mode
```bash
python run_api.py --reload
```

### Production Mode
```bash
python run_api.py --host 0.0.0.0 --port 8000
```

Or using uvicorn directly:
```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

## API Endpoints

### Health Check
- `GET /api/v1/health` - Service health check

### Video Processing - Audio Removal
- `POST /api/v1/videos/remove-audio` - Upload video and remove audio
  - Accepts: Any file field name (e.g., `video`, `file`, `upload`)
  - Returns: JSON with `job_id` immediately
  - Processing happens in background
  - Output: Processed video without audio

### Video Processing - Scene Detection
- `POST /api/v1/videos/detect-scenes` - Upload video and detect scene cuts
  - Accepts: Any file field name (e.g., `video`, `file`, `upload`)
  - Returns: JSON with `job_id` immediately
  - Processing happens in background
  - Output: JSON file with scene timestamps

### Job Management
- `GET /api/v1/jobs/{job_id}` - Get job status (poll this endpoint)
- `GET /api/v1/jobs` - List all jobs (with optional status filter)
- `DELETE /api/v1/jobs/{job_id}` - Delete a job

### Download Endpoints
- `GET /api/v1/videos/{job_id}/download` - Download processed video (audio removal jobs)
- `GET /api/v1/videos/{job_id}/scenes` - Get scene detection results (JSON response)
- `GET /api/v1/videos/{job_id}/scenes/download` - Download scene data as JSON file

## API Documentation

Once the service is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Example Usage

### 1. Upload Video and Get Job ID

```bash
curl -X POST "http://localhost:8000/api/v1/videos/remove-audio" \
  -F "video=@input.mp4"
```

Response:
```json
{
  "job_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "pending",
  "message": "Video upload successful. Processing started.",
  "status_url": "/api/v1/jobs/123e4567-e89b-12d3-a456-426614174000",
  "download_url": "/api/v1/videos/123e4567-e89b-12d3-a456-426614174000/download"
}
```

### 2. Poll for Job Status

```bash
curl "http://localhost:8000/api/v1/jobs/123e4567-e89b-12d3-a456-426614174000"
```

Response (while processing):
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "type": "remove_audio",
  "status": "processing",
  "progress": 30,
  "message": "Removing audio track...",
  "created_at": "2025-01-09T12:00:00",
  "updated_at": "2025-01-09T12:00:05"
}
```

Response (when completed):
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "type": "remove_audio",
  "status": "completed",
  "progress": 100,
  "message": "Audio removal completed",
  "output_path": "/path/to/output.mp4",
  "created_at": "2025-01-09T12:00:00",
  "updated_at": "2025-01-09T12:00:30"
}
```

### 3. Download Processed Video

```bash
curl "http://localhost:8000/api/v1/videos/123e4567-e89b-12d3-a456-426614174000/download" \
  --output output.mp4
```

### 4. Scene Detection Example

```bash
# 1. Upload video for scene detection
curl -X POST "http://localhost:8000/api/v1/videos/detect-scenes" \
  -F "video=@input.mp4"
```

Response:
```json
{
  "job_id": "456e7890-e89b-12d3-a456-426614174001",
  "status": "pending",
  "message": "Scene detection started. Processing video...",
  "status_url": "/api/v1/jobs/456e7890-e89b-12d3-a456-426614174001"
}
```

```bash
# 2. Poll for status
curl "http://localhost:8000/api/v1/jobs/456e7890-e89b-12d3-a456-426614174001"
```

Response (when completed):
```json
{
  "id": "456e7890-e89b-12d3-a456-426614174001",
  "type": "scene_detection",
  "status": "completed",
  "progress": 100,
  "message": "Scene detection completed. Found 5 scenes.",
  "parameters": {
    "scenes": [
      {
        "scene_number": 1,
        "start_time": 0.0,
        "end_time": 12.5,
        "duration": 12.5,
        "start_time_formatted": "00:00:00.000",
        "end_time_formatted": "00:00:12.500"
      },
      {
        "scene_number": 2,
        "start_time": 12.5,
        "end_time": 25.3,
        "duration": 12.8,
        "start_time_formatted": "00:00:12.500",
        "end_time_formatted": "00:00:25.300"
      }
    ],
    "total_scenes": 5,
    "video_duration": 60.5
  }
}
```

```bash
# 3. Get scene results (JSON response)
curl "http://localhost:8000/api/v1/videos/456e7890-e89b-12d3-a456-426614174001/scenes"

# 4. Or download scene data as JSON file
curl "http://localhost:8000/api/v1/videos/456e7890-e89b-12d3-a456-426614174001/scenes/download" \
  --output scenes.json
```

### Complete Example (Python)

```python
import requests
import time

# 1. Upload video
files = {'video': open('input.mp4', 'rb')}
response = requests.post(
    'http://localhost:8000/api/v1/videos/remove-audio',
    files=files
)
job_data = response.json()
job_id = job_data['job_id']
print(f"Job ID: {job_id}")

# 2. Poll for status
while True:
    status_response = requests.get(
        f'http://localhost:8000/api/v1/jobs/{job_id}'
    )
    job = status_response.json()
    
    print(f"Status: {job['status']}, Progress: {job['progress']}%")
    
    if job['status'] == 'completed':
        print("Processing completed!")
        break
    elif job['status'] == 'failed':
        print(f"Processing failed: {job.get('error', 'Unknown error')}")
        break
    
    time.sleep(2)  # Poll every 2 seconds

# 3. Download video
if job['status'] == 'completed':
    download_response = requests.get(
        f'http://localhost:8000/api/v1/videos/{job_id}/download'
    )
    with open('output.mp4', 'wb') as f:
        f.write(download_response.content)
    print("Video downloaded!")
```

## Project Structure

```
api/
├── main.py                 # FastAPI app entry point
├── core/
│   └── job_manager.py      # Job tracking and management
├── routes/
│   ├── video.py           # Video processing endpoints
│   └── status.py          # Status/job endpoints
└── services/
    └── video_processor.py  # Video processing service

temp_videos/
├── uploads/               # Temporary uploaded files (auto-cleaned)
└── output/
    ├── audio_removal/     # Processed videos without audio
    └── scene_detection/   # Scene detection JSON results
```

## Job Status

Jobs can have the following statuses:
- `pending` - Job created, waiting to start
- `processing` - Job is currently being processed
- `completed` - Job completed successfully
- `failed` - Job failed with an error
- `cancelled` - Job was cancelled

## Notes

- Video processing runs in background tasks
- Uploaded files are stored in `temp_videos/uploads/` (auto-cleaned after processing)
- Outputs are organized by use case:
  - `temp_videos/output/audio_removal/` - Processed videos without audio
  - `temp_videos/output/scene_detection/` - Scene detection JSON results
- Input files are automatically cleaned up after processing
- Job information is stored in memory (consider using Redis/database for production)
- Poll the status endpoint to check job progress
- Scene detection uses PySceneDetect library for accurate scene cut detection
