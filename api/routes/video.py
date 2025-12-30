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
from api.services.ytdlp_service import YTDLPService

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
    """Download processed video by job ID (for audio removal and color grading jobs)."""
    job_manager: JobManager = get_job_manager(request)
    
    job = job_manager.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Allow download for video output jobs
    if job["type"] not in ["remove_audio", "color_grading", "crop_zoom", "reencode", "merge_audio_video", "comprehensive", "ytdlp_download"]:
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
    
    # Generate appropriate output filename based on job type
    if job["type"] == "remove_audio":
        output_filename = f"no_audio_{Path(original_filename).stem}.mp4"
    elif job["type"] == "color_grading":
        preset = job.get("parameters", {}).get("preset", "graded")
        output_filename = f"graded_{preset}_{Path(original_filename).stem}.mp4"
    elif job["type"] == "crop_zoom":
        output_size = job.get("parameters", {}).get("output_size", 1080)
        size_suffix = f"{output_size}x{output_size}" if output_size else "square"
        output_filename = f"square_{size_suffix}_{Path(original_filename).stem}.mp4"
    elif job["type"] == "reencode":
        codec = job.get("parameters", {}).get("codec", "libx264")
        output_filename = f"reencoded_{codec}_{Path(original_filename).stem}.mp4"
    elif job["type"] == "merge_audio_video":
        output_filename = f"merged_{Path(original_filename).stem}.mp4"
    elif job["type"] == "comprehensive":
        # Use the actual output filename from the job parameters
        output_filename = Path(job.get("output_path", "")).name or f"processed_{Path(original_filename).stem}.mp4"
    else:
        output_filename = f"processed_{Path(original_filename).stem}.mp4"
    
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


@router.post("/videos/download-from-url")
async def download_video_from_url(
    background_tasks: BackgroundTasks,
    request: Request,
    url: str = Form(...),
    quality: Optional[str] = Form("best"),
    format_type: Optional[str] = Form("mp4"),
    audio_only: Optional[bool] = Form(False),
    output_filename: Optional[str] = Form(None),
):
    """
    Download a video from a URL using yt-dlp (subprocess-based implementation).
    
    Supports YouTube, Vimeo, and other platforms supported by yt-dlp.
    
    Parameters (form-data):
    - url: URL of the video to download (required)
    - quality: Video quality ('best', 'worst', '720p', '1080p', etc.) - default: 'best'
    - format_type: Output format ('mp4', 'webm', etc.) - default: 'mp4'
    - audio_only: If True, download audio only (as mp3) - default: False
    - output_filename: Optional custom filename (without extension)
    
    Returns a job_id immediately. Use GET /api/v1/jobs/{job_id} to poll for status.
    When completed, download the video via GET /api/v1/videos/{job_id}/download
    """
    job_manager: JobManager = get_job_manager(request)
    
    # Validate URL
    if not url or not url.strip():
        raise HTTPException(status_code=400, detail="URL parameter is required")
    
    # Create job
    job_id = job_manager.create_job(
        job_type="ytdlp_download",
        parameters={
            "url": url,
            "quality": quality,
            "format_type": format_type,
            "audio_only": audio_only,
            "output_filename": output_filename,
        },
    )
    
    # Prepare output directory
    output_dir = project_root / "temp_videos" / "output" / "ytdlp_downloads"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate output filename
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    if output_filename:
        safe_filename = "".join(c for c in output_filename if c.isalnum() or c in (' ', '-', '_')).strip()
        output_path = output_dir / f"{safe_filename}.{format_type if not audio_only else 'mp3'}"
    else:
        output_path = output_dir / f"download_{timestamp}.{format_type if not audio_only else 'mp3'}"
    
    # Start background processing
    background_tasks.add_task(
        process_ytdlp_download,
        job_id=job_id,
        url=url,
        output_path=str(output_path),
        quality=quality,
        format_type=format_type,
        audio_only=audio_only,
        output_filename=output_filename,
        job_manager=job_manager,
    )
    
    # Return job_id immediately
    return {
        "job_id": job_id,
        "status": "pending",
        "message": "Download started",
        "status_url": f"/api/v1/jobs/{job_id}",
        "download_url": f"/api/v1/videos/{job_id}/download",
    }


