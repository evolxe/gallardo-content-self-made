# FastAPI Video Processing Service

A FastAPI-based service for removing audio from videos with job-based processing and polling.

## Features

- **Audio Removal**: Upload a video and remove its audio track
- **Job-Based Processing**: Submit job and poll for status
- **Background Processing**: Long-running video processing tasks run in background
- **Job Tracking**: Track job status and download completed videos

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

### Video Processing
- `POST /api/v1/videos/remove-audio` - Upload video and remove audio
  - Accepts: `video` (file upload)
  - Returns: JSON with `job_id` immediately
  - Processing happens in background

### Job Management
- `GET /api/v1/jobs/{job_id}` - Get job status (poll this endpoint)
- `GET /api/v1/jobs` - List all jobs (with optional status filter)
- `DELETE /api/v1/jobs/{job_id}` - Delete a job
- `GET /api/v1/videos/{job_id}/download` - Download processed video

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
    └── video_processor.py  # Video processing service (audio removal)
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
- Uploaded files are stored in `temp_videos/uploads/`
- Processed videos are stored in `temp_videos/output/`
- Input files are automatically cleaned up after processing
- Job information is stored in memory (consider using Redis/database for production)
- Poll the status endpoint to check job progress
