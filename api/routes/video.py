"""
Video processing endpoints - simple audio removal service.
"""

import os
import sys
import asyncio
from pathlib import Path
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, UploadFile, File, HTTPException, Request, BackgroundTasks, Form
from fastapi.responses import FileResponse, JSONResponse

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from api.core.job_manager import JobManager, JobStatus
from api.services.video_processor import VideoProcessor

router = APIRouter()

# Get job manager instance (will be injected via app state)
def get_job_manager(request: Request) -> JobManager:
    """Dependency to get job manager from app state."""
    return request.app.state.job_manager


@router.post("/videos/remove-audio")
async def remove_audio_from_video(
    background_tasks: BackgroundTasks,
    request: Request,
):
    """
    Upload a video and remove its audio track.
    
    Accepts a file upload with any field name (e.g., 'video', 'file', 'upload', etc.).
    The file must be sent as multipart/form-data.
    
    Returns a job_id immediately. Use GET /api/v1/jobs/{job_id} to poll for status.
    """
    job_manager: JobManager = get_job_manager(request)
    
    # Parse form data to get the uploaded file (accept any field name)
    # FastAPI will automatically handle multipart/form-data
    # We don't check Content-Type upfront because Postman/FastAPI handles it automatically
    try:
        form = await request.form()
    except Exception as e:
        # Provide helpful error message with debugging info
        content_type = request.headers.get("content-type", "NOT SET")
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Failed to parse form data",
                "content_type_received": content_type,
                "expected": "multipart/form-data",
                "parsing_error": str(e),
                "help": "In Postman: 1) Select 'Body' tab, 2) Choose 'form-data' (not raw/json), 3) Add key with type 'File', 4) Select your video file, 5) Make sure no Content-Type header is manually set"
            }
        )
    
    # Find the first file in the form data
    video_file = None
    field_name = None
    available_fields = []
    field_types = {}
    
    # Iterate through form data to find UploadFile
    for key, value in form.items():
        available_fields.append(key)
        field_types[key] = type(value).__name__
        
        # Check if it's an UploadFile - use multiple checks to be robust
        is_upload_file = (
            isinstance(value, UploadFile) or 
            type(value).__name__ == "UploadFile" or
            (hasattr(value, 'filename') and hasattr(value, 'read') and hasattr(value, 'file'))
        )
        
        if is_upload_file:
            video_file = value
            field_name = key
            break
    
    if not video_file:
        # Provide helpful error message with debugging info
        raise HTTPException(
            status_code=400,
            detail={
                "error": "No file uploaded",
                "found_fields": available_fields,
                "field_types": field_types,
                "help": "Make sure you're sending a file, not just text. In Postman, set the key type to 'File' (not 'Text'), then select your video file."
            }
        )
    
    # Save uploaded file
    upload_dir = project_root / "temp_videos" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    input_filename = video_file.filename or "video"
    input_path = upload_dir / f"input_{timestamp}_{input_filename}"
    
    try:
        # Save uploaded video
        with open(input_path, "wb") as f:
            content = await video_file.read()
            f.write(content)
        
        # Create output path - organized by use case
        output_dir = project_root / "temp_videos" / "output" / "audio_removal"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_filename = f"no_audio_{timestamp}_{Path(input_filename).stem}.mp4"
        output_path = output_dir / output_filename
        
        # Create job
        job_id = job_manager.create_job(
            job_type="remove_audio",
            parameters={
                "input_path": str(input_path),
                "output_path": str(output_path),
                "original_filename": input_filename,
            },
            output_path=output_path,
        )
        
        # Start background processing
        background_tasks.add_task(
            process_video_remove_audio,
            job_id=job_id,
            input_path=str(input_path),
            output_path=str(output_path),
            job_manager=job_manager,
        )
        
        # Return job_id immediately
        return {
            "job_id": job_id,
            "status": "pending",
            "message": "Video upload successful. Processing started.",
            "status_url": f"/api/v1/jobs/{job_id}",
            "download_url": f"/api/v1/videos/{job_id}/download",
        }
    
    except Exception as e:
        # Clean up on error
        if input_path.exists():
            input_path.unlink()
        raise HTTPException(status_code=500, detail=f"Error processing video: {str(e)}")


