"""
Bulk operations API endpoints for TheseusInsight.
Provides endpoints for triggering and managing bulk processing operations.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from uuid import UUID, uuid4
import asyncio

from ...data_processing.checkpoint_manager import CheckpointManager
from ...utils.harvest_and_judge import harvest_and_judge
from ...data_access.bulk_judge import BulkJudgeRunner
from ...utils.backfill_embeddings import backfill_embeddings
from ...utils.backfill_keywords import backfill_keywords
from ...db import get_connection_pool

router = APIRouter(prefix="/api/bulk-operations", tags=["bulk-operations"])

# Request models
class HarvestJudgeRequest(BaseModel):
    date_from: str = Field(..., description="Start date in YYYY-MM-DD format")
    date_to: str = Field(..., description="End date in YYYY-MM-DD format")
    top_n: int = Field(5, description="Number of top papers to select")
    cosine_threshold: float = Field(0.5, description="Cosine similarity threshold")
    update_existing: bool = Field(False, description="Whether to update existing papers")
    batch_size: int = Field(100, description="Batch size for processing")
    max_workers: int = Field(10, description="Maximum number of workers")
    rate_limit_requests: int = Field(5, description="Rate limit requests per second")
    
class BulkJudgeRequest(BaseModel):
    profile_ids: Optional[List[str]] = Field(None, description="List of profile IDs to judge")
    all_profiles: bool = Field(False, description="Judge all profiles")
    limit: Optional[int] = Field(None, description="Limit number of papers to judge")
    start_date: Optional[str] = Field(None, description="Start date for papers")
    end_date: Optional[str] = Field(None, description="End date for papers")
    batch_size: int = Field(100, description="Batch size for processing")
    
class BackfillEmbeddingsRequest(BaseModel):
    limit: Optional[int] = Field(None, description="Limit number of papers to process")
    batch_size: int = Field(100, description="Batch size for processing")
    start_date: Optional[str] = Field(None, description="Start date for papers")
    end_date: Optional[str] = Field(None, description="End date for papers")
    
class BackfillKeywordsRequest(BaseModel):
    limit: Optional[int] = Field(None, description="Limit number of papers to process")
    batch_size: int = Field(100, description="Batch size for processing")
    start_date: Optional[str] = Field(None, description="Start date for papers")
    end_date: Optional[str] = Field(None, description="End date for papers")

# Response models
class JobStartResponse(BaseModel):
    job_id: UUID
    job_type: str
    status: str
    message: str
    
class JobStatusResponse(BaseModel):
    job_id: UUID
    job_type: str
    status: str
    progress_current: int
    progress_total: Optional[int]
    progress_percent: float
    error_message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    last_checkpoint_at: Optional[datetime]

# Background task functions
async def run_harvest_judge_task(
    job_id: UUID,
    request: HarvestJudgeRequest,
    checkpoint_manager: CheckpointManager
):
    """Run harvest and judge operation in background."""
    try:
        await harvest_and_judge(
            date_from=request.date_from,
            date_to=request.date_to,
            checkpoint_dir=".",  # Not used with database checkpoints
            top_n=request.top_n,
            cosine_threshold=request.cosine_threshold,
            update_existing=request.update_existing,
            batch_size=request.batch_size,
            max_workers=request.max_workers,
            rate_limit_requests=request.rate_limit_requests,
            use_database_checkpoints=True,
            job_id=job_id
        )
    except Exception as e:
        await checkpoint_manager.fail_job(job_id, str(e))
        raise

async def run_bulk_judge_task(
    job_id: UUID,
    request: BulkJudgeRequest,
    checkpoint_manager: CheckpointManager
):
    """Run bulk judge operation in background."""
    try:
        pool = await get_connection_pool()
        runner = BulkJudgeRunner(pool=pool, checkpoint_manager=checkpoint_manager, job_id=job_id)
        
        await runner.run_bulk_judge(
            profile_ids=request.profile_ids,
            all_profiles=request.all_profiles,
            limit=request.limit,
            start_date=request.start_date,
            end_date=request.end_date,
            batch_size=request.batch_size
        )
    except Exception as e:
        await checkpoint_manager.fail_job(job_id, str(e))
        raise

async def run_backfill_embeddings_task(
    job_id: UUID,
    request: BackfillEmbeddingsRequest,
    checkpoint_manager: CheckpointManager
):
    """Run embeddings backfill operation in background."""
    try:
        await backfill_embeddings(
            limit=request.limit,
            batch_size=request.batch_size,
            start_date=request.start_date,
            end_date=request.end_date,
            use_database_checkpoints=True,
            job_id=job_id
        )
    except Exception as e:
        await checkpoint_manager.fail_job(job_id, str(e))
        raise

async def run_backfill_keywords_task(
    job_id: UUID,
    request: BackfillKeywordsRequest,
    checkpoint_manager: CheckpointManager
):
    """Run keywords backfill operation in background."""
    try:
        await backfill_keywords(
            limit=request.limit,
            batch_size=request.batch_size,
            start_date=request.start_date,
            end_date=request.end_date,
            use_database_checkpoints=True,
            job_id=job_id
        )
    except Exception as e:
        await checkpoint_manager.fail_job(job_id, str(e))
        raise

# API endpoints
@router.post("/harvest-judge", response_model=JobStartResponse)
async def start_harvest_judge(
    request: HarvestJudgeRequest,
    background_tasks: BackgroundTasks
) -> JobStartResponse:
    """Start a harvest and judge operation."""
    job_id = uuid4()
    checkpoint_manager = CheckpointManager(await get_connection_pool())
    
    # Create job record
    await checkpoint_manager.create_job(
        job_id=job_id,
        job_type="harvest_judge",
        job_config={
            "date_from": request.date_from,
            "date_to": request.date_to,
            "top_n": request.top_n,
            "cosine_threshold": request.cosine_threshold,
            "update_existing": request.update_existing,
            "batch_size": request.batch_size,
            "max_workers": request.max_workers,
            "rate_limit_requests": request.rate_limit_requests
        }
    )
    
    # Start background task
    background_tasks.add_task(
        run_harvest_judge_task,
        job_id,
        request,
        checkpoint_manager
    )
    
    return JobStartResponse(
        job_id=job_id,
        job_type="harvest_judge",
        status="running",
        message=f"Harvest and judge operation started for {request.date_from} to {request.date_to}"
    )

@router.post("/bulk-judge", response_model=JobStartResponse)
async def start_bulk_judge(
    request: BulkJudgeRequest,
    background_tasks: BackgroundTasks
) -> JobStartResponse:
    """Start a bulk judge operation."""
    if not request.all_profiles and not request.profile_ids:
        raise HTTPException(
            status_code=400,
            detail="Either all_profiles must be true or profile_ids must be provided"
        )
    
    job_id = uuid4()
    checkpoint_manager = CheckpointManager(await get_connection_pool())
    
    # Create job record
    await checkpoint_manager.create_job(
        job_id=job_id,
        job_type="bulk_judge",
        job_config={
            "profile_ids": request.profile_ids,
            "all_profiles": request.all_profiles,
            "limit": request.limit,
            "start_date": request.start_date,
            "end_date": request.end_date,
            "batch_size": request.batch_size
        }
    )
    
    # Start background task
    background_tasks.add_task(
        run_bulk_judge_task,
        job_id,
        request,
        checkpoint_manager
    )
    
    profile_desc = "all profiles" if request.all_profiles else f"{len(request.profile_ids)} profiles"
    return JobStartResponse(
        job_id=job_id,
        job_type="bulk_judge",
        status="running",
        message=f"Bulk judge operation started for {profile_desc}"
    )

@router.post("/backfill-embeddings", response_model=JobStartResponse)
async def start_backfill_embeddings(
    request: BackfillEmbeddingsRequest,
    background_tasks: BackgroundTasks
) -> JobStartResponse:
    """Start an embeddings backfill operation."""
    job_id = uuid4()
    checkpoint_manager = CheckpointManager(await get_connection_pool())
    
    # Create job record
    await checkpoint_manager.create_job(
        job_id=job_id,
        job_type="embedding_backfill",
        job_config={
            "limit": request.limit,
            "batch_size": request.batch_size,
            "start_date": request.start_date,
            "end_date": request.end_date
        }
    )
    
    # Start background task
    background_tasks.add_task(
        run_backfill_embeddings_task,
        job_id,
        request,
        checkpoint_manager
    )
    
    return JobStartResponse(
        job_id=job_id,
        job_type="embedding_backfill",
        status="running",
        message="Embeddings backfill operation started"
    )

@router.post("/backfill-keywords", response_model=JobStartResponse)
async def start_backfill_keywords(
    request: BackfillKeywordsRequest,
    background_tasks: BackgroundTasks
) -> JobStartResponse:
    """Start a keywords backfill operation."""
    job_id = uuid4()
    checkpoint_manager = CheckpointManager(await get_connection_pool())
    
    # Create job record
    await checkpoint_manager.create_job(
        job_id=job_id,
        job_type="keyword_backfill",
        job_config={
            "limit": request.limit,
            "batch_size": request.batch_size,
            "start_date": request.start_date,
            "end_date": request.end_date
        }
    )
    
    # Start background task
    background_tasks.add_task(
        run_backfill_keywords_task,
        job_id,
        request,
        checkpoint_manager
    )
    
    return JobStartResponse(
        job_id=job_id,
        job_type="keyword_backfill",
        status="running",
        message="Keywords backfill operation started"
    )

@router.get("/job/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: UUID) -> JobStatusResponse:
    """Get the status of a bulk operation job."""
    pool = await get_connection_pool()
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT 
                id, job_type, status, progress_current, progress_total,
                CASE 
                    WHEN progress_total > 0 THEN (progress_current::float / progress_total * 100)
                    ELSE 0
                END as progress_percent,
                error_message, started_at, completed_at, last_checkpoint_at
            FROM processing_jobs
            WHERE id = $1
            """,
            job_id
        )
        
        if not row:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return JobStatusResponse(
            job_id=row['id'],
            job_type=row['job_type'],
            status=row['status'],
            progress_current=row['progress_current'],
            progress_total=row['progress_total'],
            progress_percent=row['progress_percent'],
            error_message=row['error_message'],
            started_at=row['started_at'],
            completed_at=row['completed_at'],
            last_checkpoint_at=row['last_checkpoint_at']
        )

