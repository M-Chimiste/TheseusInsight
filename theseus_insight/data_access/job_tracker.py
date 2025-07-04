"""Simple job tracking system for background tasks."""

import time
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running" 
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobTracker:
    """Simple in-memory job tracking system."""
    
    def __init__(self):
        self._jobs: Dict[str, Dict[str, Any]] = {}
        
    def create_job(
        self,
        job_type: str,
        description: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create a new job and return its ID."""
        job_id = str(uuid.uuid4())
        
        self._jobs[job_id] = {
            "id": job_id,
            "type": job_type,
            "description": description,
            "status": JobStatus.PENDING,
            "created_at": datetime.now(),
            "started_at": None,
            "completed_at": None,
            "progress": {
                "current": 0,
                "total": 0,
                "message": "Initializing..."
            },
            "result": None,
            "error": None,
            "metadata": metadata or {}
        }
        
        return job_id
    
    def start_job(self, job_id: str) -> bool:
        """Mark a job as started."""
        if job_id not in self._jobs:
            return False
            
        job = self._jobs[job_id]
        job["status"] = JobStatus.RUNNING
        job["started_at"] = datetime.now()
        job["progress"]["message"] = "Starting..."
        
        return True
    
    def update_progress(
        self,
        job_id: str,
        current: int,
        total: int,
        message: str = ""
    ) -> bool:
        """Update job progress."""
        if job_id not in self._jobs:
            return False
            
        job = self._jobs[job_id]
        job["progress"] = {
            "current": current,
            "total": total,
            "message": message,
            "percentage": round((current / total * 100) if total > 0 else 0, 1)
        }
        
        return True
    
    def complete_job(
        self,
        job_id: str,
        result: Optional[Any] = None
    ) -> bool:
        """Mark a job as completed."""
        if job_id not in self._jobs:
            return False
            
        job = self._jobs[job_id]
        job["status"] = JobStatus.COMPLETED
        job["completed_at"] = datetime.now()
        job["result"] = result
        job["progress"]["message"] = "Completed"
        
        return True
    
    def fail_job(
        self,
        job_id: str,
        error: str
    ) -> bool:
        """Mark a job as failed."""
        if job_id not in self._jobs:
            return False
            
        job = self._jobs[job_id]
        job["status"] = JobStatus.FAILED
        job["completed_at"] = datetime.now()
        job["error"] = error
        job["progress"]["message"] = f"Failed: {error}"
        
        return True
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a job."""
        if job_id not in self._jobs:
            return False
            
        job = self._jobs[job_id]
        if job["status"] in [JobStatus.COMPLETED, JobStatus.FAILED]:
            return False  # Cannot cancel completed/failed jobs
            
        job["status"] = JobStatus.CANCELLED
        job["completed_at"] = datetime.now()
        job["progress"]["message"] = "Cancelled"
        
        return True
    
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job details."""
        job = self._jobs.get(job_id)
        if not job:
            return None
            
        # Convert datetime objects to ISO strings for JSON serialization
        result = job.copy()
        for date_field in ['created_at', 'started_at', 'completed_at']:
            if result[date_field]:
                result[date_field] = result[date_field].isoformat()
                
        return result
    
    def list_jobs(
        self,
        job_type: Optional[str] = None,
        status: Optional[JobStatus] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """List jobs with optional filtering."""
        jobs = list(self._jobs.values())
        
        # Apply filters
        if job_type:
            jobs = [job for job in jobs if job["type"] == job_type]
        if status:
            jobs = [job for job in jobs if job["status"] == status]
            
        # Sort by creation time (newest first)
        jobs.sort(key=lambda x: x["created_at"], reverse=True)
        
        # Limit results
        jobs = jobs[:limit]
        
        # Convert datetime objects for JSON serialization
        result = []
        for job in jobs:
            job_copy = job.copy()
            for date_field in ['created_at', 'started_at', 'completed_at']:
                if job_copy[date_field]:
                    job_copy[date_field] = job_copy[date_field].isoformat()
            result.append(job_copy)
            
        return result
    
    def cleanup_old_jobs(self, max_age_hours: int = 24) -> int:
        """Remove jobs older than specified hours."""
        cutoff_time = datetime.now().timestamp() - (max_age_hours * 3600)
        
        jobs_to_remove = []
        for job_id, job in self._jobs.items():
            job_time = job["created_at"].timestamp()
            if job_time < cutoff_time and job["status"] in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                jobs_to_remove.append(job_id)
        
        for job_id in jobs_to_remove:
            del self._jobs[job_id]
            
        return len(jobs_to_remove)


# Global job tracker instance
_job_tracker = JobTracker()


def get_job_tracker() -> JobTracker:
    """Get the global job tracker instance."""
    return _job_tracker 