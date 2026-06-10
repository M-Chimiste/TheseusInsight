"""API endpoints for embedding service management.

Provides endpoints for monitoring and managing embedding jobs,
including progress tracking, job resumption, and cleanup.
"""

from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from uuid import UUID

from ...services import StreamingEmbeddingService, EmbeddingServiceConfig

from ..models import MessageResponse, CleanupHungJobsResponse

router = APIRouter(prefix="/api/embedding-service", tags=["embedding-service"])


@router.get("/jobs", response_model=List[Dict[str, Any]])
async def list_embedding_jobs() -> List[Dict[str, Any]]:
    """List all active embedding jobs with checkpoints.
    
    Returns:
        List of job information dictionaries with progress and statistics
    """
    try:
        config = EmbeddingServiceConfig()
        service = StreamingEmbeddingService(config)
        jobs = service.list_active_jobs()
        return jobs
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list embedding jobs: {str(e)}")


@router.get("/jobs/{job_id}", response_model=Dict[str, Any])
async def get_embedding_job_status(job_id: UUID) -> Dict[str, Any]:
    """Get status of a specific embedding job.
    
    Args:
        job_id: Job ID to check
        
    Returns:
        Job information dictionary or 404 if not found
    """
    try:
        config = EmbeddingServiceConfig()
        service = StreamingEmbeddingService(config)
        status = service.get_job_status(job_id)
        
        if status is None:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        
        return status
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get job status: {str(e)}")


@router.post("/jobs/{job_id}/resume", response_model=Dict[str, Any])
async def resume_embedding_job(job_id: UUID) -> Dict[str, Any]:
    """Resume an embedding job from checkpoint.
    
    Args:
        job_id: Job ID to resume
        
    Returns:
        Job statistics after resumption
    """
    try:
        config = EmbeddingServiceConfig()
        service = StreamingEmbeddingService(config)
        stats = await service.resume_from_checkpoint(job_id)
        return stats
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to resume job: {str(e)}")


@router.delete("/jobs/{job_id}", response_model=MessageResponse)
async def delete_embedding_job(job_id: UUID) -> Dict[str, str]:
    """Delete an embedding job checkpoint.
    
    Args:
        job_id: Job ID to delete
        
    Returns:
        Success message
    """
    try:
        config = EmbeddingServiceConfig()
        service = StreamingEmbeddingService(config)
        service.checkpoint_manager.delete(job_id)
        return {"message": f"Job {job_id} deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete job: {str(e)}")


@router.post("/jobs/cleanup-hung", response_model=CleanupHungJobsResponse)
async def cleanup_hung_jobs() -> Dict[str, Any]:
    """Clean up jobs that have been inactive for too long.
    
    Returns:
        List of job IDs that were cleaned up
    """
    try:
        config = EmbeddingServiceConfig()
        service = StreamingEmbeddingService(config)
        cleaned = service.cleanup_hung_jobs()
        return {
            "cleaned_jobs": [str(job_id) for job_id in cleaned],
            "count": len(cleaned)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to cleanup hung jobs: {str(e)}")