@router.get("/validate-date-range")
async def validate_date_range(
    start_date: str = Query(..., description="Start date in YYYY-MM-DD format"),
    end_date: str = Query(..., description="End date in YYYY-MM-DD format")
) -> Dict[str, Any]:
    """Validate date range and check for existing data."""
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        
        if start > end:
            raise HTTPException(
                status_code=400,
                detail="Start date must be before or equal to end date"
            )
        
        pool = await get_connection_pool()
        async with pool.acquire() as conn:
            # Check for existing papers in date range
            paper_count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM papers
                WHERE published_date >= $1 AND published_date <= $2
                """,
                start, end
            )
            
            # Check for papers with embeddings
            papers_with_embeddings = await conn.fetchval(
                """
                SELECT COUNT(*) FROM papers
                WHERE published_date >= $1 AND published_date <= $2
                AND embedding IS NOT NULL
                """,
                start, end
            )
            
            # Check for papers with keywords
            papers_with_keywords = await conn.fetchval(
                """
                SELECT COUNT(*) FROM papers
                WHERE published_date >= $1 AND published_date <= $2
                AND keywords IS NOT NULL
                """,
                start, end
            )
            
        return {
            "valid": True,
            "start_date": start_date,
            "end_date": end_date,
            "days": (end - start).days + 1,
            "existing_papers": paper_count,
            "papers_with_embeddings": papers_with_embeddings,
            "papers_with_keywords": papers_with_keywords,
            "coverage": {
                "embeddings": round(papers_with_embeddings / paper_count * 100, 1) if paper_count > 0 else 0,
                "keywords": round(papers_with_keywords / paper_count * 100, 1) if paper_count > 0 else 0
            }
        }
        
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid date format. Use YYYY-MM-DD"
        )