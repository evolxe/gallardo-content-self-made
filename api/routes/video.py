"""
Video processing endpoints - simple audio removal service.
"""

import os
import sys
import asyncio
import mimetypes
from pathlib import Path
from typing import Optional, Tuple
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


async def extract_cookies_file(form: dict, upload_dir: Path) -> Optional[str]:
    """
    Extract cookies file from form data (as file upload or from form field).
    
    Args:
        form: Form data dictionary
        upload_dir: Directory to save uploaded cookies file
        
    Returns:
        Path to saved cookies file, or None if no cookies provided
        
    Raises:
        HTTPException: If cookies file is invalid or can't be saved
    """
    cookies_file = None
    cookies_file_upload = None
    
    # First, check for cookies file upload (look for any file with 'cookie' in the field name)
    for key, value in form.items():
        key_lower = key.lower()
        if 'cookie' in key_lower:
            is_upload_file = (
                isinstance(value, UploadFile) or 
                type(value).__name__ == "UploadFile" or
                (hasattr(value, 'filename') and hasattr(value, 'read') and hasattr(value, 'file'))
            )
            if is_upload_file:
                cookies_file_upload = value
                break
    
    if cookies_file_upload:
        # Save uploaded cookies file
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        cookies_filename = cookies_file_upload.filename or "cookies.txt"
        cookies_path = upload_dir / f"cookies_{timestamp}_{cookies_filename}"
        
        try:
            content = await cookies_file_upload.read()
            
            # Validate it's a text file (check for Netscape cookie format header)
            content_str = content.decode('utf-8', errors='ignore')
            if not (content_str.strip().startswith('# HTTP Cookie File') or 
                    content_str.strip().startswith('# Netscape HTTP Cookie File')):
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "Invalid cookies file format",
                        "help": "Cookies file must be in Netscape format. First line should be '# HTTP Cookie File' or '# Netscape HTTP Cookie File'"
                    }
                )
            
            with open(cookies_path, "wb") as f:
                f.write(content)
            
            cookies_file = str(cookies_path)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": f"Failed to save cookies file: {str(e)}",
                    "help": "Make sure the cookies file is valid and in Netscape format"
                }
            )
    
    return cookies_file


async def get_video_input(
    form: dict,
    video_url: Optional[str] = None,
    upload_dir: Optional[Path] = None,
    prefix: str = "video",
    cookies_file: Optional[str] = None,
) -> Tuple[Path, str]:
    """
    Helper function to get video input from either URL or file upload.
    
    Args:
        form: Form data dictionary
        video_url: Optional URL to download video from
        upload_dir: Directory to save uploaded/downloaded videos
        prefix: Prefix for the saved filename
        
    Returns:
        Tuple of (local_file_path, original_filename)
        
    Raises:
        HTTPException: If neither URL nor file is provided, or both are provided
    """
    if upload_dir is None:
        upload_dir = project_root / "temp_videos" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    
    # Check if both URL and file are provided
    video_file = None
    for key, value in form.items():
        # Skip cookie files - they're not video files
        key_lower = key.lower()
        if 'cookie' in key_lower:
            continue
        
        is_upload_file = (
            isinstance(value, UploadFile) or 
            type(value).__name__ == "UploadFile" or
            (hasattr(value, 'filename') and hasattr(value, 'read') and hasattr(value, 'file'))
        )
        if is_upload_file:
            video_file = value
            break
    
    if video_url and video_file:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Both video_url and file upload provided",
                "help": "Provide either a video_url parameter OR upload a file, not both"
            }
        )
    
    if video_url:
        # Download from URL using yt-dlp
        try:
            # Create output directory for downloaded video
            download_dir = upload_dir / "url_downloads"
            download_dir.mkdir(parents=True, exist_ok=True)
            
            # Initialize yt-dlp service
            ytdlp_service = YTDLPService(output_dir=download_dir)
            
            # Download video synchronously (we're in an async function, but download_video is sync)
            # We'll use asyncio to run it in executor
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                ytdlp_service.download_video,
                video_url,
                None,  # output_filename - let it use default
                "best",  # quality
                "mp4",  # format_type
                False,  # audio_only
                cookies_file,  # cookies_file
            )
            
            downloaded_path = Path(result["output_path"])
            if not downloaded_path.exists():
                raise Exception("Downloaded file not found")
            
            # Generate a standardized filename with prefix
            original_filename = result.get("filename", "downloaded_video")
            file_extension = downloaded_path.suffix
            new_filename = f"{prefix}_{timestamp}_{Path(original_filename).stem}{file_extension}"
            input_path = upload_dir / new_filename
            
            # Move/copy the downloaded file to uploads directory with standardized name
            import shutil
            shutil.move(str(downloaded_path), str(input_path))
            
            return input_path, original_filename
            
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": f"Failed to download video from URL: {str(e)}",
                    "url": video_url,
                }
            )
    
    elif video_file:
        # Handle file upload
        input_filename = video_file.filename or "video"
        # Ensure filename has an extension - try to detect from content-type
        if not Path(input_filename).suffix:
            # Try to get extension from content-type header
            content_type = getattr(video_file, 'content_type', None)
            if content_type:
                ext = mimetypes.guess_extension(content_type.split(';')[0].strip())
                if ext:
                    input_filename = f"{input_filename}{ext}"
            # If no extension can be determined, leave it as-is
            # FFmpeg/MoviePy can auto-detect format from file headers
        
        input_path = upload_dir / f"{prefix}_{timestamp}_{input_filename}"
        
        # Save uploaded video
        content = await video_file.read()
        with open(input_path, "wb") as f:
            f.write(content)
        
        return input_path, input_filename
    
    else:
        # Neither URL nor file provided
        available_fields = list(form.keys())
        raise HTTPException(
            status_code=400,
            detail={
                "error": "No video input provided",
                "help": "Either provide a video_url parameter OR upload a video file",
                "available_fields": available_fields,
            }
        )