async def process_ytdlp_download(
    job_id: str,
    url: str,
    output_path: str,
    quality: str,
    format_type: str,
    audio_only: bool,
    output_filename: Optional[str],
    job_manager: JobManager,
):
    """
    Background task to download video using yt-dlp.
    """
    try:
        job_manager.update_job(
            job_id,
            status=JobStatus.PROCESSING,
            progress=10,
            message="Initializing download...",
        )
        
        # Initialize yt-dlp service
        output_dir = Path(output_path).parent
        ytdlp_service = YTDLPService(output_dir=output_dir)
        
        job_manager.update_job(
            job_id,
            progress=20,
            message="Connecting to video source...",
        )
        
        # Run download in executor to avoid blocking
        loop = asyncio.get_event_loop()
        
        job_manager.update_job(
            job_id,
            progress=30,
            message="Downloading video...",
        )
        
        # Download video (runs in thread pool)
        result = await loop.run_in_executor(
            None,
            ytdlp_service.download_video,
            url,
            output_filename,
            quality,
            format_type,
            audio_only,
        )
        
        job_manager.update_job(
            job_id,
            progress=90,
            message="Download completed, finalizing...",
        )
        
        # Verify output file exists
        actual_output_path = Path(result["output_path"])
        if not actual_output_path.exists():
            raise Exception("Downloaded file was not found")
        
        # Update job to completed
        job_manager.update_job(
            job_id,
            status=JobStatus.COMPLETED,
            progress=100,
            message="Download completed successfully",
            output_path=actual_output_path,
        )
    
    except Exception as e:
        error_msg = str(e)
        job_manager.update_job(
            job_id,
            status=JobStatus.FAILED,
            error=error_msg,
            message=f"Download failed: {error_msg}",
        )


@router.post("/videos/color-grade")
async def color_grade_video(
    background_tasks: BackgroundTasks,
    request: Request,
    preset: Optional[str] = Form("random"),
    brightness: Optional[float] = Form(None),
    contrast: Optional[float] = Form(None),
    saturation: Optional[float] = Form(None),
):
    """
    Upload a video and apply color grading.
    
    Accepts a file upload with any field name (e.g., 'video', 'file', 'upload', etc.).
    The file must be sent as multipart/form-data.
    
    Parameters:
    - preset: Color grading preset (cinematic, warm, cool, vintage, vivid, bw, natural, random)
              Defaults to "random" which applies random color grading
    - brightness: Brightness adjustment (-1.0 to 1.0). If not provided, will be random when preset is "random"
    - contrast: Contrast adjustment (0.0 to 2.0). If not provided, will be random when preset is "random"
    - saturation: Saturation adjustment (0.0 to 2.0). If not provided, will be random when preset is "random"
    
    Returns a job_id immediately. Use GET /api/v1/jobs/{job_id} to poll for status.
    When completed, download the video via GET /api/v1/videos/{job_id}/download
    """
    job_manager: JobManager = get_job_manager(request)
    
    valid_presets = ["cinematic", "warm", "cool", "vintage", "vivid", "bw", "natural", "random"]
    
    # Generate random parameters if preset is "random" or if parameters are None
    use_random = preset == "random"
    
    if use_random:
        # Generate random color grading parameters
        preset, brightness, contrast, saturation = VideoProcessor.generate_random_color_grading()
    else:
        # Validate preset if not random
        if preset not in valid_presets:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": f"Invalid preset '{preset}'",
                    "valid_presets": valid_presets,
                    "help": f"Choose one of: {', '.join(valid_presets)}"
                }
            )
        
        # Use defaults if parameters are None (only when not using random)
        if brightness is None:
            brightness = 0.0
        if contrast is None:
            contrast = 1.0
        if saturation is None:
            saturation = 1.0
    
    # Validate adjustment ranges
    if not -1.0 <= brightness <= 1.0:
        raise HTTPException(
            status_code=400,
            detail="Brightness must be between -1.0 and 1.0"
        )
    if not 0.0 <= contrast <= 2.0:
        raise HTTPException(
            status_code=400,
            detail="Contrast must be between 0.0 and 2.0"
        )
    if not 0.0 <= saturation <= 2.0:
        raise HTTPException(
            status_code=400,
            detail="Saturation must be between 0.0 and 2.0"
        )
    
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
    
    # Save uploaded file
    upload_dir = project_root / "temp_videos" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    input_filename = video_file.filename or "video"
    input_path = upload_dir / f"color_grade_{timestamp}_{input_filename}"
    
    try:
        # Save uploaded video
        with open(input_path, "wb") as f:
            content = await video_file.read()
            f.write(content)
        
        # Create output path
        output_dir = project_root / "temp_videos" / "output" / "color_grading"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_filename = f"graded_{preset}_{timestamp}_{Path(input_filename).stem}.mp4"
        output_path = output_dir / output_filename
        
        # Create job
        job_id = job_manager.create_job(
            job_type="color_grading",
            parameters={
                "input_path": str(input_path),
                "output_path": str(output_path),
                "original_filename": input_filename,
                "preset": preset,
                "brightness": brightness,
                "contrast": contrast,
                "saturation": saturation,
                "was_random": use_random,  # Track if random was used
            },
            output_path=output_path,
        )
        
        # Start background processing
        background_tasks.add_task(
            process_color_grading,
            job_id=job_id,
            input_path=str(input_path),
            output_path=str(output_path),
            preset=preset,
            brightness=brightness,
            contrast=contrast,
            saturation=saturation,
            job_manager=job_manager,
        )
        
        # Return job_id immediately
        response = {
            "job_id": job_id,
            "status": "pending",
            "message": "Video upload successful. Color grading started.",
            "status_url": f"/api/v1/jobs/{job_id}",
            "download_url": f"/api/v1/videos/{job_id}/download",
            "preset": preset,
            "adjustments": {
                "brightness": brightness,
                "contrast": contrast,
                "saturation": saturation,
            },
        }
        
        if use_random:
            response["random"] = True
            response["message"] += " (Random color grading applied)"
        
        return response
    
    except Exception as e:
        # Clean up on error
        if input_path.exists():
            input_path.unlink()
        raise HTTPException(status_code=500, detail=f"Error processing video: {str(e)}")


