"""
FastAPI Video Generation Service

Main application entry point for the video generation API.
"""

import os
import sys
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from api.routes import video, status
from api.core.job_manager import JobManager

# Initialize job manager
job_manager = JobManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown events."""
    # Startup
    print("=" * 80)
    print("FastAPI Video Generation Service")
    print("=" * 80)
    print(f"Project root: {project_root}")
    print("Service starting...")
    print("=" * 80)
    
    # Ensure temp directories exist - organized by use case
    temp_dir = project_root / "temp_videos"
    temp_dir.mkdir(exist_ok=True)
    
    # Upload directory (shared across all use cases)
    upload_dir = temp_dir / "uploads"
    upload_dir.mkdir(exist_ok=True)
    
    # Output directories organized by use case
    audio_removal_dir = temp_dir / "output" / "audio_removal"
    audio_removal_dir.mkdir(parents=True, exist_ok=True)
    
    scene_detection_dir = temp_dir / "output" / "scene_detection"
    scene_detection_dir.mkdir(parents=True, exist_ok=True)
    
    color_grading_dir = temp_dir / "output" / "color_grading"
    color_grading_dir.mkdir(parents=True, exist_ok=True)
    
    crop_zoom_dir = temp_dir / "output" / "crop_zoom"
    crop_zoom_dir.mkdir(parents=True, exist_ok=True)
    
    reencode_dir = temp_dir / "output" / "reencode"
    reencode_dir.mkdir(parents=True, exist_ok=True)
    
    merge_audio_video_dir = temp_dir / "output" / "merge_audio_video"
    merge_audio_video_dir.mkdir(parents=True, exist_ok=True)
    
    comprehensive_dir = temp_dir / "output" / "comprehensive"
    comprehensive_dir.mkdir(parents=True, exist_ok=True)
    
    yield
    
    # Shutdown
    print("Service shutting down...")


# Create FastAPI app
app = FastAPI(
    title="Gallardo Video Generation Service",
    description="API service for generating videos with text overlays and custom processing",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(video.router, prefix="/api/v1", tags=["videos"])
app.include_router(status.router, prefix="/api/v1", tags=["status"])


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "service": "Gallardo Video Generation Service",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/v1/health",
    }


@app.get("/api/v1/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "video-generation",
    }


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": str(exc),
        },
    )


# Make job_manager available to routes
app.state.job_manager = job_manager