@router.post("/videos/remove-audio")
async def remove_audio_from_video(
    background_tasks: BackgroundTasks,
    request: Request,
    video_url: Optional[str] = Form(None),
    cookies_file: Optional[UploadFile] = File(None),
):
    """
    Upload a video (or provide URL) and remove its audio track.
    
    Either:
    - Upload a file with any field name (e.g., 'video', 'file', 'upload', etc.)
    - OR provide a video_url parameter with a URL to download from (YouTube, Instagram, etc.)
    
    The file/request must be sent as multipart/form-data.
    
    Returns a job_id immediately. Use GET /api/v1/jobs/{job_id} to poll for status.
    """
    job_manager: JobManager = get_job_manager(request)
    input_path = None  # Initialize to avoid UnboundLocalError
    
    # Parse form data
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
                "help": "In Postman: 1) Select 'Body' tab, 2) Choose 'form-data' (not raw/json), 3) Add key with type 'File' OR add video_url parameter, 4) Make sure no Content-Type header is manually set"
            }
        )
    
    # Extract cookies file if provided
    upload_dir = project_root / "temp_videos" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    cookies_path = None
    try:
        cookies_path = await extract_cookies_file(form, upload_dir)
    except HTTPException:
        raise
    except Exception:
        pass
    
    try:
        # Get video input (from URL or file upload)
        input_path, input_filename = await get_video_input(
            form=form,
            video_url=video_url,
            prefix="input",
            cookies_file=cookies_path,
        )
        
        # Create output path - organized by use case
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
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
                "video_url": video_url if video_url else None,
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
    
    except HTTPException:
        # Re-raise HTTPExceptions (they're already properly formatted)
        raise
    except Exception as e:
        # Clean up on error
        if input_path is not None and input_path.exists():
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
    video_url: Optional[str] = Form(None),
    cookies_file: Optional[UploadFile] = File(None),
):
    """
    Upload a video (or provide URL) and detect scene cuts.
    
    Either:
    - Upload a file with any field name (e.g., 'video', 'file', 'upload', etc.)
    - OR provide a video_url parameter with a URL to download from (YouTube, Instagram, etc.)
    
    Returns a job_id immediately. Use GET /api/v1/jobs/{job_id} to poll for status.
    When completed, the job result will contain scene information.
    """
    job_manager: JobManager = get_job_manager(request)
    input_path = None  # Initialize to avoid UnboundLocalError
    
    # Parse form data
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
                "help": "In Postman: 1) Select 'Body' tab, 2) Choose 'form-data' (not raw/json), 3) Add key with type 'File' OR add video_url parameter"
            }
        )
    
    # Extract cookies file if provided
    upload_dir = project_root / "temp_videos" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    cookies_path = None
    try:
        cookies_path = await extract_cookies_file(form, upload_dir)
    except HTTPException:
        raise
    except Exception:
        pass
    
    try:
        # Get video input (from URL or file upload)
        input_path, input_filename = await get_video_input(
            form=form,
            video_url=video_url,
            prefix="scene_detection",
            cookies_file=cookies_path,
        )
        
        # Create output path for scene data (JSON file)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
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
                "video_url": video_url if video_url else None,
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
    
    except HTTPException:
        # Re-raise HTTPExceptions (they're already properly formatted)
        raise
    except Exception as e:
        # Clean up on error
        if input_path is not None and input_path.exists():
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