async def process_color_grading(
    job_id: str,
    input_path: str,
    output_path: str,
    preset: str,
    brightness: float,
    contrast: float,
    saturation: float,
    job_manager: JobManager,
):
    """Background task to apply color grading to video."""
    try:
        job_manager.update_job(
            job_id,
            status=JobStatus.PROCESSING,
            progress=10,
            message="Loading video file...",
        )
        
        # Run color grading in executor to avoid blocking
        loop = asyncio.get_event_loop()
        processor = VideoProcessor()
        
        job_manager.update_job(
            job_id,
            progress=30,
            message=f"Applying {preset} color grading...",
        )
        
        # Process video (runs in thread pool)
        await loop.run_in_executor(
            None,
            processor.apply_color_grading,
            input_path,
            output_path,
            preset,
            brightness,
            contrast,
            saturation,
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
            message=f"Color grading completed ({preset} preset)",
            output_path=Path(output_path),
        )
    
    except Exception as e:
        error_msg = str(e)
        job_manager.update_job(
            job_id,
            status=JobStatus.FAILED,
            error=error_msg,
            message=f"Color grading failed: {error_msg}",
        )
    
    finally:
        # Clean up input file after processing
        try:
            if Path(input_path).exists():
                Path(input_path).unlink()
        except Exception:
            pass


@router.post("/videos/crop-zoom")
async def crop_and_zoom_video(
    background_tasks: BackgroundTasks,
    request: Request,
    output_size: Optional[int] = Form(1080),
):
    """
    Upload a video and crop it to center 1:1 (square) aspect ratio.
    
    Accepts a file upload with any field name (e.g., 'video', 'file', 'upload', etc.).
    The file must be sent as multipart/form-data.
    
    Parameters:
    - output_size: Output square size in pixels (default: 1080, creates 1080x1080 video)
                   Set to 0 to keep original cropped resolution
    
    Returns a job_id immediately. Use GET /api/v1/jobs/{job_id} to poll for status.
    When completed, download the video via GET /api/v1/videos/{job_id}/download
    """
    job_manager: JobManager = get_job_manager(request)
    
    # Validate output_size
    if output_size is not None and output_size < 0:
        raise HTTPException(
            status_code=400,
            detail="output_size must be 0 or greater (0 = keep original cropped resolution)"
        )
    
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
    
    # Save uploaded file
    upload_dir = project_root / "temp_videos" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    input_filename = video_file.filename or "video"
    input_path = upload_dir / f"crop_zoom_{timestamp}_{input_filename}"
    
    try:
        # Save uploaded video
        with open(input_path, "wb") as f:
            content = await video_file.read()
            f.write(content)
        
        # Create output path
        output_dir = project_root / "temp_videos" / "output" / "crop_zoom"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        size_suffix = f"{output_size}x{output_size}" if output_size else "original"
        output_filename = f"square_{size_suffix}_{timestamp}_{Path(input_filename).stem}.mp4"
        output_path = output_dir / output_filename
        
        # Create job
        job_id = job_manager.create_job(
            job_type="crop_zoom",
            parameters={
                "input_path": str(input_path),
                "output_path": str(output_path),
                "original_filename": input_filename,
                "output_size": output_size,
            },
            output_path=output_path,
        )
        
        # Start background processing
        background_tasks.add_task(
            process_crop_and_zoom,
            job_id=job_id,
            input_path=str(input_path),
            output_path=str(output_path),
            output_size=output_size,
            job_manager=job_manager,
        )
        
        # Return job_id immediately
        return {
            "job_id": job_id,
            "status": "pending",
            "message": "Video upload successful. Crop and zoom started.",
            "status_url": f"/api/v1/jobs/{job_id}",
            "download_url": f"/api/v1/videos/{job_id}/download",
            "output_size": output_size,
        }
    
    except Exception as e:
        # Clean up on error
        if input_path.exists():
            input_path.unlink()
        raise HTTPException(status_code=500, detail=f"Error processing video: {str(e)}")