async def process_video_remove_audio(
    job_id: str,
    input_path: str,
    output_path: str,
    job_manager: JobManager,
):
    """
    Background task to process video and remove audio.
    """
    try:
        job_manager.update_job(
            job_id,
            status=JobStatus.PROCESSING,
            progress=10,
            message="Loading video file...",
        )
        
        # Run video processing in executor to avoid blocking
        loop = asyncio.get_event_loop()
        processor = VideoProcessor()
        
        job_manager.update_job(
            job_id,
            progress=30,
            message="Removing audio track...",
        )
        
        # Process video (runs in thread pool)
        await loop.run_in_executor(
            None,
            processor.remove_audio,
            input_path,
            output_path,
        )
        
        job_manager.update_job(
            job_id,
            progress=90,
            message="Finalizing video...",
        )
        
        # Verify output file exists
        if not Path(output_path).exists():
            raise Exception("Output file was not created")
        
        # Update job to completed
        job_manager.update_job(
            job_id,
            status=JobStatus.COMPLETED,
            progress=100,
            message="Audio removal completed",
            output_path=Path(output_path),
        )
    
    except Exception as e:
        error_msg = str(e)
        job_manager.update_job(
            job_id,
            status=JobStatus.FAILED,
            error=error_msg,
            message=f"Video processing failed: {error_msg}",
        )
    
    finally:
        # Clean up input file after processing
        try:
            if Path(input_path).exists():
                Path(input_path).unlink()
        except Exception:
            pass


@router.post("/videos/detect-scenes")
async def detect_scenes_in_video(
    background_tasks: BackgroundTasks,
    request: Request,
):
    """
    Upload a video and detect scene cuts.
    
    Returns a job_id immediately. Use GET /api/v1/jobs/{job_id} to poll for status.
    When completed, the job result will contain scene information.
    """
    job_manager: JobManager = get_job_manager(request)
    
    # Parse form data to get the uploaded file (accept any field name)
    try:
        form = await request.form()
    except Exception as e:
        content_type = request.headers.get("content-type", "NOT SET")
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Failed to parse form data",
                "content_type_received": content_type,
                "expected": "multipart/form-data",
                "parsing_error": str(e),
                "help": "In Postman: 1) Select 'Body' tab, 2) Choose 'form-data' (not raw/json), 3) Add key with type 'File', 4) Select your video file, 5) Make sure no Content-Type header is manually set"
            }
        )
    
    # Find the first file in the form data
    video_file = None
    field_name = None
    available_fields = []
    field_types = {}
    
    for key, value in form.items():
        available_fields.append(key)
        field_types[key] = type(value).__name__
        
        is_upload_file = (
            isinstance(value, UploadFile) or 
            type(value).__name__ == "UploadFile" or
            (hasattr(value, 'filename') and hasattr(value, 'read') and hasattr(value, 'file'))
        )
        
        if is_upload_file:
            video_file = value
            field_name = key
            break
    
    if not video_file:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "No file uploaded",
                "found_fields": available_fields,
                "field_types": field_types,
                "help": "Make sure you're sending a file, not just text. In Postman, set the key type to 'File' (not 'Text'), then select your video file."
            }
        )
    
    # Save uploaded file - organized by use case
    upload_dir = project_root / "temp_videos" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    input_filename = video_file.filename or "video"
    input_path = upload_dir / f"scene_detection_{timestamp}_{input_filename}"
    
    try:
        # Save uploaded video
        with open(input_path, "wb") as f:
            content = await video_file.read()
            f.write(content)
        
        # Create output path for scene data (JSON file)
        output_dir = project_root / "temp_videos" / "output" / "scene_detection"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_filename = f"scenes_{timestamp}_{Path(input_filename).stem}.json"
        output_path = output_dir / output_filename
        
        # Create job
        job_id = job_manager.create_job(
            job_type="scene_detection",
            parameters={
                "input_path": str(input_path),
                "output_path": str(output_path),
                "original_filename": input_filename,
            },
            output_path=output_path,
        )
        
        # Start background processing
        background_tasks.add_task(
            process_scene_detection,
            job_id=job_id,
            input_path=str(input_path),
            output_path=str(output_path),
            job_manager=job_manager,
        )
        
        # Return job_id immediately
        return {
            "job_id": job_id,
            "status": "pending",
            "message": "Scene detection started. Processing video...",
            "status_url": f"/api/v1/jobs/{job_id}",
        }
    
    except Exception as e:
        # Clean up on error
        if input_path.exists():
            input_path.unlink()
        raise HTTPException(status_code=500, detail=f"Error processing video: {str(e)}")


async def process_scene_detection(
    job_id: str,
    input_path: str,
    output_path: str,
    job_manager: JobManager,
):
    """Background task to detect scenes in video."""
    import json
    
    try:
        job_manager.update_job(
            job_id,
            status=JobStatus.PROCESSING,
            progress=10,
            message="Loading video file...",
        )
        
        # Run scene detection in executor to avoid blocking
        loop = asyncio.get_event_loop()
        processor = VideoProcessor()
        
        job_manager.update_job(
            job_id,
            progress=30,
            message="Analyzing video for scene cuts...",
        )
        
        # Detect scenes (runs in thread pool)
        scenes = await loop.run_in_executor(
            None,
            processor.detect_scenes,
            input_path,
        )
        
        job_manager.update_job(
            job_id,
            progress=80,
            message="Saving scene data...",
        )
        
        # Calculate total duration
        total_duration = scenes[-1]["end_time"] if scenes else 0
        
        # Prepare result data
        result_data = {
            "total_scenes": len(scenes),
            "video_duration": total_duration,
            "scenes": scenes,
        }
        
        # Save to JSON file
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result_data, f, indent=2)
        
        job_manager.update_job(
            job_id,
            status=JobStatus.COMPLETED,
            progress=100,
            message=f"Scene detection completed. Found {len(scenes)} scenes.",
            output_path=Path(output_path),
        )
        
        # Store scene data in job parameters for easy access
        job = job_manager.get_job(job_id)
        if job:
            job["parameters"]["scenes"] = scenes
            job["parameters"]["total_scenes"] = len(scenes)
            job["parameters"]["video_duration"] = total_duration
    
    except Exception as e:
        error_msg = str(e)
        job_manager.update_job(
            job_id,
            status=JobStatus.FAILED,
            error=error_msg,
            message=f"Scene detection failed: {error_msg}",
        )
    
    finally:
        # Clean up input file after processing
        try:
            if Path(input_path).exists():
                Path(input_path).unlink()
        except Exception:
            pass


@router.get("/videos/{job_id}/download")
async def download_video(job_id: str, request: Request):
    """Download processed video by job ID (for audio removal jobs)."""
    job_manager: JobManager = get_job_manager(request)
    
    job = job_manager.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job["type"] != "remove_audio":
        raise HTTPException(
            status_code=400,
            detail=f"This endpoint is for video downloads only. Job type: {job['type']}",
        )
    
    if job["status"] != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Job is not completed. Current status: {job['status']}",
        )
    
    output_path = job.get("output_path")
    if not output_path or not Path(output_path).exists():
        raise HTTPException(status_code=404, detail="Output file not found")
    
    # Get original filename if available
    original_filename = job.get("parameters", {}).get("original_filename", "video.mp4")
    output_filename = f"no_audio_{Path(original_filename).stem}.mp4"
    
    return FileResponse(
        output_path,
        media_type="video/mp4",
        filename=output_filename,
    )


@router.get("/videos/{job_id}/scenes")
async def get_scene_detection_results(job_id: str, request: Request):
    """
    Get scene detection results by job ID.
    
    Returns scene data for completed scene detection jobs.
    Scene data is also available in the job status endpoint.
    """
    job_manager: JobManager = get_job_manager(request)
    
    job = job_manager.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job["type"] != "scene_detection":
        raise HTTPException(
            status_code=400,
            detail=f"This endpoint is for scene detection results only. Job type: {job['type']}",
        )
    
    if job["status"] != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Job is not completed. Current status: {job['status']}",
        )
    
    # Return scene data from job parameters
    scenes = job.get("parameters", {}).get("scenes", [])
    total_scenes = job.get("parameters", {}).get("total_scenes", len(scenes))
    video_duration = job.get("parameters", {}).get("video_duration", 0)
    
    return {
        "job_id": job_id,
        "total_scenes": total_scenes,
        "video_duration": video_duration,
        "scenes": scenes,
    }


@router.get("/videos/{job_id}/scenes/download")
async def download_scene_data(job_id: str, request: Request):
    """Download scene detection results as JSON file."""
    job_manager: JobManager = get_job_manager(request)
    
    job = job_manager.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job["type"] != "scene_detection":
        raise HTTPException(
            status_code=400,
            detail=f"This endpoint is for scene detection results only. Job type: {job['type']}",
        )
    
    if job["status"] != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Job is not completed. Current status: {job['status']}",
        )
    
    output_path = job.get("output_path")
    if not output_path or not Path(output_path).exists():
        raise HTTPException(status_code=404, detail="Scene data file not found")
    
    # Get original filename if available
    original_filename = job.get("parameters", {}).get("original_filename", "video.mp4")
    output_filename = f"scenes_{Path(original_filename).stem}.json"
    
    return FileResponse(
        output_path,
        media_type="application/json",
        filename=output_filename,
    )
