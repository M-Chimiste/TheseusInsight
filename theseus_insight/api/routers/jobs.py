"""
API endpoints for job monitoring and management.
Provides real-time status updates for processing jobs.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID
import asyncpg

from ...data_processing.checkpoint_manager import CheckpointManager
from ...db import get_connection_pool
from ..models import (
    JobStatus,
    JobResponse,
    JobListResponse,
    JobStatisticsResponse
)

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])


@router.get("/", response_model=JobListResponse)
async def list_jobs(
    status: Optional[str] = Query(None, description="Filter by job status"),
    job_type: Optional[str] = Query(None, description="Filter by job type"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of jobs to return"),
    offset: int = Query(0, ge=0, description="Number of jobs to skip")
) -> JobListResponse:
    """
    List all processing jobs with optional filtering.
    
    Status values: pending, running, completed, failed, cancelled
    Job types: harvest_judge, bulk_judge, embedding_backfill, newsletter_generation
    """
    pool = await get_connection_pool()
    
    query_parts = ["SELECT * FROM processing_jobs WHERE 1=1"]
    params = []
    param_count = 0
    
    if status:
        param_count += 1
        query_parts.append(f"AND status = ${param_count}")
        params.append(status)
    
    if job_type:
        param_count += 1
        query_parts.append(f"AND job_type = ${param_count}")
        params.append(job_type)
    
    # Add ordering and pagination
    query_parts.append("ORDER BY created_at DESC")
    param_count += 1
    query_parts.append(f"LIMIT ${param_count}")
    params.append(limit)
    param_count += 1
    query_parts.append(f"OFFSET ${param_count}")
    params.append(offset)
    
    query = " ".join(query_parts)
    
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
        
        # Get total count
        count_query = "SELECT COUNT(*) FROM processing_jobs WHERE 1=1"
        if status:
            count_query += f" AND status = '{status}'"
        if job_type:
            count_query += f" AND job_type = '{job_type}'"
        
        total_count = await conn.fetchval(count_query)
    
    jobs = []
    for row in rows:
        jobs.append(JobResponse(
            id=row['id'],
            job_type=row['job_type'],
            status=row['status'],
            configuration=row['configuration'],
            state=row['state'],
            progress_current=row['progress_current'],
            progress_total=row['progress_total'],
            progress_percent=float(row['progress_percent']) if row['progress_percent'] else 0,
            error_message=row['error_message'],
            error_count=row['error_count'],
            started_at=row['started_at'],
            completed_at=row['completed_at'],
            last_checkpoint_at=row['last_checkpoint_at'],
            created_at=row['created_at'],
            updated_at=row['updated_at']
        ))
    
    return JobListResponse(
        jobs=jobs,
        total=total_count,
        limit=limit,
        offset=offset
    )


@router.get("/active", response_model=List[JobResponse])
async def get_active_jobs() -> List[JobResponse]:
    """Get all currently active (pending or running) jobs."""
    pool = await get_connection_pool()
    
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM active_jobs
            ORDER BY started_at DESC
            """
        )
    
    jobs = []
    for row in rows:
        jobs.append(JobResponse(
            id=row['id'],
            job_type=row['job_type'],
            status=row['status'],
            configuration={},  # Not included in view
            state={},  # Not included in view
            progress_current=0,  # Calculate from percent
            progress_total=0,  # Calculate from percent
            progress_percent=float(row['progress_percent']) if row['progress_percent'] else 0,
            error_message=None,
            error_count=0,
            started_at=row['started_at'],
            completed_at=None,
            last_checkpoint_at=row['last_checkpoint_at'],
            created_at=datetime.now(),  # Not included in view
            updated_at=datetime.now()  # Not included in view
        ))
    
    return jobs


@router.get("/statistics", response_model=JobStatisticsResponse)
async def get_job_statistics(
    job_type: Optional[str] = Query(None, description="Filter statistics by job type")
) -> JobStatisticsResponse:
    """Get aggregated job statistics."""
    pool = await get_connection_pool()
    
    async with pool.acquire() as conn:
        if job_type:
            rows = await conn.fetch(
                """
                SELECT * FROM job_statistics
                WHERE job_type = $1
                """,
                job_type
            )
        else:
            rows = await conn.fetch("SELECT * FROM job_statistics")
    
    statistics = []
    for row in rows:
        statistics.append({
            'job_type': row['job_type'],
            'total_jobs': row['total_jobs'],
            'completed_jobs': row['completed_jobs'],
            'failed_jobs': row['failed_jobs'],
            'running_jobs': row['running_jobs'],
            'avg_runtime_minutes': float(row['avg_runtime_minutes']) if row['avg_runtime_minutes'] else 0,
            'success_rate': (row['completed_jobs'] / row['total_jobs'] * 100) if row['total_jobs'] > 0 else 0
        })
    
    # Calculate overall statistics
    total_all = sum(s['total_jobs'] for s in statistics)
    completed_all = sum(s['completed_jobs'] for s in statistics)
    failed_all = sum(s['failed_jobs'] for s in statistics)
    running_all = sum(s['running_jobs'] for s in statistics)
    
    return JobStatisticsResponse(
        statistics=statistics,
        overall={
            'total_jobs': total_all,
            'completed_jobs': completed_all,
            'failed_jobs': failed_all,
            'running_jobs': running_all,
            'success_rate': (completed_all / total_all * 100) if total_all > 0 else 0
        }
    )


