"""
Job Manager for tracking video generation tasks.

Manages job status, results, and metadata for long-running video processing tasks.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Dict, Optional, Any
from pathlib import Path
import json


class JobStatus(str, Enum):
    """Job status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobManager:
    """Manages video generation jobs and their status."""
    
    def __init__(self):
        """Initialize the job manager."""
        self._jobs: Dict[str, Dict[str, Any]] = {}
    
    def create_job(
        self,
        job_type: str,
        parameters: Dict[str, Any],
        output_path: Optional[Path] = None,
    ) -> str:
        """
        Create a new job and return its ID.
        
        Args:
            job_type: Type of job (e.g., "video_generation", "video_upload")
            parameters: Job parameters
            output_path: Optional output file path
            
        Returns:
            Job ID (UUID string)
        """
        job_id = str(uuid.uuid4())
        
        self._jobs[job_id] = {
            "id": job_id,
            "type": job_type,
            "status": JobStatus.PENDING,
            "parameters": parameters,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "output_path": str(output_path) if output_path else None,
            "error": None,
            "progress": 0,
            "message": "Job created",
        }
        
        return job_id
    
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get job information by ID.
        
        Args:
            job_id: Job ID
            
        Returns:
            Job dictionary or None if not found
        """
        return self._jobs.get(job_id)
    
    def update_job(
        self,
        job_id: str,
        status: Optional[JobStatus] = None,
        progress: Optional[int] = None,
        message: Optional[str] = None,
        error: Optional[str] = None,
        output_path: Optional[Path] = None,
    ) -> bool:
        """
        Update job status and information.
        
        Args:
            job_id: Job ID
            status: New status
            progress: Progress percentage (0-100)
            message: Status message
            error: Error message if failed
            output_path: Output file path when completed
            
        Returns:
            True if job was updated, False if not found
        """
        if job_id not in self._jobs:
            return False
        
        job = self._jobs[job_id]
        
        if status:
            job["status"] = status
        if progress is not None:
            job["progress"] = max(0, min(100, progress))
        if message:
            job["message"] = message
        if error:
            job["error"] = error
        if output_path:
            job["output_path"] = str(output_path)
        
        job["updated_at"] = datetime.utcnow().isoformat()
        
        return True
    
    def list_jobs(
        self,
        status: Optional[JobStatus] = None,
        limit: int = 100,
    ) -> list[Dict[str, Any]]:
        """
        List jobs, optionally filtered by status.
        
        Args:
            status: Optional status filter
            limit: Maximum number of jobs to return
            
        Returns:
            List of job dictionaries
        """
        jobs = list(self._jobs.values())
        
        if status:
            jobs = [j for j in jobs if j["status"] == status]
        
        # Sort by created_at descending
        jobs.sort(key=lambda x: x["created_at"], reverse=True)
        
        return jobs[:limit]
    
    def delete_job(self, job_id: str) -> bool:
        """
        Delete a job from the manager.
        
        Args:
            job_id: Job ID
            
        Returns:
            True if job was deleted, False if not found
        """
        if job_id in self._jobs:
            del self._jobs[job_id]
            return True
        return False