async def process_crop_and_zoom(
    job_id: str,
    input_path: str,
    output_path: str,
    output_size: int,
    job_manager: JobManager,
):
    """Background task to crop and zoom video to square."""
    try:
        job_manager.update_job(
            job_id,
            status=JobStatus.PROCESSING,
            progress=10,
            message="Loading video file...",
        )
        
        # Run crop and zoom in executor to avoid blocking
        loop = asyncio.get_event_loop()
        processor = VideoProcessor()
        
        job_manager.update_job(
            job_id,
            progress=30,
            message="Cropping to center square...",
        )
        
        # Process video (runs in thread pool)
        await loop.run_in_executor(
            None,
            processor.crop_and_zoom_to_square,
            input_path,
            output_path,
            output_size,
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
        size_info = f"{output_size}x{output_size}" if output_size else "original size"
        job_manager.update_job(
            job_id,
            status=JobStatus.COMPLETED,
            progress=100,
            message=f"Crop and zoom completed ({size_info})",
            output_path=Path(output_path),
        )
    
    except Exception as e:
        error_msg = str(e)
        job_manager.update_job(
            job_id,
            status=JobStatus.FAILED,
            error=error_msg,
            message=f"Crop and zoom failed: {error_msg}",
        )
    
    finally:
        # Clean up input file after processing
        try:
            if Path(input_path).exists():
                Path(input_path).unlink()
        except Exception:
            pass



@router.post("/videos/reencode")
async def reencode_video(
    background_tasks: BackgroundTasks,
    request: Request,
    codec: Optional[str] = Form("libx264"),
    bitrate: Optional[str] = Form(None),
    fps: Optional[float] = Form(None),
):
    """
    Upload a video and re-encode it with specified settings.
    
    Accepts a file upload with any field name (e.g., 'video', 'file', 'upload', etc.).
    The file must be sent as multipart/form-data.
    
    Parameters:
    - codec: Video codec to use (default: "libx264")
    - bitrate: Target bitrate in kbps format (e.g., "5000k") - optional
    - fps: Target FPS - optional, uses original if not specified
    
    Returns a job_id immediately. Use GET /api/v1/jobs/{job_id} to poll for status.
    When completed, download the video via GET /api/v1/videos/{job_id}/download
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
    
    # Save uploaded file
    upload_dir = project_root / "temp_videos" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    input_filename = video_file.filename or "video"
    input_path = upload_dir / f"reencode_{timestamp}_{input_filename}"
    
    try:
        # Save uploaded video
        with open(input_path, "wb") as f:
            content = await video_file.read()
            f.write(content)
        
        # Create output path
        output_dir = project_root / "temp_videos" / "output" / "reencode"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_filename = f"reencoded_{codec}_{timestamp}_{Path(input_filename).stem}.mp4"
        output_path = output_dir / output_filename
        
        # Create job
        job_id = job_manager.create_job(
            job_type="reencode",
            parameters={
                "input_path": str(input_path),
                "output_path": str(output_path),
                "original_filename": input_filename,
                "codec": codec,
                "bitrate": bitrate,
                "fps": fps,
            },
            output_path=output_path,
        )
        
        # Start background processing
        background_tasks.add_task(
            process_reencode,
            job_id=job_id,
            input_path=str(input_path),
            output_path=str(output_path),
            codec=codec,
            bitrate=bitrate,
            fps=fps,
            job_manager=job_manager,
        )
        
        # Return job_id immediately
        return {
            "job_id": job_id,
            "status": "pending",
            "message": "Video upload successful. Re-encoding started.",
            "status_url": f"/api/v1/jobs/{job_id}",
            "download_url": f"/api/v1/videos/{job_id}/download",
            "codec": codec,
            "bitrate": bitrate,
            "fps": fps,
        }
    
    except Exception as e:
        # Clean up on error
        if input_path.exists():
            input_path.unlink()
        raise HTTPException(status_code=500, detail=f"Error processing video: {str(e)}")


async def process_reencode(
    job_id: str,
    input_path: str,
    output_path: str,
    codec: str,
    bitrate: Optional[str],
    fps: Optional[float],
    job_manager: JobManager,
):
    """Background task to re-encode video."""
    try:
        job_manager.update_job(
            job_id,
            status=JobStatus.PROCESSING,
            progress=10,
            message="Loading video file...",
        )
        
        # Run re-encoding in executor to avoid blocking
        loop = asyncio.get_event_loop()
        processor = VideoProcessor()
        
        job_manager.update_job(
            job_id,
            progress=30,
            message=f"Re-encoding video with codec {codec}...",
        )
        
        # Process video (runs in thread pool)
        await loop.run_in_executor(
            None,
            processor.reencode_video,
            input_path,
            output_path,
            codec,
            bitrate,
            fps,
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
            message=f"Re-encoding completed (codec: {codec})",
            output_path=Path(output_path),
        )
    
    except Exception as e:
        error_msg = str(e)
        job_manager.update_job(
            job_id,
            status=JobStatus.FAILED,
            error=error_msg,
            message=f"Re-encoding failed: {error_msg}",
        )
    
    finally:
        # Clean up input file after processing
        try:
            if Path(input_path).exists():
                Path(input_path).unlink()
        except Exception:
            pass


@router.post("/videos/merge-audio-video")
async def merge_audio_and_video(
    background_tasks: BackgroundTasks,
    request: Request,
):
    """
    Upload a video file and an audio file, merge them together.
    
    The longer of the two will be clipped to match the shorter duration.
    
    Accepts two file uploads with any field names (e.g., 'video', 'audio', 'file1', 'file2', etc.).
    The files must be sent as multipart/form-data.
    
    Returns a job_id immediately. Use GET /api/v1/jobs/{job_id} to poll for status.
    When completed, download the video via GET /api/v1/videos/{job_id}/download
    """
    job_manager: JobManager = get_job_manager(request)
    
    # Parse form data to get the uploaded files
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
                "help": "In Postman: 1) Select 'Body' tab, 2) Choose 'form-data', 3) Add two keys with type 'File' - one for video and one for audio"
            }
        )
    
    # Find video and audio files in the form data
    video_file = None
    audio_file = None
    available_fields = []
    field_types = {}
    
    video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv'}
    audio_extensions = {'.mp3', '.wav', '.aac', '.m4a', '.ogg', '.flac', '.wma'}
    
    for key, value in form.items():
        available_fields.append(key)
        field_types[key] = type(value).__name__
        
        is_upload_file = (
            isinstance(value, UploadFile) or 
            type(value).__name__ == "UploadFile" or
            (hasattr(value, 'filename') and hasattr(value, 'read') and hasattr(value, 'file'))
        )
        
        if is_upload_file:
            filename = getattr(value, 'filename', '')
            ext = Path(filename).suffix.lower()
            
            # Classify as video or audio based on extension
            if ext in video_extensions and not video_file:
                video_file = value
            elif ext in audio_extensions and not audio_file:
                audio_file = value
    
    # If we couldn't determine by extension, use first two files
    if not video_file or not audio_file:
        files = []
        for key, value in form.items():
            is_upload_file = (
                isinstance(value, UploadFile) or 
                type(value).__name__ == "UploadFile" or
                (hasattr(value, 'filename') and hasattr(value, 'read') and hasattr(value, 'file'))
            )
            if is_upload_file:
                files.append(value)
        
        if len(files) < 2:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Need both video and audio files",
                    "found_fields": available_fields,
                    "field_types": field_types,
                    "help": "Upload two files: one video file (mp4, avi, mov, etc.) and one audio file (mp3, wav, aac, etc.)"
                }
            )
        
        # First file as video, second as audio (or vice versa)
        if not video_file:
            video_file = files[0]
        if not audio_file:
            audio_file = files[1] if len(files) > 1 else None
    
    if not video_file or not audio_file:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Both video and audio files are required",
                "found_fields": available_fields,
                "field_types": field_types,
                "help": "Upload two files: one video file and one audio file"
            }
        )
    
    # Save uploaded files
    upload_dir = project_root / "temp_videos" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    video_filename = video_file.filename or "video"
    audio_filename = audio_file.filename or "audio"
    
    video_path = upload_dir / f"merge_video_{timestamp}_{video_filename}"
    audio_path = upload_dir / f"merge_audio_{timestamp}_{audio_filename}"
    
    try:
        # Save uploaded video
        with open(video_path, "wb") as f:
            content = await video_file.read()
            f.write(content)
        
        # Save uploaded audio
        with open(audio_path, "wb") as f:
            content = await audio_file.read()
            f.write(content)
        
        # Create output path
        output_dir = project_root / "temp_videos" / "output" / "merge_audio_video"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_filename = f"merged_{timestamp}_{Path(video_filename).stem}.mp4"
        output_path = output_dir / output_filename
        
        # Create job
        job_id = job_manager.create_job(
            job_type="merge_audio_video",
            parameters={
                "video_path": str(video_path),
                "audio_path": str(audio_path),
                "output_path": str(output_path),
                "video_filename": video_filename,
                "audio_filename": audio_filename,
            },
            output_path=output_path,
        )
        
        # Start background processing
        background_tasks.add_task(
            process_merge_audio_video,
            job_id=job_id,
            video_path=str(video_path),
            audio_path=str(audio_path),
            output_path=str(output_path),
            job_manager=job_manager,
        )
        
        # Return job_id immediately
        return {
            "job_id": job_id,
            "status": "pending",
            "message": "Files uploaded successfully. Merging started.",
            "status_url": f"/api/v1/jobs/{job_id}",
            "download_url": f"/api/v1/videos/{job_id}/download",
        }
    
    except Exception as e:
        # Clean up on error
        if video_path.exists():
            video_path.unlink()
        if audio_path.exists():
            audio_path.unlink()
        raise HTTPException(status_code=500, detail=f"Error processing files: {str(e)}")


async def process_merge_audio_video(
    job_id: str,
    video_path: str,
    audio_path: str,
    output_path: str,
    job_manager: JobManager,
):
    """Background task to merge audio and video."""
    try:
        job_manager.update_job(
            job_id,
            status=JobStatus.PROCESSING,
            progress=10,
            message="Loading video and audio files...",
        )
        
        # Run merging in executor to avoid blocking
        loop = asyncio.get_event_loop()
        processor = VideoProcessor()
        
        job_manager.update_job(
            job_id,
            progress=30,
            message="Merging audio with video...",
        )
        
        # Process files (runs in thread pool)
        await loop.run_in_executor(
            None,
            processor.merge_audio_and_video,
            video_path,
            audio_path,
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
            message="Audio and video merged successfully",
            output_path=Path(output_path),
        )
    
    except Exception as e:
        error_msg = str(e)
        job_manager.update_job(
            job_id,
            status=JobStatus.FAILED,
            error=error_msg,
            message=f"Merge failed: {error_msg}",
        )
    
    finally:
        # Clean up input files after processing
        try:
            if Path(video_path).exists():
                Path(video_path).unlink()
            if Path(audio_path).exists():
                Path(audio_path).unlink()
        except Exception:
            pass



@router.post("/videos/process")
async def process_video_comprehensive(
    background_tasks: BackgroundTasks,
    request: Request,
    remove_audio: Optional[bool] = Form(False),
    merge_audio: Optional[bool] = Form(False),
    color_grading: Optional[bool] = Form(False),
    color_preset: Optional[str] = Form("cinematic"),
    color_brightness: Optional[float] = Form(0.0),
    color_contrast: Optional[float] = Form(1.0),
    color_saturation: Optional[float] = Form(1.0),
    crop_zoom: Optional[bool] = Form(False),
    crop_output_size: Optional[int] = Form(1080),
    reencode: Optional[bool] = Form(False),
    codec: Optional[str] = Form("libx264"),
    bitrate: Optional[str] = Form(None),
    fps: Optional[float] = Form(None),
):
    """
    Comprehensive video processing endpoint - apply multiple transformations in one request.
    
    Upload a video file (and optionally an audio file) and apply multiple processing operations
    based on boolean flags. All operations are applied in sequence:
    1. Merge audio (if merge_audio=True and audio file provided)
    2. Remove audio (if remove_audio=True, overrides merge_audio)
    3. Color grading (if color_grading=True)
    4. Crop and zoom to square (if crop_zoom=True)
    5. Re-encode (if reencode=True)
    
    Accepts file uploads with any field names. The files must be sent as multipart/form-data.
    
    Boolean Parameters (all default to False):
    - remove_audio: Remove audio track from video
    - merge_audio: Merge audio file with video (requires audio file upload)
    - color_grading: Apply color grading
    - crop_zoom: Crop to center 1:1 square aspect ratio
    - reencode: Re-encode video with specified codec/bitrate/fps
    
    Color Grading Parameters (if color_grading=True):
    - color_preset: Preset name (cinematic, warm, cool, vintage, vivid, bw, natural, random)
    - color_brightness: Brightness adjustment (-1.0 to 1.0)
    - color_contrast: Contrast adjustment (0.0 to 2.0)
    - color_saturation: Saturation adjustment (0.0 to 2.0)
    
    Crop Parameters (if crop_zoom=True):
    - crop_output_size: Output square size in pixels (default: 1080)
    
    Re-encode Parameters (if reencode=True):
    - codec: Video codec (default: "libx264")
    - bitrate: Target bitrate in kbps format (e.g., "5000k")
    - fps: Target FPS
    
    Returns a job_id immediately. Use GET /api/v1/jobs/{job_id} to poll for status.
    When completed, download the video via GET /api/v1/videos/{job_id}/download
    """
    job_manager: JobManager = get_job_manager(request)
    
    # Parse form data to get uploaded files
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
                "help": "In Postman: 1) Select 'Body' tab, 2) Choose 'form-data', 3) Add file keys and boolean parameters"
            }
        )
    
    # Find video and audio files
    video_file = None
    audio_file = None
    video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv'}
    audio_extensions = {'.mp3', '.wav', '.aac', '.m4a', '.ogg', '.flac', '.wma'}
    
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
            filename = getattr(value, 'filename', '')
            ext = Path(filename).suffix.lower()
            
            if ext in video_extensions and not video_file:
                video_file = value
            elif ext in audio_extensions and not audio_file:
                audio_file = value
    
    # If we couldn't determine by extension, use first file as video, second as audio
    if not video_file:
        files = []
        for key, value in form.items():
            is_upload_file = (
                isinstance(value, UploadFile) or 
                type(value).__name__ == "UploadFile" or
                (hasattr(value, 'filename') and hasattr(value, 'read') and hasattr(value, 'file'))
            )
            if is_upload_file:
                files.append(value)
        
        if len(files) > 0:
            video_file = files[0]
        if len(files) > 1:
            audio_file = files[1]
    
    if not video_file:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "No video file uploaded",
                "found_fields": available_fields,
                "field_types": field_types,
                "help": "Upload at least one video file"
            }
        )
    
    # Validate merge_audio requires audio file
    if merge_audio and not audio_file:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "merge_audio=True requires an audio file to be uploaded",
                "help": "Upload both a video file and an audio file when merge_audio=True"
            }
        )
    
    # Save uploaded files
    upload_dir = project_root / "temp_videos" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    video_filename = video_file.filename or "video"
    input_video_path = upload_dir / f"process_{timestamp}_{video_filename}"
    
    input_audio_path = None
    if audio_file:
        audio_filename = audio_file.filename or "audio"
        input_audio_path = upload_dir / f"process_audio_{timestamp}_{audio_filename}"
    
    try:
        # Save uploaded video
        with open(input_video_path, "wb") as f:
            content = await video_file.read()
            f.write(content)
        
        # Save uploaded audio if provided
        if audio_file and input_audio_path:
            with open(input_audio_path, "wb") as f:
                content = await audio_file.read()
                f.write(content)
        
        # Create output path
        output_dir = project_root / "temp_videos" / "output" / "comprehensive"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Build output filename with operations included
        operations = []
        if remove_audio:
            operations.append("no_audio")
        if merge_audio:
            operations.append("merged")
        if color_grading:
            operations.append(f"graded_{color_preset}")
        if crop_zoom:
            operations.append(f"square_{crop_output_size}")
        if reencode:
            operations.append(f"reencoded_{codec}")
        
        ops_suffix = "_".join(operations) if operations else "processed"
        output_filename = f"{ops_suffix}_{timestamp}_{Path(video_filename).stem}.mp4"
        output_path = output_dir / output_filename
        
        # Create job
        job_id = job_manager.create_job(
            job_type="comprehensive",
            parameters={
                "video_path": str(input_video_path),
                "audio_path": str(input_audio_path) if input_audio_path else None,
                "output_path": str(output_path),
                "video_filename": video_filename,
                "audio_filename": audio_file.filename if audio_file else None,
                "remove_audio": remove_audio,
                "merge_audio": merge_audio,
                "color_grading": color_grading,
                "color_preset": color_preset,
                "color_brightness": color_brightness,
                "color_contrast": color_contrast,
                "color_saturation": color_saturation,
                "crop_zoom": crop_zoom,
                "crop_output_size": crop_output_size,
                "reencode": reencode,
                "codec": codec,
                "bitrate": bitrate,
                "fps": fps,
            },
            output_path=output_path,
        )
        
        # Start background processing
        background_tasks.add_task(
            process_comprehensive,
            job_id=job_id,
            video_path=str(input_video_path),
            audio_path=str(input_audio_path) if input_audio_path else None,
            output_path=str(output_path),
            remove_audio=remove_audio,
            merge_audio=merge_audio,
            color_grading=color_grading,
            color_preset=color_preset,
            color_brightness=color_brightness,
            color_contrast=color_contrast,
            color_saturation=color_saturation,
            crop_zoom=crop_zoom,
            crop_output_size=crop_output_size,
            reencode=reencode,
            codec=codec,
            bitrate=bitrate,
            fps=fps,
            job_manager=job_manager,
        )
        
        # Build operations list for response
        applied_operations = []
        if remove_audio:
            applied_operations.append("remove_audio")
        if merge_audio:
            applied_operations.append("merge_audio")
        if color_grading:
            applied_operations.append(f"color_grading({color_preset})")
        if crop_zoom:
            applied_operations.append(f"crop_zoom({crop_output_size}x{crop_output_size})")
        if reencode:
            applied_operations.append(f"reencode({codec})")
        
        return {
            "job_id": job_id,
            "status": "pending",
            "message": "Video upload successful. Processing started.",
            "status_url": f"/api/v1/jobs/{job_id}",
            "download_url": f"/api/v1/videos/{job_id}/download",
            "applied_operations": applied_operations if applied_operations else ["none"],
        }
    
    except Exception as e:
        # Clean up on error
        if input_video_path.exists():
            input_video_path.unlink()
        if input_audio_path and input_audio_path.exists():
            input_audio_path.unlink()
        raise HTTPException(status_code=500, detail=f"Error processing video: {str(e)}")


async def process_comprehensive(
    job_id: str,
    video_path: str,
    audio_path: Optional[str],
    output_path: str,
    remove_audio: bool,
    merge_audio: bool,
    color_grading: bool,
    color_preset: str,
    color_brightness: float,
    color_contrast: float,
    color_saturation: float,
    crop_zoom: bool,
    crop_output_size: int,
    reencode: bool,
    codec: str,
    bitrate: Optional[str],
    fps: Optional[float],
    job_manager: JobManager,
):
    """Background task for comprehensive video processing."""
    try:
        job_manager.update_job(
            job_id,
            status=JobStatus.PROCESSING,
            progress=5,
            message="Loading video file...",
        )
        
        # Run processing in executor to avoid blocking
        loop = asyncio.get_event_loop()
        processor = VideoProcessor()
        
        # Build operations list for progress messages
        operations = []
        if remove_audio:
            operations.append("removing audio")
        if merge_audio:
            operations.append("merging audio")
        if color_grading:
            operations.append(f"color grading ({color_preset})")
        if crop_zoom:
            operations.append(f"cropping to square ({crop_output_size}x{crop_output_size})")
        if reencode:
            operations.append(f"re-encoding ({codec})")
        
        progress_steps = len(operations) if operations else 1
        step_progress = 85 / progress_steps if progress_steps > 0 else 85
        current_progress = 10
        
        job_manager.update_job(
            job_id,
            progress=current_progress,
            message=f"Processing video: {', '.join(operations) if operations else 'no operations'}",
        )
        
        # Process video (runs in thread pool)
        await loop.run_in_executor(
            None,
            processor.process_video_comprehensive,
            video_path,
            output_path,
            audio_path,
            remove_audio,
            merge_audio,
            color_grading,
            color_preset,
            color_brightness,
            color_contrast,
            color_saturation,
            crop_zoom,
            crop_output_size,
            reencode,
            codec,
            bitrate,
            fps,
        )
        
        job_manager.update_job(
            job_id,
            progress=95,
            message="Finalizing video...",
        )
        
        # Verify output file exists
        if not Path(output_path).exists():
            raise Exception("Output file was not created")
        
        # Update job to completed
        operations_summary = ", ".join(operations) if operations else "no transformations"
        job_manager.update_job(
            job_id,
            status=JobStatus.COMPLETED,
            progress=100,
            message=f"Video processing completed ({operations_summary})",
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
        # Clean up input files after processing
        try:
            if Path(video_path).exists():
                Path(video_path).unlink()
            if audio_path and Path(audio_path).exists():
                Path(audio_path).unlink()
        except Exception:
            pass