@router.get("/{job_id}", response_model=JobResponse)
async def get_job_details(job_id: UUID) -> JobResponse:
    """Get detailed information about a specific job."""
    checkpoint_manager = CheckpointManager()
    await checkpoint_manager.initialize()
    
    job_state = await checkpoint_manager.get_job_state(job_id)
    
    if not job_state:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    pool = await get_connection_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM processing_jobs WHERE id = $1",
            job_id
        )
    
    return JobResponse(
        id=row['id'],
        job_type=row['job_type'],
        status=row['status'],
        configuration=row['configuration'],
        state=row['state'],
        progress_current=row['progress_current'],
        progress_total=row['progress_total'],
        progress_percent=float(row['progress_percent']) if row['progress_percent'] else 0,
        error_message=row['error_message'],
        error_count=row['error_count'],
        started_at=row['started_at'],
        completed_at=row['completed_at'],
        last_checkpoint_at=row['last_checkpoint_at'],
        created_at=row['created_at'],
        updated_at=row['updated_at']
    )


@router.get("/{job_id}/checkpoints")
async def get_job_checkpoints(
    job_id: UUID,
    checkpoint_type: Optional[str] = Query(None, description="Filter by checkpoint type")
) -> List[Dict[str, Any]]:
    """Get all checkpoints for a specific job."""
    pool = await get_connection_pool()
    
    query = """
        SELECT * FROM processing_checkpoints
        WHERE job_id = $1
    """
    params = [job_id]
    
    if checkpoint_type:
        query += " AND checkpoint_type = $2"
        params.append(checkpoint_type)
    
    query += " ORDER BY created_at DESC"
    
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
    
    checkpoints = []
    for row in rows:
        checkpoints.append({
            'id': row['id'],
            'checkpoint_type': row['checkpoint_type'],
            'checkpoint_data': row['checkpoint_data'],
            'item_count': row['item_count'],
            'created_at': row['created_at']
        })
    
    return checkpoints


@router.post("/{job_id}/cancel")
async def cancel_job(job_id: UUID) -> Dict[str, str]:
    """Cancel a running job."""
    pool = await get_connection_pool()
    
    async with pool.acquire() as conn:
        # Check if job exists and is cancellable
        job = await conn.fetchrow(
            "SELECT status FROM processing_jobs WHERE id = $1",
            job_id
        )
        
        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        
        if job['status'] not in ['pending', 'running']:
            raise HTTPException(
                status_code=400, 
                detail=f"Job {job_id} cannot be cancelled (status: {job['status']})"
            )
        
        # Update job status
        await conn.execute(
            """
            UPDATE processing_jobs
            SET status = 'cancelled',
                completed_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = $1
            """,
            job_id
        )
    
    return {"message": f"Job {job_id} has been cancelled"}


@router.post("/{job_id}/resume")
async def resume_job(job_id: UUID) -> Dict[str, str]:
    """Resume a failed or cancelled job."""
    checkpoint_manager = CheckpointManager()
    await checkpoint_manager.initialize()
    
    try:
        # Check if job can be resumed
        job_state = await checkpoint_manager.get_job_state(job_id)
        if not job_state:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        
        if job_state['status'] not in ['failed', 'cancelled']:
            raise HTTPException(
                status_code=400,
                detail=f"Job {job_id} cannot be resumed (status: {job_state['status']})"
            )
        
        # Resume the job
        await checkpoint_manager.resume_job(job_id)
        
        # TODO: Actually restart the job processing based on job_type
        # This would require spawning the appropriate background task
        
        return {"message": f"Job {job_id} has been resumed"}
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/old", description="Clean up old completed jobs")
async def cleanup_old_jobs(
    days: int = Query(30, ge=1, le=365, description="Delete jobs older than this many days")
) -> Dict[str, Any]:
    """Clean up old completed jobs from the database."""
    checkpoint_manager = CheckpointManager()
    await checkpoint_manager.initialize()
    
    deleted_count = await checkpoint_manager.cleanup_old_jobs(days)
    
    return {
        "message": f"Deleted {deleted_count} old jobs",
        "criteria": f"Completed/cancelled jobs older than {days} days"
    }


@router.get("/{job_id}/progress/stream")
async def stream_job_progress(job_id: UUID):
    """
    Stream real-time job progress updates via Server-Sent Events.
    
    This endpoint is designed to work with EventSource in the frontend.
    """
    from fastapi import Response
    from fastapi.responses import StreamingResponse
    import asyncio
    import json
    
    async def event_generator():
        checkpoint_manager = CheckpointManager()
        await checkpoint_manager.initialize()
        
        while True:
            # Get current job state
            job_state = await checkpoint_manager.get_job_state(job_id)
            
            if not job_state:
                yield f"data: {json.dumps({'error': 'Job not found'})}\n\n"
                break
            
            # Send progress update
            progress_data = {
                'job_id': str(job_id),
                'status': job_state['status'],
                'progress': job_state['progress'],
                'error_message': job_state.get('error_message')
            }
            
            yield f"data: {json.dumps(progress_data)}\n\n"
            
            # Stop streaming if job is complete
            if job_state['status'] in ['completed', 'failed', 'cancelled']:
                break
            
            # Wait before next update
            await asyncio.sleep(2)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )