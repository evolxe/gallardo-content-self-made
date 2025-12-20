"""
Status and job tracking endpoints.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Request
from api.core.job_manager import JobManager, JobStatus

router = APIRouter()


def get_job_manager(request: Request) -> JobManager:
    """Dependency to get job manager from app state."""
    return request.app.state.job_manager


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str, request: Request):
    """
    Get the status of a specific job.
    
    Returns job information including status, progress, and output path if completed.
    """
    job_manager: JobManager = get_job_manager(request)
    
    job = job_manager.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return job


@router.get("/jobs")
async def list_jobs(
    request: Request,
    status: Optional[JobStatus] = Query(None, description="Filter by status"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of jobs to return"),
):
    """
    List all jobs, optionally filtered by status.
    
    Returns a list of jobs sorted by creation time (newest first).
    """
    job_manager: JobManager = get_job_manager(request)
    
    jobs = job_manager.list_jobs(status=status, limit=limit)
    
    return {
        "count": len(jobs),
        "jobs": jobs,
    }


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str, request: Request):
    """
    Delete a job from the system.
    
    Note: This does not delete the output file, only the job record.
    """
    job_manager: JobManager = get_job_manager(request)
    
    if not job_manager.delete_job(job_id):
        raise HTTPException(status_code=404, detail="Job not found")
    
    return {"message": "Job deleted successfully"}