@router.post("/videos/download-audio-from-url")
async def download_audio_from_url(
    background_tasks: BackgroundTasks,
    request: Request,
    url: str = Form(...),
    output_filename: Optional[str] = Form(None),
):
    """
    Download audio only from a video URL using yt-dlp.
    
    Downloads audio track from YouTube, Instagram, Vimeo, and other platforms supported by yt-dlp.
    The audio is extracted and saved as MP3.
    
    Parameters (form-data):
    - url: URL of the video to extract audio from (required)
    - output_filename: Optional custom filename (without extension)
    - cookies_file: Optional cookies file upload (Netscape format) for authentication
    
    Returns a job_id immediately. Use GET /api/v1/jobs/{job_id} to poll for status.
    When completed, download the audio via GET /api/v1/videos/{job_id}/download
    """
    job_manager: JobManager = get_job_manager(request)
    
    # Parse form data to extract cookies file if provided
    try:
        form = await request.form()
    except Exception:
        form = {}
    
    # Validate URL
    if not url or not url.strip():
        raise HTTPException(status_code=400, detail="URL parameter is required")
    
    # Extract cookies file if provided
    cookies_file = None
    upload_dir = project_root / "temp_videos" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    try:
        cookies_file = await extract_cookies_file(form, upload_dir)
    except HTTPException:
        raise
    except Exception as e:
        # If cookies extraction fails, continue without cookies
        pass
    
    # Create job
    job_id = job_manager.create_job(
        job_type="ytdlp_audio_download",
        parameters={
            "url": url,
            "audio_only": True,
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
        output_path = output_dir / f"{safe_filename}.mp3"
    else:
        output_path = output_dir / f"audio_download_{timestamp}.mp3"
    
    # Start background processing
    background_tasks.add_task(
        process_ytdlp_download,
        job_id=job_id,
        url=url,
        output_path=str(output_path),
        quality="best",  # Not used for audio, but required parameter
        format_type="mp3",
        audio_only=True,  # This is the key parameter
        output_filename=output_filename,
        cookies_file=cookies_file,
        job_manager=job_manager,
    )
    
    # Return job_id immediately
    return {
        "job_id": job_id,
        "status": "pending",
        "message": "Audio download started",
        "status_url": f"/api/v1/jobs/{job_id}",
        "download_url": f"/api/v1/videos/{job_id}/download",
    }


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
    - cookies_file: Optional cookies file upload (Netscape format) for authentication
    
    Returns a job_id immediately. Use GET /api/v1/jobs/{job_id} to poll for status.
    When completed, download the video via GET /api/v1/videos/{job_id}/download
    """
    job_manager: JobManager = get_job_manager(request)
    
    # Parse form data to extract cookies file if provided
    try:
        form = await request.form()
    except Exception:
        form = {}
    
    # Validate URL
    if not url or not url.strip():
        raise HTTPException(status_code=400, detail="URL parameter is required")
    
    # Extract cookies file if provided
    cookies_file = None
    upload_dir = project_root / "temp_videos" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    try:
        cookies_file = await extract_cookies_file(form, upload_dir)
    except HTTPException:
        raise
    except Exception as e:
        # If cookies extraction fails, continue without cookies
        pass
    
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
        cookies_file=cookies_file,
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
    cookies_file: Optional[str],
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
            cookies_file,
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
    video_url: Optional[str] = Form(None),
    cookies_file: Optional[UploadFile] = File(None),
):
    """
    Upload a video (or provide URL) and apply color grading.
    
    Either:
    - Upload a file with any field name (e.g., 'video', 'file', 'upload', etc.)
    - OR provide a video_url parameter with a URL to download from (YouTube, Instagram, etc.)
    
    The file/request must be sent as multipart/form-data.
    
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
    input_path = None  # Initialize to avoid UnboundLocalError
    
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
    
    # Parse form data
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
                "help": "In Postman: 1) Select 'Body' tab, 2) Choose 'form-data' (not raw/json), 3) Add key with type 'File' OR add video_url parameter"
            }
        )
    
    # Extract cookies file if provided
    upload_dir = project_root / "temp_videos" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    cookies_path = None
    try:
        cookies_path = await extract_cookies_file(form, upload_dir)
    except HTTPException:
        raise
    except Exception:
        pass
    
    try:
        # Get video input (from URL or file upload)
        input_path, input_filename = await get_video_input(
            form=form,
            video_url=video_url,
            prefix="color_grade",
            cookies_file=cookies_path,
        )
        
        # Create output path
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
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
                "video_url": video_url if video_url else None,
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
    
    except HTTPException:
        # Re-raise HTTPExceptions (they're already properly formatted)
        raise
    except Exception as e:
        # Clean up on error
        if input_path is not None and input_path.exists():
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
    aspect_ratio: Optional[str] = Form(None),
    background_color: Optional[str] = Form(None),
    video_url: Optional[str] = Form(None),
    cookies_file: Optional[UploadFile] = File(None),
):
    """
    Upload a video (or provide URL) and crop it to any aspect ratio, outputting as 9:16.
    
    Either:
    - Upload a file with any field name (e.g., 'video', 'file', 'upload', etc.)
    - OR provide a video_url parameter with a URL to download from (YouTube, Instagram, etc.)
    
    The file/request must be sent as multipart/form-data.
    
    Parameters:
    - aspect_ratio: Desired crop aspect ratio in format "W:H" (e.g., "16:9", "1:1", "4:3", "21:9")
                    Default: "1:1" (square) if not provided
    - background_color: Background color for padding when aspect ratio is not 9:16
                        Can be hex format (e.g., "#000000" for black, "#FFFFFF" for white)
                        or named colors (black, white, red, green, blue, yellow, cyan, magenta, gray)
                        Default: Random color if not provided
    
    Note: Output is ALWAYS 9:16 (1080x1920). If the cropped aspect ratio is not 9:16,
    the video will be scaled to fit and padded with the background color.
    
    Returns a job_id immediately. Use GET /api/v1/jobs/{job_id} to poll for status.
    When completed, download the video via GET /api/v1/videos/{job_id}/download
    """
    job_manager: JobManager = get_job_manager(request)
    input_path = None  # Initialize to avoid UnboundLocalError
    
    # Default aspect_ratio to 1:1 if not provided
    if not aspect_ratio:
        aspect_ratio = "1:1"
    
    # Validate aspect_ratio format
    try:
        parts = aspect_ratio.split(":")
        if len(parts) != 2:
            raise ValueError("Aspect ratio must be in format 'W:H'")
        float(parts[0])
        float(parts[1])
    except (ValueError, IndexError):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid aspect_ratio format '{aspect_ratio}'. Use format 'W:H' (e.g., '16:9', '1:1')"
        )
    
    # Pick random background color if not provided
    if not background_color:
        import random
        colors = [
            "#000000",  # black
            "#FFFFFF",  # white
            "#FF0000",  # red
            "#00FF00",  # green
            "#0000FF",  # blue
            "#FFFF00",  # yellow
            "#00FFFF",  # cyan
            "#FF00FF",  # magenta
            "#808080",  # gray
            "#FFA500",  # orange
            "#800080",  # purple
            "#FFC0CB",  # pink
        ]
        background_color = random.choice(colors)
    
    # Parse form data
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
                "help": "In Postman: 1) Select 'Body' tab, 2) Choose 'form-data' (not raw/json), 3) Add key with type 'File' OR add video_url parameter"
            }
        )
    
    # Extract cookies file if provided
    upload_dir = project_root / "temp_videos" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    cookies_path = None
    try:
        cookies_path = await extract_cookies_file(form, upload_dir)
    except HTTPException:
        raise
    except Exception:
        pass
    
    try:
        # Get video input (from URL or file upload)
        input_path, input_filename = await get_video_input(
            form=form,
            video_url=video_url,
            prefix="crop_zoom",
            cookies_file=cookies_path,
        )
        
        # Create output path
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_dir = project_root / "temp_videos" / "output" / "crop_zoom"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Sanitize aspect_ratio for filename
        aspect_safe = aspect_ratio.replace(":", "_")
        output_filename = f"crop_{aspect_safe}_9x16_{timestamp}_{Path(input_filename).stem}.mp4"
        output_path = output_dir / output_filename
        
        # Create job
        job_id = job_manager.create_job(
            job_type="crop_zoom",
            parameters={
                "input_path": str(input_path),
                "output_path": str(output_path),
                "original_filename": input_filename,
                "aspect_ratio": aspect_ratio,
                "background_color": background_color,
                "video_url": video_url if video_url else None,
            },
            output_path=output_path,
        )
        
        # Start background processing
        background_tasks.add_task(
            process_crop_and_zoom,
            job_id=job_id,
            input_path=str(input_path),
            output_path=str(output_path),
            aspect_ratio=aspect_ratio,
            background_color=background_color,
            job_manager=job_manager,
        )
        
        # Return job_id immediately
        return {
            "job_id": job_id,
            "status": "pending",
            "message": "Video upload successful. Crop and zoom started.",
            "status_url": f"/api/v1/jobs/{job_id}",
            "download_url": f"/api/v1/videos/{job_id}/download",
            "aspect_ratio": aspect_ratio,
            "background_color": background_color,
            "output_format": "9:16 (1080x1920)",
        }
    
    except HTTPException:
        # Re-raise HTTPExceptions (they're already properly formatted)
        raise
    except Exception as e:
        # Clean up on error
        if input_path is not None and input_path.exists():
            input_path.unlink()
        raise HTTPException(status_code=500, detail=f"Error processing video: {str(e)}")


async def process_crop_and_zoom(
    job_id: str,
    input_path: str,
    output_path: str,
    aspect_ratio: str,
    background_color: str,
    job_manager: JobManager,
):
    """Background task to crop video to aspect ratio and output as 9:16."""
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
            message=f"Processing video: cropping to {aspect_ratio}, scaling, and encoding to 9:16 (this may take several minutes)...",
        )
        
        # Process video (runs in thread pool)
        # Note: This is a long-running operation that can take several minutes
        # The write_videofile call is CPU-intensive and does not provide progress updates
        await loop.run_in_executor(
            None,
            processor.crop_to_aspect_ratio_and_pad_to_9_16,
            input_path,
            output_path,
            aspect_ratio,
            background_color,
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
            message=f"Crop completed (cropped to {aspect_ratio}, output as 9:16)",
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
    video_url: Optional[str] = Form(None),
    cookies_file: Optional[UploadFile] = File(None),
):
    """
    Upload a video (or provide URL) and re-encode it with specified settings.
    
    Either:
    - Upload a file with any field name (e.g., 'video', 'file', 'upload', etc.)
    - OR provide a video_url parameter with a URL to download from (YouTube, Instagram, etc.)
    
    The file/request must be sent as multipart/form-data.
    
    Parameters:
    - codec: Video codec to use (default: "libx264")
    - bitrate: Target bitrate in kbps format (e.g., "5000k") - optional
    - fps: Target FPS - optional, uses original if not specified
    
    Returns a job_id immediately. Use GET /api/v1/jobs/{job_id} to poll for status.
    When completed, download the video via GET /api/v1/videos/{job_id}/download
    """
    job_manager: JobManager = get_job_manager(request)
    
    # Parse form data
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
                "help": "In Postman: 1) Select 'Body' tab, 2) Choose 'form-data' (not raw/json), 3) Add key with type 'File' OR add video_url parameter"
            }
        )
    
    # Extract cookies file if provided
    upload_dir = project_root / "temp_videos" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    cookies_path = None
    try:
        cookies_path = await extract_cookies_file(form, upload_dir)
    except HTTPException:
        raise
    except Exception:
        pass
    
    input_path = None  # Initialize to avoid UnboundLocalError
    try:
        # Get video input (from URL or file upload)
        input_path, input_filename = await get_video_input(
            form=form,
            video_url=video_url,
            prefix="reencode",
            cookies_file=cookies_path,
        )
        
        # Create output path
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
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
                "video_url": video_url if video_url else None,
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
    video_url: Optional[str] = Form(None),
    audio_url: Optional[str] = Form(None),
):
    """
    Upload a video file (or provide URL) and an audio file (or provide URL), merge them together.
    
    The longer of the two will be clipped to match the shorter duration.
    
    Video input:
    - Upload a video file with any field name (e.g., 'video', 'file', etc.)
    - OR provide a video_url parameter with a URL to download from (YouTube, Instagram, etc.)
    
    Audio input:
    - Upload an audio file with any field name (e.g., 'audio', 'file', etc.)
    - OR provide an audio_url parameter with a URL to download audio from (YouTube, Instagram, etc.)
      The audio will be extracted using yt-dlp with audio-only mode.
    
    The files/request must be sent as multipart/form-data.
    
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
    
    # Extract URLs from form - ALWAYS check form dict first, then use parameter if form doesn't have it
    # This ensures we get the values even if Form() parameter extraction fails
    form_video_url = form.get("video_url")
    form_audio_url = form.get("audio_url")
    
    # Prioritize form dict values, fallback to parameter
    # Only use URL if it's a non-empty string (not empty string, None, or UploadFile)
    if form_video_url and not isinstance(form_video_url, UploadFile):
        video_url_str = str(form_video_url).strip()
        video_url = video_url_str if video_url_str else None
    elif video_url and isinstance(video_url, str):
        video_url_str = video_url.strip()
        video_url = video_url_str if video_url_str else None
    else:
        video_url = None
    
    if form_audio_url and not isinstance(form_audio_url, UploadFile):
        audio_url_str = str(form_audio_url).strip()
        audio_url = audio_url_str if audio_url_str else None
    elif audio_url and isinstance(audio_url, str):
        audio_url_str = audio_url.strip()
        audio_url = audio_url_str if audio_url_str else None
    else:
        audio_url = None
    
    # Extract cookies file if provided (universal for all downloads)
    upload_dir = project_root / "temp_videos" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    cookies_file = None
    
    try:
        cookies_file = await extract_cookies_file(form, upload_dir)
    except HTTPException:
        raise
    except Exception:
        pass
    
    # Generate timestamp once for use throughout the function
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    
    # Handle video input (from URL or file upload)
    video_path = None
    video_filename = None
    uploaded_video_file = None  # Track if we got video from file upload
    
    if video_url and video_url.strip():
        # Download video from URL
        try:
            video_path, video_filename = await get_video_input(
                form={},  # Empty form since we're using URL
                video_url=video_url,
                prefix="merge_video",
                cookies_file=cookies_file,
            )
                
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": f"Failed to download video from URL: {str(e)}",
                    "url": video_url,
                }
            )
    else:
        # Find video file in form data
        video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv'}
        
        for key, value in form.items():
            # Skip cookie files - they're not video files
            key_lower = key.lower()
            if 'cookie' in key_lower:
                continue
            
            is_upload_file = (
                isinstance(value, UploadFile) or 
                type(value).__name__ == "UploadFile" or
                (hasattr(value, 'filename') and hasattr(value, 'read') and hasattr(value, 'file'))
            )
            
            if is_upload_file:
                filename = getattr(value, 'filename', '')
                ext = Path(filename).suffix.lower()
                if ext in video_extensions:
                    uploaded_video_file = value
                    break
        
        if not uploaded_video_file:
            # Try first file as video if no extension match
            for key, value in form.items():
                # Skip cookie files - they're not video files
                key_lower = key.lower()
                if 'cookie' in key_lower:
                    continue
                
                is_upload_file = (
                    isinstance(value, UploadFile) or 
                    type(value).__name__ == "UploadFile" or
                    (hasattr(value, 'filename') and hasattr(value, 'read') and hasattr(value, 'file'))
                )
                if is_upload_file:
                    uploaded_video_file = value
                    break
        
        if uploaded_video_file:
            video_path, video_filename = await get_video_input(
                form={key: uploaded_video_file for key, value in form.items() if value == uploaded_video_file},
                video_url=None,
                prefix="merge_video"
            )
        
        if not video_path:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Video input is required",
                    "help": "Either provide a video_url parameter OR upload a video file"
                }
            )
    
    # Handle audio input (from URL or file upload)
    audio_path = None
    audio_filename = None
    uploaded_audio_file = None
    
    # Final check: If audio_url is still None, search all form keys (case-insensitive)
    # This handles cases where the form key might be different
    # But skip keys that are clearly file uploads (not URL fields)
    if not audio_url:
        for key in form.keys():
            value = form.get(key)
            # Skip UploadFile objects - they're files, not URLs
            if isinstance(value, UploadFile):
                continue
            
            key_lower = key.lower().replace('-', '_').replace(' ', '_')
            # Only check URL-specific keys, not generic 'audio' (which might be a file upload field name)
            if key_lower in ['audio_url', 'audiourl', 'audiofileurl']:
                if value:
                    audio_url = str(value).strip() if str(value).strip() else None
                    if audio_url:
                        break
    
    # Now check if we have audio_url - if yes, download it; if no, look for file upload
    if audio_url and audio_url.strip():
        # Download audio from URL using yt-dlp with audio_only=True (same pattern as download-from-url)
        try:
            # Prepare output directory for audio download
            audio_download_dir = project_root / "temp_videos" / "uploads"
            audio_download_dir.mkdir(parents=True, exist_ok=True)
            
            audio_output_filename = f"merge_audio_download_{timestamp}"
            audio_output_path = audio_download_dir / f"{audio_output_filename}.mp3"
            
            # Initialize yt-dlp service (same as download-from-url)
            ytdlp_service = YTDLPService(output_dir=audio_download_dir)
            
            # Run download in executor to avoid blocking (same pattern as process_ytdlp_download)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                ytdlp_service.download_video,
                audio_url,
                audio_output_filename,
                "best",  # quality
                "mp3",   # format_type
                True,    # audio_only
                cookies_file,  # cookies_file (universal for all downloads)
            )
            
            audio_path = Path(result["output_path"])
            if not audio_path.exists():
                raise Exception("Downloaded audio file was not found")
            
            audio_filename = audio_path.name
            
        except Exception as e:
            # Clean up cookies file on error
            if cookies_file and Path(cookies_file).exists():
                try:
                    Path(cookies_file).unlink()
                except Exception:
                    pass
            raise HTTPException(
                status_code=400,
                detail={
                    "error": f"Failed to download audio from URL: {str(e)}",
                    "url": audio_url,
                }
            )
    else:
        # Find audio file in form data
        audio_file = None
        audio_extensions = {'.mp3', '.wav', '.aac', '.m4a', '.ogg', '.flac', '.wma'}
        
        for key, value in form.items():
            # Skip cookie files - they're not audio files
            key_lower = key.lower()
            if 'cookie' in key_lower:
                continue
            
            is_upload_file = (
                isinstance(value, UploadFile) or 
                type(value).__name__ == "UploadFile" or
                (hasattr(value, 'filename') and hasattr(value, 'read') and hasattr(value, 'file'))
            )
            
            if is_upload_file and value != uploaded_video_file:  # Don't use same file as video
                filename = getattr(value, 'filename', '')
                ext = Path(filename).suffix.lower()
                if ext in audio_extensions:
                    audio_file = value
                    uploaded_audio_file = value
                    break
        
        if not audio_file:
            # Try to find any file as audio (skip the uploaded video file if it exists)
            for key, value in form.items():
                # Skip cookie files - they're not audio files
                key_lower = key.lower()
                if 'cookie' in key_lower:
                    continue
                
                is_upload_file = (
                    isinstance(value, UploadFile) or 
                    type(value).__name__ == "UploadFile" or
                    (hasattr(value, 'filename') and hasattr(value, 'read') and hasattr(value, 'file'))
                )
                if is_upload_file and value != uploaded_video_file:
                    audio_file = value
                    uploaded_audio_file = value
                    break
        
        if not audio_file:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Audio input is required",
                    "help": "Either provide an audio_url parameter OR upload an audio file (mp3, wav, aac, etc.)"
                }
            )
        
        # Save uploaded audio file
        upload_dir = project_root / "temp_videos" / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        audio_filename = audio_file.filename or "audio"
        # Ensure filename has an extension - try to detect from content-type
        if not Path(audio_filename).suffix:
            # Try to get extension from content-type header
            content_type = getattr(audio_file, 'content_type', None)
            if content_type:
                ext = mimetypes.guess_extension(content_type.split(';')[0].strip())
                if ext:
                    audio_filename = f"{audio_filename}{ext}"
            # If no extension can be determined, leave it as-is
            # FFmpeg/MoviePy can auto-detect format from file headers
        
        audio_path = upload_dir / f"merge_audio_{timestamp}_{audio_filename}"
        
        # Save uploaded audio
        with open(audio_path, "wb") as f:
            content = await audio_file.read()
            f.write(content)
    
    try:
        if not video_path:
            raise HTTPException(status_code=400, detail="Video input is required (either video_url or video file upload)")
        
        if not audio_path:
            raise HTTPException(status_code=400, detail="Audio input is required (either audio_url or audio file upload)")
        
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
                "video_url": video_url if video_url else None,
                "audio_url": audio_url if audio_url else None,
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
        
        # Clean up cookies file after downloads complete (no longer needed)
        # Downloads happen synchronously, so cookies are safe to delete now
        if cookies_file and Path(cookies_file).exists():
            try:
                Path(cookies_file).unlink()
            except Exception:
                pass
        
        # Return job_id immediately
        return {
            "job_id": job_id,
            "status": "pending",
            "message": "Files uploaded successfully. Merging started.",
            "status_url": f"/api/v1/jobs/{job_id}",
            "download_url": f"/api/v1/videos/{job_id}/download",
        }
    
    except HTTPException:
        # Re-raise HTTPExceptions (they're already properly formatted)
        raise
    except Exception as e:
        # Clean up on error
        if video_path and Path(video_path).exists():
            Path(video_path).unlink()
        if audio_path and Path(audio_path).exists():
            Path(audio_path).unlink()
        # Clean up cookies file
        if cookies_file and Path(cookies_file).exists():
            try:
                Path(cookies_file).unlink()
            except Exception:
                pass
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
    video_url: Optional[str] = Form(None),
    cookies_file: Optional[UploadFile] = File(None),
):
    """
    Comprehensive video processing endpoint - apply multiple transformations in one request.
    
    Upload a video file (or provide URL) and optionally an audio file, then apply multiple processing operations
    based on boolean flags. All operations are applied in sequence:
    1. Merge audio (if merge_audio=True and audio file provided)
    2. Remove audio (if remove_audio=True, overrides merge_audio)
    3. Color grading (if color_grading=True)
    4. Crop and zoom to square (if crop_zoom=True)
    5. Re-encode (if reencode=True)
    
    Either:
    - Upload a video file with any field name (and optionally an audio file)
    - OR provide a video_url parameter with a URL to download from (YouTube, Instagram, etc.)
    
    The files/request must be sent as multipart/form-data.
    
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
    
    # Extract cookies file if provided
    upload_dir = project_root / "temp_videos" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    cookies_path = None
    try:
        cookies_path = await extract_cookies_file(form, upload_dir)
    except HTTPException:
        raise
    except Exception:
        pass
    
    try:
        # Get video input (from URL or file upload)
        input_video_path, video_filename = await get_video_input(
            form=form,
            video_url=video_url,
            prefix="process",
            cookies_file=cookies_path,
        )
        
        # Find audio file if merge_audio is requested
        audio_file = None
        input_audio_path = None
        audio_filename = None
        
        if merge_audio:
            audio_extensions = {'.mp3', '.wav', '.aac', '.m4a', '.ogg', '.flac', '.wma'}
            
            # Find audio file in form data
            for key, value in form.items():
                is_upload_file = (
                    isinstance(value, UploadFile) or 
                    type(value).__name__ == "UploadFile" or
                    (hasattr(value, 'filename') and hasattr(value, 'read') and hasattr(value, 'file'))
                )
                
                if is_upload_file:
                    filename = getattr(value, 'filename', '')
                    ext = Path(filename).suffix.lower()
                    if ext in audio_extensions:
                        audio_file = value
                        break
            
            if not audio_file:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "merge_audio=True requires an audio file to be uploaded",
                        "help": "Upload an audio file (mp3, wav, aac, etc.) when merge_audio=True"
                    }
                )
            
            # Save audio file
            upload_dir = project_root / "temp_videos" / "uploads"
            upload_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            audio_filename = audio_file.filename or "audio"
            input_audio_path = upload_dir / f"process_audio_{timestamp}_{audio_filename}"
            
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
                "video_url": video_url if video_url else None,
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
