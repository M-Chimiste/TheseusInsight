"""
Bulk operations API endpoints for TheseusInsight.
Provides endpoints for triggering and managing bulk processing operations.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
from uuid import UUID, uuid4
import asyncio
import logging

from ...data_processing.checkpoint_manager import CheckpointManager
from ...utils.harvest_and_judge import harvest_and_judge
from ...data_access.bulk_judge import BulkJudgeRunner
from ...utils.backfill_embeddings import backfill_embeddings
from ...utils.backfill_keywords import backfill_keywords
from ...db import get_connection_pool
from ...data_access.ollama_servers import OllamaServersRepository
from ...data_processing.queue_producer import JudgeQueueProducer
from ...scheduler import scheduler
from ...data_access.papers import PaperRepository
from ...data_processing.arxiv import ArxivDataProcessor
from ...data_model.papers import Paper as PaperModel
from ...inference.llm import SentenceTransformerInference

# Initialize logger for the module
logger = logging.getLogger(__name__)

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
    # Profile selection
    profile_ids: Optional[List[str]] = Field(None, description="List of profile IDs to judge")
    all_profiles: bool = Field(False, description="Judge all profiles")

    # Paper filtering
    limit: Optional[int] = Field(None, description="Limit number of papers to judge")
    start_date: Optional[str] = Field(None, description="Start date for papers")
    end_date: Optional[str] = Field(None, description="End date for papers")

    # Multi-server configuration
    use_multi_server: bool = Field(False, description="Use multiple Ollama servers for distributed processing")
    server_ids: Optional[List[int]] = Field(None, description="Specific server IDs to use (if not provided, uses all enabled servers)")
    request_timeout_sec: Optional[int] = Field(None, description="Request timeout in seconds (uses global default if not provided)")
    max_retries: Optional[int] = Field(None, description="Max retries per error type (uses global default if not provided)")

    # Scheduler and job management
    suspend_scheduled_tasks: bool = Field(True, description="Suspend background scheduled tasks during bulk job")
    overwrite_existing: bool = Field(False, description="Overwrite existing scores instead of skipping")

    # Processing configuration
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
# -------------------------------
# Preflight preparation helpers
# -------------------------------

def _filter_valid_abstracts(papers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    filtered = []
    for p in papers:
        title = (p.get('title') or '').strip()
        abstract = (p.get('abstract') or p.get('summary') or '').strip()
        if title and abstract:
            filtered.append(p)
    return filtered

def _ensure_embeddings_for_range(date_from: Optional[str], date_to: Optional[str]) -> int:
    """Ensure all papers in the date range have embeddings before judging.
    Returns number of embeddings computed.
    """
    if not date_from and not date_to:
        return 0

    # Only fetch papers missing embeddings to avoid unnecessary work
    logger.info(f"🔍 Preflight: fetching papers missing embeddings in range {date_from}..{date_to}")
    missing = PaperRepository.get_papers_missing_embeddings_in_date_range(start_date=date_from, end_date=date_to)
    if not missing:
        logger.info("Preflight: all papers already have embeddings; skipping embedding stage")
        return 0

    logger.info(f"Preflight: {len(missing)} papers missing embeddings after filtering for non-empty title/abstract")

    # Compute embeddings in batches
    logger.info(f"🧠 Preflight: embedding {len(missing)} papers in batches")
    model = SentenceTransformerInference()
    model_name = model.model_name  # Get the actual model name being used
    batch_size = 128
    updates: List[Tuple[int, List[float]]] = []
    for i in range(0, len(missing), batch_size):
        batch = missing[i:i+batch_size]
        texts = [p['abstract'] for p in batch]
        logger.info(f"🧪 Embedding batch {i//batch_size + 1}/{(len(missing)+batch_size-1)//batch_size} (papers {i+1}-{i+len(batch)})")
        embs = model.invoke(
            text=texts,
            batch_size=batch_size,
            show_progress_bar=False,
            to_list=True,
            convert_to_numpy=True
        )
        for p, emb in zip(batch, embs):
            try:
                vector = emb.tolist() if hasattr(emb, 'tolist') else list(emb)
            except Exception:
                vector = emb
            updates.append((p['id'], vector))

    if updates:
        PaperRepository.bulk_update_embeddings(updates, embedding_model=model_name)
        logger.info(f"✅ Preflight: updated embeddings for {len(updates)} papers using model {model_name}")
    return len(updates)


def _download_arxiv_for_range(
    date_from: Optional[str], 
    date_to: Optional[str],
    overwrite_existing: bool = False
) -> Dict[str, int]:
    """Download papers from arXiv for the given range and insert into DB.
    
    Args:
        date_from: Start date for the range
        date_to: End date for the range
        overwrite_existing: If True, download regardless of existing data.
                          If False, skip download if papers exist.
    
    Returns:
        Stats dict {total, imported, skipped, errors} from bulk_insert.
    """
    if not date_from and not date_to:
        logger.info("Preflight: no date range provided; skipping arXiv download")
        return {"total": 0, "imported": 0, "skipped": 0, "errors": 0}

    # Check for existing papers and decide whether to skip download
    try:
        counts = PaperRepository.count_embeddings_status_in_date_range(start_date=date_from, end_date=date_to)
        paper_count = counts.get('total', 0)
        embedded_count = counts.get('embedded', 0)
        
        # Only skip download if we have existing data AND overwrite is not requested
        if paper_count > 0 and not overwrite_existing:
            logger.info(
                f"📦 Preflight: existing papers {paper_count} (embedded {embedded_count}) in range {date_from}..{date_to}; skipping download (overwrite_existing=False)"
            )
            return {"total": paper_count, "imported": 0, "skipped": paper_count, "errors": 0}
        elif paper_count > 0 and overwrite_existing:
            logger.info(
                f"🔄 Preflight: existing papers {paper_count} found, but overwrite_existing=True; proceeding with download"
            )
    except Exception as e:
        logger.warning(f"Preflight: existing-data check failed; will attempt download: {e}")

    logger.info(f"📡 Preflight: downloading arXiv papers for range {date_from}..{date_to}")
    try:
        # Force Kaggle via explicit flag to avoid persistent env state
        proc = ArxivDataProcessor(start_date=date_from, end_date=date_to, category=None, subcategories=None, force_kaggle=True)
        df = proc.download_and_process_data()
    except Exception as e:
        logger.warning(f"Preflight: arXiv download failed: {e}")
        return {"total": 0, "imported": 0, "skipped": 0, "errors": 1}

    if df is None or df.empty:
        logger.info("Preflight: arXiv download returned no new records")
        return {"total": 0, "imported": 0, "skipped": 0, "errors": 0}

    # Convert to PaperModel list
    papers: List[PaperModel] = []
    from datetime import date as _date
    today = _date.today().strftime('%Y-%m-%d')
    for _, row in df.iterrows():
        title = row.get('title') or ''
        abstract = row.get('abstract') or ''
        pdf_url = row.get('pdf_url') or row.get('url') or ''
        created = row.get('date')
        # Ensure date string
        if hasattr(created, 'strftime'):
            created_str = created.strftime('%Y-%m-%d')
        else:
            created_str = str(created) if created else today
        try:
            papers.append(PaperModel(
                title=title,
                abstract=abstract,
                date=created_str,
                date_run=today,
                score=None,
                rationale=None,
                related=False,
                cosine_similarity=0.0,
                url=pdf_url,
                embedding_model="pending",
                embedding=None
            ))
        except Exception:
            # Skip malformed rows
            continue

    if not papers:
        logger.info("Preflight: no valid papers to insert after download")
        return {"total": 0, "imported": 0, "skipped": 0, "errors": 0}

    logger.info(f"💾 Preflight: inserting up to {len(papers)} downloaded papers into DB (skipping duplicates)")
    stats = PaperRepository.bulk_insert(papers, skip_duplicates=True)
    logger.info(f"✅ Preflight: arXiv insert stats: {stats}")
    return stats

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
    print(f"🎯 Background task started: run_bulk_judge_task for job {job_id}")
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

async def run_multi_server_bulk_judge_task(
    job_id: UUID,
    request: BulkJudgeRequest,
    checkpoint_manager: CheckpointManager,
    selected_servers: List
):
    """Run multi-server bulk judge operation using queue-based processing."""
    print(f"🎯 Background task started: run_multi_server_bulk_judge_task for job {job_id}")
    logger.info(f"🎯 Background task started: run_multi_server_bulk_judge_task for job {job_id}")
    
    # Force flush to ensure logs are written
    import sys
    sys.stdout.flush()
    sys.stderr.flush()
    
    try:
        pool = await get_connection_pool()

        # Create queue producer and enqueue tasks
        queue_producer = JudgeQueueProducer()
        
        # Convert profile_ids from strings to integers
        profile_ids_int = [int(pid) for pid in request.profile_ids] if request.profile_ids else None
        
        result = queue_producer.enqueue_bulk_judge_job(
            job_id=job_id,  # Pass as UUID, not string
            profile_ids=profile_ids_int,
            date_from=request.start_date,
            date_to=request.end_date,
            overwrite_existing=request.overwrite_existing
        )

        print(f"📊 Queue producer result: {result}")

        # Launch worker processes for each selected server
        await _launch_worker_processes(job_id, selected_servers, request.request_timeout_sec, request.max_retries)

        # Monitor job progress until completion
        await _monitor_multi_server_job(job_id, checkpoint_manager)

    except Exception as e:
        await checkpoint_manager.fail_job(job_id, str(e))
        # Restore suspended tasks on failure
        try:
            await _restore_scheduled_tasks(request.suspend_scheduled_tasks, checkpoint_manager, job_id)
        except Exception as restore_error:
            print(f"Warning: Failed to restore scheduled tasks: {restore_error}")
        raise
    finally:
        # Restore suspended tasks on completion
        try:
            await _restore_scheduled_tasks(request.suspend_scheduled_tasks, checkpoint_manager, job_id)
        except Exception as restore_error:
            print(f"Warning: Failed to restore scheduled tasks: {restore_error}")

async def _suspend_scheduled_tasks():
    """Suspend all scheduled background tasks and return snapshot."""
    suspended_tasks = []

    try:
        # Get all scheduled jobs
        jobs = scheduler.scheduler.get_jobs()

        for job in jobs:
            if hasattr(job, 'id') and hasattr(job, 'next_run_time'):
                task_info = {
                    'job_id': job.id,
                    'name': getattr(job, 'name', ''),
                    'func': str(job.func),
                    'trigger': str(job.trigger),
                    'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
                    'enabled': True
                }
                suspended_tasks.append(task_info)

                # Pause the job
                job.pause()

        return suspended_tasks

    except Exception as e:
        print(f"Error suspending scheduled tasks: {e}")
        return suspended_tasks

async def _restore_scheduled_tasks(suspend_scheduled_tasks: bool, checkpoint_manager: CheckpointManager, job_id: UUID):
    """Restore suspended scheduled tasks."""
    if not suspend_scheduled_tasks:
        return

    try:
        # Get suspended tasks from job config
        job_record = await checkpoint_manager.get_job(job_id)
        if not job_record or not job_record.configuration:
            return

        suspended_tasks = job_record.configuration.get('suspended_tasks_snapshot', [])

        for task_info in suspended_tasks:
            try:
                # Find and resume the job
                jobs = scheduler.scheduler.get_jobs()
                for job in jobs:
                    if hasattr(job, 'id') and job.id == task_info.get('job_id'):
                        job.resume()
                        break
            except Exception as e:
                print(f"Error restoring task {task_info.get('job_id')}: {e}")

    except Exception as e:
        print(f"Error restoring scheduled tasks: {e}")

async def _launch_single_worker(job_id: UUID, server_url: str, request_timeout_sec: int, max_retries: int):
    """Launch a single worker process for a specific server."""
    import subprocess
    import sys
    import os
    
    print(f"🚀 Launching single worker for job {job_id} on {server_url}")
    
    # Get the current conda environment
    conda_env = os.environ.get('CONDA_DEFAULT_ENV', 'base')
    
    try:
        # Build the command to run the worker
        cmd = [
            'conda', 'run', '-n', conda_env, 'python', '-m', 'theseus_insight.workers.judge_worker',
            '--job-id', str(job_id),
            '--server-url', server_url,
            '--timeout', str(request_timeout_sec),
            '--max-retries', str(max_retries)
        ]
        
        # Launch the process in the background; send output to DEVNULL to avoid pipe backpressure
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=os.getcwd(),
            start_new_session=True  # Detach from parent process
        )
        
        print(f"✅ Single worker launched for {server_url} (PID: {process.pid})")
        return process.pid
        
    except Exception as e:
        print(f"❌ Failed to launch single worker for {server_url}: {e}")
        raise

async def _launch_worker_processes(job_id: UUID, selected_servers, request_timeout_sec: Optional[int], max_retries: Optional[int]):
    """Launch worker processes for each selected server."""
    import subprocess
    import os
    import sys

    print(f"🚀 Launching worker processes for job {job_id} with {len(selected_servers)} servers")

    try:
        # Get global defaults if not provided
        if request_timeout_sec is None or max_retries is None:
            from ...data_access.settings import SettingsRepository
            if request_timeout_sec is None:
                request_timeout_sec = SettingsRepository.get_int("ollama_request_timeout_sec", 30)
            if max_retries is None:
                max_retries = SettingsRepository.get_int("ollama_max_retries", 3)

        print(f"⚙️ Worker configuration: timeout={request_timeout_sec}, max_retries={max_retries}")
        print(f"🚀 About to launch {len(selected_servers)} worker processes")

        # Launch a worker process for each server
        successful_launches = 0
        failed_launches = []
        
        for i, server in enumerate(selected_servers):
            try:
                print(f"\n{'='*60}")
                print(f"🔧 [{i+1}/{len(selected_servers)}] Preparing to launch worker for server: {server.name} ({server.url}) - ID: {server.id}")

                # Launch worker in background
                cmd = [
                    sys.executable, "-m", "theseus_insight.workers.judge_worker",
                    "--job-id", str(job_id),
                    "--server-url", server.url,
                    "--timeout", str(request_timeout_sec),
                    "--max-retries", str(max_retries)
                ]

                print(f"📋 Worker command: {' '.join(cmd)}")

                # Launch as background process
                print(f"🚀 Launching worker process for server {server.name}")
                print(f"📋 Command: {' '.join(cmd)}")

                try:
                    process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        cwd=os.getcwd(),
                        env=os.environ.copy()
                    )

                    print(f"✅ Launched worker process for server {server.name} (PID: {process.pid})")

                    # Wait a moment for the process to start and check for immediate errors
                    import time
                    time.sleep(1.0)  # Give it more time to start

                    if process.poll() is None:
                        print(f"🟢 Worker process {process.pid} is running successfully for {server.name}")
                        successful_launches += 1
                        # Let the process continue running in background
                        # Don't wait for it or communicate with it
                    else:
                        # Process failed to start
                        stdout, stderr = process.communicate(timeout=5)
                        print(f"❌ Worker process {process.pid} failed to start for {server.name} (exit code: {process.returncode})")
                        print(f"STDOUT: {stdout}")
                        print(f"STDERR: {stderr}")
                        failed_launches.append(server.name)

                except subprocess.TimeoutExpired:
                    print(f"⚠️ Worker process {process.pid} timed out during startup")
                except Exception as e:
                    print(f"❌ Failed to create worker process for server {server.name}: {e}")
                    import traceback
                    traceback.print_exc()

            except Exception as e:
                print(f"❌ Failed to launch worker for server {server.name}: {e}")
                failed_launches.append(server.name)
                import traceback
                traceback.print_exc()
        
        # Print summary
        print(f"\n{'='*60}")
        print(f"📊 Worker Launch Summary:")
        print(f"  ✅ Successful launches: {successful_launches}/{len(selected_servers)}")
        if failed_launches:
            print(f"  ❌ Failed launches: {', '.join(failed_launches)}")
        print(f"{'='*60}\n")

    except Exception as e:
        print(f"❌ Error launching worker processes: {e}")
        import traceback
        traceback.print_exc()

async def _monitor_multi_server_job(job_id: UUID, checkpoint_manager: CheckpointManager):
    """Monitor multi-server job progress until completion."""
    import asyncio
    from ...data_access.judge_task_queue import JudgeTaskQueueRepository
    from ...data_access.worker_heartbeats import WorkerHeartbeatsRepository

    logger.info(f"🎯 Monitor started for job {job_id}")

    try:
        queue_repo = JudgeTaskQueueRepository()
        heartbeat_repo = WorkerHeartbeatsRepository()

        iteration = 0
        while True:
            iteration += 1
            # Get job progress
            progress = queue_repo.get_job_progress(job_id)
            
            logger.debug(f"Monitor iteration {iteration} for job {job_id}: progress={progress}")

            if progress:
                # Update job progress
                await checkpoint_manager.update_progress(
                    job_id,
                    progress['completed_tasks'],
                    progress['total_tasks']
                )

                # Check if job is complete
                completed = progress.get('completed_tasks', 0)
                total = progress.get('total_tasks', 0)
                pending = progress.get('pending_tasks', 0)
                in_prog = progress.get('in_progress_tasks', 0)
                
                logger.info(f"📊 Job {job_id} progress: {completed}/{total} completed, {pending} pending, {in_prog} in-progress")
                
                if completed >= total and total > 0:
                    # Mark job as complete and terminate workers
                    logger.info(f"✅ Job {job_id} COMPLETE: {completed}/{total} tasks finished")
                    if progress['failed_tasks'] > 0:
                        # Mark job as completed with failures
                        await checkpoint_manager.complete_job(
                            job_id,
                            f"Completed with {progress['failed_tasks']} failed tasks out of {progress['total_tasks']} total tasks"
                        )
                    else:
                        # Mark job as fully successful
                        await checkpoint_manager.complete_job(
                            job_id,
                            f"Successfully completed {progress['total_tasks']} tasks"
                        )
                    
                    # Terminate all worker processes for this job
                    logger.info(f"🛑 Terminating worker processes for completed job {job_id}")
                    await _signal_workers_cancel(job_id)
                    logger.info(f"🎉 Job {job_id} monitoring complete - exiting monitor loop")
                    break

            # Check for active workers - fallback completion detection
            active_workers = heartbeat_repo.get_active_workers(job_id)
            logger.debug(f"Active workers for job {job_id}: {len(active_workers) if active_workers else 0}")
            
            if not active_workers and progress and progress['pending_tasks'] == 0 and progress['in_progress_tasks'] == 0:
                # No active workers and no pending/in-progress tasks - mark as complete
                logger.info(f"✅ Job {job_id} detected complete via worker shutdown (no active workers, no pending tasks)")
                if progress['failed_tasks'] > 0:
                    await checkpoint_manager.complete_job(
                        job_id,
                        f"Completed with {progress['failed_tasks']} failed tasks out of {progress['total_tasks']} total tasks"
                    )
                else:
                    await checkpoint_manager.complete_job(
                        job_id,
                        f"Successfully completed {progress['completed_tasks']} tasks"
                    )
                
                # Ensure all worker processes are terminated
                logger.info(f"🛑 Terminating any remaining worker processes for job {job_id}")
                await _signal_workers_cancel(job_id)
                logger.info(f"🎉 Job {job_id} monitoring complete - exiting monitor loop")
                break

            # Wait before next check (5 seconds for faster completion detection)
            await asyncio.sleep(5)

    except Exception as e:
        logger.error(f"❌ Monitor for job {job_id} crashed: {e}", exc_info=True)
        try:
            await checkpoint_manager.fail_job(job_id, f"Monitoring failed: {str(e)}")
        except Exception as fail_error:
            logger.error(f"Failed to mark job as failed: {fail_error}")
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
        configuration={
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

async def _start_bulk_judge_operation(
    request: BulkJudgeRequest,
    background_tasks: BackgroundTasks
) -> JobStartResponse:
    """Core bulk judge operation logic that can be called from multiple endpoints."""
    if not request.all_profiles and not request.profile_ids:
        raise HTTPException(
            status_code=400,
            detail="Either all_profiles must be true or profile_ids must be provided"
        )

    pool = await get_connection_pool()
    checkpoint_manager = CheckpointManager(pool)

    # Check for job conflicts before starting
    conflict_data = await _check_job_conflicts()
    if conflict_data["has_conflicts"]:
        # Smart conflict detection:
        # - Allow multi-server bulk judge jobs to run concurrently (different Ollama servers)
        # - Block if single-server bulk judge is running (same resources)
        # - Block if other resource-intensive jobs are running (newsletters, mindmaps, podcasts)
        
        # Check for non-bulk-judge resource-intensive jobs
        non_bulk_judge_conflicts = [
            job for job in conflict_data["conflicts"]
            if job["job_type"] in ['harvest_judge', 'newsletter_generation', 'mindmap_generation', 'podcast_generation']
        ]
        
        # Check for single-server bulk judge jobs
        single_server_bulk_judge = [
            job for job in conflict_data["conflicts"]
            if job["job_type"] == 'bulk_judge' and not job.get("multi_server", False)
        ]
        
        # Block if there are any non-bulk-judge resource-intensive jobs
        if non_bulk_judge_conflicts:
            conflict_details = "; ".join([f"{job['job_type']} ({job['description']})" for job in non_bulk_judge_conflicts])
            raise HTTPException(
                status_code=409,
                detail=f"Resource conflict with running jobs: {conflict_details}. " +
                       f"Recommendation: {conflict_data['recommendations'][0] if conflict_data['recommendations'] else 'Wait for jobs to complete or cancel them.'}"
            )
        
        # Block if there's a single-server bulk judge running and we're NOT using multi-server mode
        if single_server_bulk_judge and not request.use_multi_server:
            conflict_details = "; ".join([f"{job['job_type']} ({job['description']})" for job in single_server_bulk_judge])
            raise HTTPException(
                status_code=409,
                detail=f"A single-server bulk judge job is running: {conflict_details}. " +
                       f"Either wait for it to complete, or enable multi-server mode to process in parallel."
            )

    # Validate multi-server configuration if enabled
    selected_servers = []
    if request.use_multi_server:
        print(f"🔍 Multi-server mode enabled, requested server_ids: {request.server_ids}")
        server_repo = OllamaServersRepository()
        available_servers = server_repo.get_enabled()
        print(f"📋 Found {len(available_servers)} available servers: {[(s.id, s.name, s.url) for s in available_servers]}")

        if not available_servers:
            raise HTTPException(
                status_code=400,
                detail="Multi-server mode requested but no enabled Ollama servers found. Please configure and enable servers in Settings."
            )

        if request.server_ids:
            # Validate specific server IDs
            server_id_set = set(request.server_ids)
            available_ids = {server.id for server in available_servers}
            invalid_ids = server_id_set - available_ids

            if invalid_ids:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid server IDs: {list(invalid_ids)}. Available server IDs: {list(available_ids)}"
                )

            selected_servers = [server for server in available_servers if server.id in request.server_ids]
            print(f"🎯 Selected {len(selected_servers)} servers by ID filter: {[(s.id, s.name, s.url) for s in selected_servers]}")
        else:
            # Use all enabled servers
            selected_servers = available_servers
            print(f"🎯 Using all {len(selected_servers)} enabled servers: {[(s.id, s.name, s.url) for s in selected_servers]}")

        if not selected_servers:
            raise HTTPException(
                status_code=400,
                detail="No valid servers available for multi-server processing"
            )

    # Suspend scheduled tasks if requested
    suspended_tasks_snapshot = []
    if request.suspend_scheduled_tasks:
        try:
            suspended_tasks_snapshot = await _suspend_scheduled_tasks()
        except Exception as e:
            # Log but don't fail - scheduler suspension is not critical
            print(f"Warning: Failed to suspend scheduled tasks: {e}")

    # Create job record with enhanced configuration
    configuration = {
        "profile_ids": request.profile_ids,
        "all_profiles": request.all_profiles,
        "limit": request.limit,
        "start_date": request.start_date,
        "end_date": request.end_date,
        "batch_size": request.batch_size,
        "use_multi_server": request.use_multi_server,
        "server_ids": request.server_ids,
        "request_timeout_sec": request.request_timeout_sec,
        "max_retries": request.max_retries,
        "suspend_scheduled_tasks": request.suspend_scheduled_tasks,
        "overwrite_existing": request.overwrite_existing,
        "suspended_tasks_snapshot": suspended_tasks_snapshot,
        "selected_servers": [{"id": s.id, "name": s.name, "url": s.url} for s in selected_servers] if selected_servers else []
    }

    # Create the job and get the assigned job ID
    created_job_id = await checkpoint_manager.create_job(
        job_type="bulk_judge",
        configuration=configuration
    )

    # Start appropriate background task
    if request.use_multi_server:
        # Preflight: ensure downloads/embeddings done before spinning up workers
        # Download new papers from arXiv for this range and insert them
        # Skip download only if overwrite_existing is False and papers exist
        try:
            dl_stats = _download_arxiv_for_range(
                request.start_date, 
                request.end_date,
                overwrite_existing=request.overwrite_existing
            )
            logger.info(f"Preflight download stats: {dl_stats}")
        except Exception as pre_dle:
            logger.warning(f"Preflight arXiv download failed or partial: {pre_dle}")

        # Then, ensure embeddings for all papers in range
        try:
            pre_embedded = _ensure_embeddings_for_range(request.start_date, request.end_date)
            logger.info(f"Preflight embeddings ensured for {pre_embedded} papers")
        except Exception as pre_e:
            logger.warning(f"Preflight embedding stage failed or partial: {pre_e}")

        # Enqueue tasks synchronously (dynamic pool; no server pre-assignment)
        queue_producer = JudgeQueueProducer()
        profile_ids_int = [int(pid) for pid in request.profile_ids] if request.profile_ids else None
        result = queue_producer.enqueue_bulk_judge_job(
            job_id=created_job_id,
            profile_ids=profile_ids_int,
            date_from=request.start_date,
            date_to=request.end_date,
            overwrite_existing=request.overwrite_existing,
            create_processing_job=False,
            server_urls=None  # dynamic pooling
        )
        
        print(f"📊 Queue producer result: {result}")
        
        # Launch workers immediately (not in background task)
        await _launch_worker_processes(created_job_id, selected_servers, request.request_timeout_sec, request.max_retries)
        
        # Use queue-based multi-server processing
        background_tasks.add_task(
            _monitor_multi_server_job,
            created_job_id,
            checkpoint_manager
        )
    else:
        # Use traditional single-server processing
        background_tasks.add_task(
            run_bulk_judge_task,
            created_job_id,
            request,
            checkpoint_manager
        )

    # Generate descriptive message
    profile_desc = "all profiles" if request.all_profiles else f"{len(request.profile_ids)} profiles"
    server_desc = f" using {len(selected_servers)} servers" if request.use_multi_server else " (single server)"

    return JobStartResponse(
        job_id=created_job_id,
        job_type="bulk_judge",
        status="running",
        message=f"Bulk judge operation started for {profile_desc}{server_desc}"
    )

@router.post("/bulk-judge", response_model=JobStartResponse)
async def start_bulk_judge(
    request: BulkJudgeRequest,
    background_tasks: BackgroundTasks
) -> JobStartResponse:
    """Start a bulk judge operation with multi-server support."""
    return await _start_bulk_judge_operation(request, background_tasks)

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
        configuration={
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
        configuration={
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

# Job Control Endpoints
@router.post("/job/{job_id}/pause", response_model=Dict[str, Any])
async def pause_job(job_id: UUID) -> Dict[str, Any]:
    """Pause a running bulk judge job."""
    pool = await get_connection_pool()
    checkpoint_manager = CheckpointManager(pool)

    try:
        # Update job status to paused
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE processing_jobs SET status = 'paused' WHERE id = $1",
                job_id
            )

        # For multi-server jobs, signal workers to pause
        if await _is_multi_server_job(job_id, pool):
            await _signal_workers_pause(job_id)

        return {
            "success": True,
            "job_id": str(job_id),
            "status": "paused",
            "message": "Job paused successfully"
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to pause job: {str(e)}"
        )

@router.post("/job/{job_id}/resume", response_model=Dict[str, Any])
async def resume_job(
    job_id: UUID,
    background_tasks: BackgroundTasks
) -> Dict[str, Any]:
    """Resume a paused bulk judge job."""
    pool = await get_connection_pool()
    checkpoint_manager = CheckpointManager(pool)

    try:
        # Get job configuration
        async with pool.acquire() as conn:
            job_row = await conn.fetchrow(
                "SELECT configuration FROM processing_jobs WHERE id = $1",
                job_id
            )
            
            if not job_row:
                raise HTTPException(status_code=404, detail="Job not found")
            
            configuration = job_row['configuration']
            
            # Update job status to running
            await conn.execute(
                "UPDATE processing_jobs SET status = 'running' WHERE id = $1",
                job_id
            )

        # For multi-server jobs, restart workers and monitoring
        if await _is_multi_server_job(job_id, pool):
            logger.info(f"🔄 Resuming multi-server job {job_id}")
            
            from ...data_access.ollama_servers import OllamaServersRepository
            server_repo = OllamaServersRepository()
            
            # Get selected servers from configuration, or use all enabled servers as fallback
            selected_servers = []
            if configuration and isinstance(configuration, dict):
                server_configs = configuration.get('selected_servers', [])
                
                if server_configs:
                    # Reconstruct server objects from saved configuration
                    for server_cfg in server_configs:
                        # Create a simple object with the needed attributes
                        class ServerObj:
                            def __init__(self, id, name, url):
                                self.id = id
                                self.name = name
                                self.url = url
                        
                        selected_servers.append(ServerObj(
                            server_cfg['id'],
                            server_cfg['name'],
                            server_cfg['url']
                        ))
                    logger.info(f"📋 Using {len(selected_servers)} servers from job configuration")
            
            # Fallback: use all currently enabled servers if no servers in config
            if not selected_servers:
                logger.warning(f"No servers found in job configuration, using all enabled servers as fallback")
                selected_servers = server_repo.get_enabled()
                
                if not selected_servers:
                    raise HTTPException(
                        status_code=400,
                        detail="No enabled Ollama servers found. Please enable servers in Settings before resuming."
                    )
                
                logger.info(f"📋 Using {len(selected_servers)} enabled servers as fallback")
            
            # Relaunch worker processes
            request_timeout = configuration.get('request_timeout_sec', 300) if configuration and isinstance(configuration, dict) else 300
            max_retries = configuration.get('max_retries', 3) if configuration and isinstance(configuration, dict) else 3
            
            logger.info(f"🚀 Relaunching {len(selected_servers)} workers for job {job_id}")
            await _launch_worker_processes(job_id, selected_servers, request_timeout, max_retries)
            
            # Restart monitoring task in background
            logger.info(f"👁️ Restarting monitoring for job {job_id}")
            background_tasks.add_task(
                _monitor_multi_server_job,
                job_id,
                checkpoint_manager
            )
            
            return {
                "success": True,
                "job_id": str(job_id),
                "status": "running",
                "message": f"Job resumed with {len(selected_servers)} workers and monitoring restarted"
            }
        else:
            # Single-server jobs don't support pause/resume yet
            return {
                "success": True,
                "job_id": str(job_id),
                "status": "running",
                "message": "Job status updated to running (single-server jobs cannot be fully resumed)"
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to resume job {job_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to resume job: {str(e)}"
        )

@router.post("/job/{job_id}/force-complete", response_model=Dict[str, Any])
async def force_complete_job(job_id: UUID) -> Dict[str, Any]:
    """Force a stuck job to complete status and terminate workers."""
    from ...data_access.judge_task_queue import JudgeTaskQueueRepository
    
    pool = await get_connection_pool()
    checkpoint_manager = CheckpointManager(pool)

    try:
        # Get current queue status
        queue_repo = JudgeTaskQueueRepository()
        progress = queue_repo.get_job_progress(job_id)
        
        if not progress:
            raise HTTPException(status_code=404, detail="Job progress not found")
        
        # Mark job as completed
        await checkpoint_manager.complete_job(
            job_id,
            f"Force completed: {progress['completed_tasks']}/{progress['total_tasks']} tasks, "
            f"{progress['failed_tasks']} failed"
        )
        
        # Terminate all worker processes
        if await _is_multi_server_job(job_id, pool):
            await _signal_workers_cancel(job_id)
        
        # Restore suspended tasks
        await _restore_scheduled_tasks_on_cancel(job_id, pool)

        return {
            "success": True,
            "job_id": str(job_id),
            "status": "completed",
            "message": f"Job force completed: {progress['completed_tasks']}/{progress['total_tasks']} tasks",
            "progress": progress
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to force complete job: {str(e)}"
        )

@router.post("/job/{job_id}/cancel", response_model=Dict[str, Any])
async def cancel_job(job_id: UUID) -> Dict[str, Any]:
    """Cancel a running bulk judge job."""
    pool = await get_connection_pool()
    checkpoint_manager = CheckpointManager(pool)

    try:
        # Update job status to canceled
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE processing_jobs SET status = 'canceled', cancel_requested = TRUE WHERE id = $1",
                job_id
            )

        # For multi-server jobs, signal workers to cancel
        if await _is_multi_server_job(job_id, pool):
            await _signal_workers_cancel(job_id)

        # Restore suspended tasks
        await _restore_scheduled_tasks_on_cancel(job_id, pool)

        return {
            "success": True,
            "job_id": str(job_id),
            "status": "canceled",
            "message": "Job canceled successfully"
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to cancel job: {str(e)}"
        )

@router.get("/job/{job_id}/metrics", response_model=Dict[str, Any])
async def get_job_metrics(job_id: UUID) -> Dict[str, Any]:
    """Get detailed metrics for a bulk judge job."""
    pool = await get_connection_pool()

    try:
        async with pool.acquire() as conn:
            # Get job info
            job_row = await conn.fetchrow(
                "SELECT * FROM processing_jobs WHERE id = $1",
                job_id
            )

            if not job_row:
                raise HTTPException(status_code=404, detail="Job not found")

            metrics = {
                "job_id": str(job_id),
                "job_type": job_row['job_type'],
                "status": job_row['status'],
                "progress": {
                    "current": job_row['progress_current'] or 0,
                    "total": job_row['progress_total'] or 0,
                    "percent": round((job_row['progress_current'] or 0) / (job_row['progress_total'] or 1) * 100, 1)
                },
                "timestamps": {
                    "started_at": job_row['started_at'].isoformat() if job_row['started_at'] else None,
                    "completed_at": job_row['completed_at'].isoformat() if job_row['completed_at'] else None,
                    "last_checkpoint_at": job_row['last_checkpoint_at'].isoformat() if job_row['last_checkpoint_at'] else None
                },
                "error_message": job_row['error_message']
            }

            # Add multi-server specific metrics (for both active and completed/failed multi-server jobs)
            if await _is_multi_server_job(job_id, pool):
                from ...data_access.judge_task_queue import JudgeTaskQueueRepository
                from ...data_access.worker_heartbeats import WorkerHeartbeatsRepository

                queue_repo = JudgeTaskQueueRepository()
                heartbeat_repo = WorkerHeartbeatsRepository()

                queue_progress = queue_repo.get_job_progress(job_id)
                all_workers = heartbeat_repo.get_all_workers(job_id, include_failed=True)

                if queue_progress:
                    # Override main progress with queue metrics for multi-server jobs
                    metrics["progress"] = {
                        "current": queue_progress['completed_tasks'],
                        "total": queue_progress['total_tasks'],
                        "percent": round((queue_progress['completed_tasks'] / queue_progress['total_tasks'] * 100) if queue_progress['total_tasks'] > 0 else 0, 1)
                    }
                    
                    metrics["queue_metrics"] = {
                        "pending_tasks": queue_progress['pending_tasks'],
                        "in_progress_tasks": queue_progress['in_progress_tasks'],
                        "completed_tasks": queue_progress['completed_tasks'],
                        "failed_tasks": queue_progress['failed_tasks'],
                        "total_tasks": queue_progress['total_tasks']
                    }

                if all_workers:
                    metrics["worker_metrics"] = []
                    for worker in all_workers:
                        worker_data = {
                            "worker_id": worker.worker_id,
                            "server_url": worker.server_url,
                            "status": worker.status,
                            "tasks_processed": worker.tasks_processed,
                            "last_heartbeat": worker.last_heartbeat.isoformat() if worker.last_heartbeat else None,
                            "failure_reason": worker.failure_reason,
                            "failure_count": worker.failure_count,
                            "last_failure_at": worker.last_failure_at.isoformat() if worker.last_failure_at else None
                        }
                        metrics["worker_metrics"].append(worker_data)

            return metrics

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get job metrics: {str(e)}"
        )

# Helper functions for job control
async def _is_multi_server_job(job_id: UUID, pool) -> bool:
    """Check if a job is using multi-server processing."""
    async with pool.acquire() as conn:
        configuration = await conn.fetchval(
            "SELECT configuration FROM processing_jobs WHERE id = $1",
            job_id
        )

        if configuration:
            # Handle both dict and JSON string configurations
            if isinstance(configuration, str):
                try:
                    import json
                    configuration = json.loads(configuration)
                except (json.JSONDecodeError, TypeError):
                    return False
            
            if isinstance(configuration, dict):
                return configuration.get('use_multi_server', False)

    return False

async def _signal_workers_pause(job_id: UUID):
    """Signal workers to pause processing."""
    try:
        from ...data_access.worker_heartbeats import WorkerHeartbeatsRepository
        heartbeat_repo = WorkerHeartbeatsRepository()

        # Update worker status to paused
        active_workers = heartbeat_repo.get_active_workers(job_id)
        for worker in active_workers:
            # This would signal the worker process to pause
            # Implementation depends on inter-process communication method
            pass

    except Exception as e:
        print(f"Error signaling workers to pause: {e}")

async def _signal_workers_resume(job_id: UUID):
    """Signal workers to resume processing."""
    try:
        from ...data_access.worker_heartbeats import WorkerHeartbeatsRepository
        heartbeat_repo = WorkerHeartbeatsRepository()

        # Update worker status to active
        active_workers = heartbeat_repo.get_active_workers(job_id)
        for worker in active_workers:
            # This would signal the worker process to resume
            # Implementation depends on inter-process communication method
            pass

    except Exception as e:
        print(f"Error signaling workers to resume: {e}")

async def _signal_workers_cancel(job_id: UUID):
    """Signal workers to cancel processing and terminate processes."""
    import subprocess
    import signal
    
    try:
        from ...data_access.worker_heartbeats import WorkerHeartbeatsRepository
        heartbeat_repo = WorkerHeartbeatsRepository()

        # Update worker status to canceled in database
        active_workers = heartbeat_repo.get_active_workers(job_id)
        for worker in active_workers:
            heartbeat_repo.update_worker_status(worker.worker_id, "canceled")

        # Find and terminate worker processes
        try:
            # Get all judge_worker processes for this job
            result = subprocess.run([
                "ps", "aux"
            ], capture_output=True, text=True, check=True)
            
            processes_to_kill = []
            for line in result.stdout.split('\n'):
                if 'theseus_insight.workers.judge_worker' in line and str(job_id) in line:
                    # Extract PID (second column)
                    parts = line.split()
                    if len(parts) > 1:
                        try:
                            pid = int(parts[1])
                            processes_to_kill.append(pid)
                        except ValueError:
                            continue
            
            # Terminate processes gracefully first, then force kill if needed
            for pid in processes_to_kill:
                try:
                    print(f"🛑 Terminating worker process {pid} for job {job_id}")
                    subprocess.run(["kill", "-TERM", str(pid)], check=False)
                except Exception as e:
                    print(f"Warning: Could not terminate process {pid}: {e}")
            
            # Wait a moment, then force kill any remaining processes
            import asyncio
            await asyncio.sleep(2)
            
            for pid in processes_to_kill:
                try:
                    # Check if process still exists
                    subprocess.run(["kill", "-0", str(pid)], check=True, capture_output=True)
                    # If we get here, process still exists, force kill it
                    print(f"🔥 Force killing worker process {pid} for job {job_id}")
                    subprocess.run(["kill", "-KILL", str(pid)], check=False)
                except subprocess.CalledProcessError:
                    # Process already terminated, which is what we want
                    pass
                except Exception as e:
                    print(f"Warning: Could not force kill process {pid}: {e}")
                    
        except Exception as e:
            print(f"Error terminating worker processes: {e}")

        # Clean up database resources
        pool = await get_connection_pool()
        async with pool.acquire() as conn:
            # Mark all tasks for this job as canceled
            await conn.execute(
                """
                UPDATE judge_task_queue 
                SET status = 'canceled', updated_at = NOW()
                WHERE job_id = $1 AND status IN ('pending', 'leased', 'in_progress')
                """,
                job_id
            )
            
            # Mark worker heartbeats as inactive instead of deleting (preserve failure history)
            await conn.execute(
                """
                UPDATE worker_heartbeats 
                SET status = 'inactive', 
                    last_heartbeat = NOW()
                WHERE job_id = $1 AND status != 'failed'
                """,
                job_id
            )
            
        print(f"✅ Cleaned up resources for job {job_id}")

    except Exception as e:
        print(f"Error signaling workers to cancel: {e}")
        import traceback
        traceback.print_exc()

async def _cleanup_failed_job(job_id: UUID):
    """Clean up resources for a failed job."""
    try:
        print(f"🧹 Cleaning up failed job {job_id}")
        
        # Use the same cleanup logic as cancellation
        await _signal_workers_cancel(job_id)
        
        # Update job status to failed if not already
        pool = await get_connection_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE processing_jobs 
                SET status = 'failed', completed_at = NOW()
                WHERE id = $1 AND status IN ('running', 'pending', 'paused')
                """,
                job_id
            )
        
        # Restore scheduled tasks
        await _restore_scheduled_tasks_on_cancel(job_id, pool)
        
        print(f"✅ Failed job {job_id} cleaned up")
        
    except Exception as e:
        print(f"Error cleaning up failed job {job_id}: {e}")
        import traceback
        traceback.print_exc()

# Note: cleanup_orphaned_processes() has been moved to startup_cleanup.py
# for better organization and separation of concerns

@router.post("/cleanup-orphaned-processes")
async def cleanup_orphaned_processes_endpoint() -> Dict[str, Any]:
    """
    Manually trigger cleanup of orphaned worker processes and stuck jobs.
    
    This endpoint allows manual triggering of the startup cleanup logic.
    Useful for clearing stuck jobs without restarting the API.
    """
    try:
        from ...startup_cleanup import cleanup_stuck_jobs_and_processes
        await cleanup_stuck_jobs_and_processes()
        return {
            "success": True,
            "message": "Orphaned processes and stuck jobs cleaned up successfully"
        }
    except Exception as e:
        print(f"Error cleaning up orphaned processes: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cleanup orphaned processes: {str(e)}")

@router.post("/restart-failed-workers/{job_id}")
async def restart_failed_workers(job_id: UUID) -> Dict[str, Any]:
    """Restart all failed workers for a specific job."""
    try:
        from ...data_access.worker_heartbeats import WorkerHeartbeatsRepository
        
        # Get all failed workers for this job
        failed_workers = WorkerHeartbeatsRepository.get_all_workers(job_id, include_failed=True)
        failed_workers = [w for w in failed_workers if w.status == 'failed']
        
        if not failed_workers:
            return {
                "message": "No failed workers found for this job",
                "job_id": str(job_id),
                "restarted_workers": []
            }
        
        # Check if the job is still active
        pool = await get_connection_pool()
        async with pool.acquire() as conn:
            job_row = await conn.fetchrow(
                "SELECT status FROM processing_jobs WHERE id = $1",
                job_id
            )
            
            if not job_row or job_row['status'] not in ['running', 'pending']:
                return {
                    "message": "Cannot restart workers for inactive job",
                    "job_id": str(job_id),
                    "job_status": job_row['status'] if job_row else 'not_found',
                    "restarted_workers": []
                }
        
        restarted_workers = []
        for worker in failed_workers:
            try:
                # Reset worker status to pending for retry
                success = WorkerHeartbeatsRepository.retry_failed_worker(
                    worker.worker_id, 
                    worker.server_url, 
                    job_id
                )
                
                if success:
                    # Launch new worker process
                    await _launch_single_worker(
                        job_id=job_id,
                        server_url=worker.server_url,
                        request_timeout_sec=30,
                        max_retries=3
                    )
                    
                    restarted_workers.append({
                        "worker_id": worker.worker_id,
                        "server_url": worker.server_url,
                        "previous_failure_reason": worker.failure_reason,
                        "failure_count": worker.failure_count
                    })
                    
                    logger.info(f"Restarted failed worker {worker.worker_id} for job {job_id}")
                
            except Exception as e:
                logger.error(f"Failed to restart worker {worker.worker_id}: {e}")
        
        return {
            "message": f"Restarted {len(restarted_workers)} failed workers",
            "job_id": str(job_id),
            "total_failed_workers": len(failed_workers),
            "restarted_workers": restarted_workers
        }
        
    except Exception as e:
        logger.error(f"Failed to restart failed workers: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to restart workers: {str(e)}")

async def _restore_scheduled_tasks_on_cancel(job_id: UUID, pool):
    """Restore suspended tasks when job is canceled."""
    try:
        async with pool.acquire() as conn:
            configuration = await conn.fetchval(
                "SELECT configuration FROM processing_jobs WHERE id = $1",
                job_id
            )

            if configuration and isinstance(configuration, dict):
                suspend_scheduled_tasks = configuration.get('suspend_scheduled_tasks', False)
                if suspend_scheduled_tasks:
                    suspended_tasks = configuration.get('suspended_tasks_snapshot', [])

                    # Restore tasks using scheduler
                    for task_info in suspended_tasks:
                        try:
                            jobs = scheduler.scheduler.get_jobs()
                            for job in jobs:
                                if hasattr(job, 'id') and job.id == task_info.get('job_id'):
                                    job.resume()
                                    break
                        except Exception as e:
                            print(f"Error restoring task {task_info.get('job_id')}: {e}")

    except Exception as e:
        print(f"Error restoring scheduled tasks on cancel: {e}")

@router.post("/conflict-check", response_model=Dict[str, Any])
async def check_job_conflicts() -> Dict[str, Any]:
    """Check for potential conflicts with running jobs."""
    pool = await get_connection_pool()

    try:
        async with pool.acquire() as conn:
            # Check for running bulk judge jobs
            running_jobs = await conn.fetch(
                """
                SELECT id, job_type, started_at, configuration
                FROM processing_jobs
                WHERE status IN ('running', 'pending')
                AND job_type IN ('bulk_judge', 'harvest_judge', 'newsletter_generation', 'mindmap_generation', 'podcast_generation')
                """
            )

            conflicts = []
            bulk_judge_running = False

            for job in running_jobs:
                job_info = {
                    "job_id": str(job['id']),
                    "job_type": job['job_type'],
                    "started_at": job['started_at'].isoformat() if job['started_at'] else None,
                    "description": _get_job_description(job['job_type'], job['configuration'])
                }

                if job['job_type'] == 'bulk_judge':
                    bulk_judge_running = True
                    # Check if it's a multi-server job
                    configuration = job['configuration']
                    if configuration and isinstance(configuration, dict) and configuration.get('use_multi_server', False):
                        job_info["multi_server"] = True
                        job_info["servers"] = configuration.get('selected_servers', [])

                conflicts.append(job_info)

            return {
                "has_conflicts": len(conflicts) > 0,
                "bulk_judge_running": bulk_judge_running,
                "conflicts": conflicts,
                "recommendations": _get_conflict_recommendations(conflicts, bulk_judge_running)
            }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check job conflicts: {str(e)}"
        )

@router.get("/active-jobs", response_model=Dict[str, Any])
async def get_active_jobs() -> Dict[str, Any]:
    """Get list of active bulk jobs with their status."""
    pool = await get_connection_pool()

    try:
        async with pool.acquire() as conn:
            active_jobs = await conn.fetch(
                """
                SELECT
                    id, job_type, status, progress_current, progress_total,
                    CASE
                        WHEN progress_total > 0 THEN (progress_current::float / progress_total * 100)
                        ELSE 0
                    END as progress_percent,
                    started_at, last_checkpoint_at, configuration
                FROM processing_jobs
                WHERE status IN ('running', 'pending', 'paused')
                AND job_type = 'bulk_judge'
                ORDER BY started_at DESC
                """
            )

            jobs = []
            for job in active_jobs:
                job_info = {
                    "job_id": str(job['id']),
                    "job_type": job['job_type'],
                    "status": job['status'],
                    "progress": {
                        "current": job['progress_current'] or 0,
                        "total": job['progress_total'] or 0,
                        "percent": round(job['progress_percent'], 1)
                    },
                    "started_at": job['started_at'].isoformat() if job['started_at'] else None,
                    "last_checkpoint_at": job['last_checkpoint_at'].isoformat() if job['last_checkpoint_at'] else None
                }

                # Add multi-server specific info
                configuration = job['configuration']
                if configuration:
                    # Handle both dict and JSON string configurations
                    if isinstance(configuration, str):
                        try:
                            import json
                            configuration = json.loads(configuration)
                        except (json.JSONDecodeError, TypeError):
                            configuration = {}
                    
                    if isinstance(configuration, dict):
                        if configuration.get('use_multi_server', False):
                            job_info["multi_server"] = True
                            job_info["servers"] = configuration.get('selected_servers', [])
                        else:
                            job_info["multi_server"] = False

                        job_info["profile_count"] = len(configuration.get('profile_ids', [])) if configuration.get('profile_ids') else ("all" if configuration.get('all_profiles') else 0)
                    else:
                        job_info["multi_server"] = False

                jobs.append(job_info)

            return {
                "active_jobs": jobs,
                "count": len(jobs)
            }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get active jobs: {str(e)}"
        )

@router.get("/server-metrics", response_model=Dict[str, Any])
async def get_server_metrics() -> Dict[str, Any]:
    """Get performance metrics for all Ollama servers."""
    try:
        from ...data_access.ollama_servers import OllamaServersRepository
        server_repo = OllamaServersRepository()

        servers = server_repo.get_all()
        server_metrics = []

        for server in servers:
            metrics = {
                "id": server.id,
                "name": server.name,
                "url": server.url,
                "enabled": server.enabled,
                "status": "unknown",
                "latency_ms": server.last_test_latency_ms,
                "last_tested": server.last_tested_at.isoformat() if server.last_tested_at else None
            }

            # Determine status
            if not server.enabled:
                metrics["status"] = "disabled"
            elif server.last_test_ok is not None:
                metrics["status"] = "healthy" if server.last_test_ok else "unhealthy"
            else:
                metrics["status"] = "not_tested"

            server_metrics.append(metrics)

        return {
            "servers": server_metrics,
            "summary": {
                "total": len(server_metrics),
                "enabled": len([s for s in server_metrics if s["enabled"]]),
                "healthy": len([s for s in server_metrics if s["status"] == "healthy"]),
                "unhealthy": len([s for s in server_metrics if s["status"] == "unhealthy"])
            }
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get server metrics: {str(e)}"
        )

@router.get("/queue-status", response_model=Dict[str, Any])
async def get_queue_status() -> Dict[str, Any]:
    """Get current queue status and depth."""
    try:
        from ...data_access.judge_task_queue import JudgeTaskQueueRepository
        queue_repo = JudgeTaskQueueRepository()

        # Get overall queue statistics
        queue_stats = queue_repo.get_queue_stats()

        # Get active jobs with queue info
        active_jobs = queue_repo.get_active_jobs_with_queue_info()

        return {
            "queue_stats": queue_stats,
            "active_jobs": active_jobs,
            "timestamp": "2025-08-29T08:46:00Z"  # Would be datetime.utcnow().isoformat()
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get queue status: {str(e)}"
        )

@router.get("/job-history", response_model=Dict[str, Any])
async def get_job_history(
    limit: int = Query(50, description="Maximum number of jobs to return"),
    job_type: Optional[str] = Query(None, description="Filter by job type")
) -> Dict[str, Any]:
    """Get historical job data including completed, failed, and canceled jobs."""
    pool = await get_connection_pool()

    try:
        async with pool.acquire() as conn:
            # Get job history with status counts
            query = """
                SELECT
                    id, job_type, status, configuration, state,
                    started_at, completed_at, created_at,
                    CASE
                        WHEN completed_at IS NOT NULL AND started_at IS NOT NULL
                        THEN EXTRACT(EPOCH FROM (completed_at - started_at))
                        ELSE NULL
                    END as duration_seconds,
                    error_message
                FROM processing_jobs
                WHERE status IN ('completed', 'failed', 'canceled')
            """

            # Handle job_type filtering
            job_type_value = job_type if isinstance(job_type, str) else None

            if job_type_value:
                query += " AND job_type = $1"
                rows = await conn.fetch(query + " ORDER BY completed_at DESC NULLS LAST, started_at DESC LIMIT $2", job_type_value, limit)
            else:
                rows = await conn.fetch(query + " ORDER BY completed_at DESC NULLS LAST, started_at DESC LIMIT $1", limit)

            jobs = []
            for row in rows:
                job_info = {
                    'job_id': str(row['id']),
                    'job_type': row['job_type'],
                    'status': row['status'],
                    'configuration': row['configuration'],
                    'state': row['state'],
                    'started_at': row['started_at'].isoformat() if row['started_at'] else None,
                    'completed_at': row['completed_at'].isoformat() if row['completed_at'] else None,
                    'created_at': row['created_at'].isoformat() if row['created_at'] else None,
                    'duration_seconds': row['duration_seconds'],
                    'error_message': row['error_message']
                }
                jobs.append(job_info)

            # Get summary statistics
            summary_query = """
                SELECT
                    COUNT(*) as total_jobs,
                    COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_jobs,
                    COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_jobs,
                    COUNT(CASE WHEN status = 'canceled' THEN 1 END) as canceled_jobs,
                    AVG(CASE
                        WHEN completed_at IS NOT NULL AND started_at IS NOT NULL
                        THEN EXTRACT(EPOCH FROM (completed_at - started_at))
                        ELSE NULL
                    END) as avg_duration_seconds
                FROM processing_jobs
                WHERE status IN ('completed', 'failed', 'canceled')
            """

            if job_type_value:
                summary_query += " AND job_type = $1"
                summary_row = await conn.fetchrow(summary_query, job_type_value)
            else:
                summary_row = await conn.fetchrow(summary_query)

            return {
                'jobs': jobs,
                'summary': {
                    'total_jobs': summary_row['total_jobs'] or 0,
                    'completed_jobs': summary_row['completed_jobs'] or 0,
                    'failed_jobs': summary_row['failed_jobs'] or 0,
                    'canceled_jobs': summary_row['canceled_jobs'] or 0,
                    'avg_duration_seconds': summary_row['avg_duration_seconds']
                },
                'limit': limit,
                'job_type_filter': job_type
            }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get job history: {str(e)}"
        )

@router.get("/worker-failures", response_model=Dict[str, Any])
async def get_worker_failures(
    limit: int = Query(50, description="Maximum number of failures to return"),
    job_id: Optional[UUID] = Query(None, description="Filter by job ID"),
    server_url: Optional[str] = Query(None, description="Filter by server URL")
) -> Dict[str, Any]:
    """Get recent worker failures and error logs for debugging."""
    try:
        pool = await get_connection_pool()
        async with pool.acquire() as conn:
            # Build query conditions
            conditions = ["error_type = 'WORKER_FAILURE'"]
            params = []
            param_count = 0
            
            if job_id:
                param_count += 1
                conditions.append(f"job_id = ${param_count}")
                params.append(str(job_id))
            
            if server_url:
                param_count += 1
                conditions.append(f"server_url = ${param_count}")
                params.append(server_url)
            
            where_clause = " AND ".join(conditions)
            param_count += 1
            
            # Get error logs
            error_logs = await conn.fetch(f"""
                SELECT job_id, server_url, worker_id, severity, description, 
                       context::text as context, created_at
                FROM error_logs
                WHERE {where_clause}
                ORDER BY created_at DESC
                LIMIT ${param_count}
            """, *params, limit)
            
            # Get failed workers from heartbeats
            failed_workers = await conn.fetch("""
                SELECT worker_id, server_url, job_id, failure_reason, failure_count, 
                       last_failure_at, last_heartbeat, tasks_processed
                FROM worker_heartbeats
                WHERE status = 'failed'
                ORDER BY last_failure_at DESC
                LIMIT $1
            """, limit)
            
            return {
                "error_logs": [dict(row) for row in error_logs],
                "failed_workers": [dict(row) for row in failed_workers],
                "summary": {
                    "total_error_logs": len(error_logs),
                    "total_failed_workers": len(failed_workers),
                    "filters_applied": {
                        "job_id": str(job_id) if job_id else None,
                        "server_url": server_url
                    }
                }
            }
            
    except Exception as e:
        logger.error(f"Failed to get worker failures: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get worker failures: {str(e)}")

@router.get("/error-statistics", response_model=Dict[str, Any])
async def get_error_statistics(
    job_id: Optional[UUID] = Query(None, description="Filter by job ID"),
    hours: int = Query(24, description="Hours to look back for statistics")
) -> Dict[str, Any]:
    """Get error statistics and patterns for debugging."""
    try:
        pool = await get_connection_pool()
        async with pool.acquire() as conn:
            # Build time filter
            time_filter = f"created_at >= NOW() - INTERVAL '{hours} hours'"
            job_filter = ""
            params = []
            
            if job_id:
                job_filter = " AND job_id = $1"
                params.append(str(job_id))
            
            # Get error type distribution
            error_types = await conn.fetch(f"""
                SELECT error_type, severity, COUNT(*) as count,
                       MIN(created_at) as first_seen,
                       MAX(created_at) as last_seen
                FROM error_logs
                WHERE {time_filter}{job_filter}
                GROUP BY error_type, severity
                ORDER BY count DESC
            """, *params)
            
            # Get server-specific error rates
            server_errors = await conn.fetch(f"""
                SELECT server_url, error_type, COUNT(*) as count
                FROM error_logs
                WHERE {time_filter}{job_filter}
                GROUP BY server_url, error_type
                ORDER BY server_url, count DESC
            """, *params)
            
            # Get recent error samples
            recent_errors = await conn.fetch(f"""
                SELECT error_type, severity, description, context, created_at, server_url, worker_id
                FROM error_logs
                WHERE {time_filter}{job_filter}
                ORDER BY created_at DESC
                LIMIT 20
            """, *params)
            
            # Calculate error rate trends (hourly)
            error_trends = await conn.fetch(f"""
                SELECT DATE_TRUNC('hour', created_at) as hour,
                       error_type,
                       COUNT(*) as count
                FROM error_logs
                WHERE {time_filter}{job_filter}
                GROUP BY DATE_TRUNC('hour', created_at), error_type
                ORDER BY hour DESC, count DESC
            """, *params)
            
            return {
                "time_range": f"Last {hours} hours",
                "job_id": str(job_id) if job_id else "All jobs",
                "error_type_distribution": [dict(row) for row in error_types],
                "server_error_rates": [dict(row) for row in server_errors],
                "recent_errors": [dict(row) for row in recent_errors],
                "hourly_trends": [dict(row) for row in error_trends],
                "summary": {
                    "total_errors": sum(row['count'] for row in error_types),
                    "unique_error_types": len(set(row['error_type'] for row in error_types)),
                    "affected_servers": len(set(row['server_url'] for row in server_errors if row['server_url'])),
                    "time_range_hours": hours
                }
            }
            
    except Exception as e:
        logger.error(f"Failed to get error statistics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get error statistics: {str(e)}")

@router.post("/worker/{worker_id}/retry", response_model=Dict[str, Any])
async def retry_failed_worker(
    worker_id: str,
    server_url: str = Query(..., description="Server URL of the worker"),
    job_id: UUID = Query(..., description="Job ID")
) -> Dict[str, Any]:
    """Retry a failed worker by restarting it."""
    try:
        from ...data_access.worker_heartbeats import WorkerHeartbeatsRepository
        from ...data_access.judge_task_queue import JudgeTaskQueueRepository
        
        heartbeat_repo = WorkerHeartbeatsRepository()
        queue_repo = JudgeTaskQueueRepository()
        
        # Check if worker exists and is failed
        worker = heartbeat_repo.get_worker_status(worker_id, server_url, job_id)
        if not worker:
            raise HTTPException(status_code=404, detail="Worker not found")
        
        if worker.status != 'failed':
            raise HTTPException(status_code=400, detail=f"Worker is not in failed state (current: {worker.status})")
        
        # Requeue any tasks that were assigned to this worker
        requeued_tasks = queue_repo.requeue_failed_worker_tasks(worker_id, server_url, job_id)
        
        # Reset worker status to pending for retry
        success = heartbeat_repo.retry_failed_worker(worker_id, server_url, job_id)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to reset worker status")
        
        # Launch new worker process
        await _launch_single_worker(job_id, server_url, 30, 3)  # Default timeout and retries
        
        return {
            "message": f"Worker {worker_id} retry initiated",
            "worker_id": worker_id,
            "server_url": server_url,
            "requeued_tasks": requeued_tasks,
            "status": "retry_initiated"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retry worker: {str(e)}"
        )

@router.delete("/clear-queue", response_model=Dict[str, Any])
async def clear_queue(
    job_id: Optional[UUID] = Query(None, description="Specific job ID to clear (clears all if not specified)"),
    status_filter: Optional[str] = Query(None, description="Status filter (pending, leased, in_progress, failed)")
) -> Dict[str, Any]:
    """Clear tasks from the judge task queue to prevent duplicates."""
    try:
        from ...data_access.judge_task_queue import JudgeTaskQueueRepository

        queue_repo = JudgeTaskQueueRepository()

        if job_id:
            # Clear tasks for a specific job
            if status_filter:
                # Clear tasks with specific status for the job
                if status_filter == 'pending':
                    cleared = await queue_repo._clear_pending_tasks_for_job(job_id)
                elif status_filter == 'leased':
                    cleared = await queue_repo._clear_leased_tasks_for_job(job_id)
                elif status_filter == 'in_progress':
                    cleared = await queue_repo._clear_in_progress_tasks_for_job(job_id)
                elif status_filter == 'failed':
                    cleared = await queue_repo._clear_failed_tasks_for_job(job_id)
                else:
                    raise HTTPException(status_code=400, detail=f"Invalid status filter: {status_filter}")
            else:
                # Clear all tasks for the job
                cleared = queue_repo.cancel_job_tasks(job_id)
        else:
            # Clear all tasks based on status filter
            if status_filter:
                if status_filter == 'pending':
                    cleared = await queue_repo._clear_all_pending_tasks()
                elif status_filter == 'leased':
                    cleared = await queue_repo._clear_all_leased_tasks()
                elif status_filter == 'in_progress':
                    cleared = await queue_repo._clear_all_in_progress_tasks()
                elif status_filter == 'failed':
                    cleared = await queue_repo._clear_all_failed_tasks()
                else:
                    raise HTTPException(status_code=400, detail=f"Invalid status filter: {status_filter}")
            else:
                # Clear all tasks (be careful with this!)
                cleared = await queue_repo._clear_all_tasks()

        return {
            'success': True,
            'cleared_tasks': cleared,
            'job_id': str(job_id) if job_id else None,
            'status_filter': status_filter,
            'message': f"Successfully cleared {cleared} tasks from the queue"
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clear queue: {str(e)}"
        )

@router.post("/bulk-judge/validate", response_model=Dict[str, Any])
async def validate_bulk_judge_job(request: BulkJudgeRequest) -> Dict[str, Any]:
    """Validate bulk judge job parameters before submission (pre-flight check)."""
    pool = await get_connection_pool()

    try:
        validation_result = {
            "valid": True,
            "warnings": [],
            "errors": [],
            "recommendations": [],
            "estimated_duration": None,
            "estimated_tasks": None
        }

        # Check profile selection
        if not request.all_profiles and not request.profile_ids:
            validation_result["valid"] = False
            validation_result["errors"].append("Either all_profiles must be true or profile_ids must be provided")
            return validation_result

        async with pool.acquire() as conn:
            # Get profile count
            if request.all_profiles:
                profile_count = await conn.fetchval("SELECT COUNT(*) FROM research_profiles WHERE is_active = true")
                profile_ids = [row['id'] for row in await conn.fetch("SELECT id FROM research_profiles WHERE is_active = true")]
            else:
                profile_count = len(request.profile_ids)
                profile_ids = request.profile_ids

            # Estimate paper count
            paper_filters = []
            params = []

            if request.start_date:
                paper_filters.append("published_date >= $1")
                params.append(request.start_date)

            if request.end_date:
                paper_filters.append("published_date <= $1")
                params.append(request.end_date)

            if request.limit:
                paper_filters.append(f"LIMIT {request.limit}")

            paper_query = f"SELECT COUNT(*) FROM papers WHERE embedding IS NOT NULL"
            if paper_filters:
                paper_query += " AND " + " AND ".join(paper_filters[:-1] if paper_filters[-1].startswith("LIMIT") else paper_filters)

            paper_count = await conn.fetchval(paper_query, *params[:len(paper_filters)-1] if paper_filters[-1].startswith("LIMIT") else params)

            # Estimate total tasks (papers × profiles)
            estimated_tasks = paper_count * profile_count
            validation_result["estimated_tasks"] = estimated_tasks

            # Estimate duration based on processing mode
            if request.use_multi_server:
                # Multi-server: faster processing
                tasks_per_minute = 10  # Conservative estimate per server
                server_count = len(request.server_ids) if request.server_ids else 4  # Assume 4 if not specified
                estimated_minutes = estimated_tasks / (tasks_per_minute * server_count)
            else:
                # Single server: slower processing
                tasks_per_minute = 5  # Conservative estimate
                estimated_minutes = estimated_tasks / tasks_per_minute

            validation_result["estimated_duration"] = {
                "minutes": round(estimated_minutes, 1),
                "hours": round(estimated_minutes / 60, 1),
                "formatted": f"{round(estimated_minutes // 60)}h {round(estimated_minutes % 60)}m" if estimated_minutes >= 60 else f"{round(estimated_minutes)}m"
            }

            # Check for conflicts
            conflict_data = await _check_job_conflicts()
            if conflict_data["has_conflicts"]:
                resource_intensive_conflicts = [
                    job for job in conflict_data["conflicts"]
                    if job["job_type"] in ['harvest_judge', 'bulk_judge', 'newsletter_generation', 'mindmap_generation', 'podcast_generation']
                ]

                if len(resource_intensive_conflicts) > 1:
                    validation_result["valid"] = False
                    validation_result["errors"].extend(conflict_data["recommendations"])
                else:
                    validation_result["warnings"].extend(conflict_data["recommendations"])

            # Validate multi-server configuration
            if request.use_multi_server:
                from ...data_access.ollama_servers import OllamaServersRepository
                server_repo = OllamaServersRepository()
                available_servers = server_repo.get_enabled()

                if not available_servers:
                    validation_result["valid"] = False
                    validation_result["errors"].append("Multi-server mode requested but no enabled Ollama servers found")
                else:
                    if request.server_ids:
                        available_ids = {server.id for server in available_servers}
                        invalid_ids = set(request.server_ids) - available_ids
                        if invalid_ids:
                            validation_result["valid"] = False
                            validation_result["errors"].append(f"Invalid server IDs: {list(invalid_ids)}")
                    else:
                        validation_result["recommendations"].append(f"Using all {len(available_servers)} enabled servers")

            # Performance warnings
            if estimated_tasks > 10000:
                validation_result["warnings"].append(f"Large job detected ({estimated_tasks} tasks). This may take {validation_result['estimated_duration']['formatted']}")

            if estimated_minutes > 480:  # 8 hours
                validation_result["warnings"].append("Job estimated to take more than 8 hours. Consider breaking into smaller batches")

            # Resource recommendations
            if request.use_multi_server and not request.suspend_scheduled_tasks:
                validation_result["recommendations"].append("Consider suspending scheduled tasks to improve performance")

            if not request.overwrite_existing:
                validation_result["recommendations"].append("Using 'skip existing' mode. Already scored Paper+Profile pairs will be skipped")

        return validation_result

    except Exception as e:
        return {
            "valid": False,
            "warnings": [],
            "errors": [f"Validation failed: {str(e)}"],
            "recommendations": [],
            "estimated_duration": None,
            "estimated_tasks": None
        }

# Helper functions for conflict checking
def _get_job_description(job_type: str, configuration: Optional[Dict[str, Any]]) -> str:
    """Generate a human-readable description of a job."""
    if job_type == 'bulk_judge':
        if configuration:
            if configuration.get('use_multi_server'):
                servers = configuration.get('selected_servers', [])
                server_desc = f"{len(servers)} servers" if servers else "multiple servers"
                return f"Bulk judge using {server_desc}"
            else:
                return "Bulk judge (single server)"
        return "Bulk judge operation"
    elif job_type == 'harvest_judge':
        return "Harvest and judge operation"
    elif job_type == 'newsletter_generation':
        return "Newsletter generation"
    elif job_type == 'mindmap_generation':
        return "Mind-map generation"
    elif job_type == 'podcast_generation':
        return "Podcast generation"
    else:
        return f"{job_type.replace('_', ' ').title()}"

def _get_conflict_recommendations(conflicts: List[Dict[str, Any]], bulk_judge_running: bool) -> List[str]:
    """Generate recommendations for handling job conflicts."""
    recommendations = []

    if bulk_judge_running:
        recommendations.append("A bulk judge job is currently running. Consider pausing it before starting other jobs.")
        recommendations.append("Bulk judge jobs can take several hours and may impact system performance.")

    if len(conflicts) > 1:
        recommendations.append(f"There are {len(conflicts)} active jobs running. Consider waiting for completion or canceling non-essential jobs.")

    # Check for resource-intensive jobs
    resource_intensive = ['harvest_judge', 'bulk_judge', 'newsletter_generation']
    intensive_running = [c for c in conflicts if c['job_type'] in resource_intensive]

    if len(intensive_running) > 1:
        recommendations.append("Multiple resource-intensive jobs are running. This may impact system performance.")

    return recommendations

async def _check_job_conflicts():
    """Check for potential conflicts with running jobs."""
    pool = await get_connection_pool()

    try:
        async with pool.acquire() as conn:
            # Check for running bulk judge jobs
            running_jobs = await conn.fetch(
                """
                SELECT id, job_type, started_at, configuration
                FROM processing_jobs
                WHERE status IN ('running', 'pending')
                AND job_type IN ('bulk_judge', 'harvest_judge', 'newsletter_generation', 'mindmap_generation', 'podcast_generation')
                """
            )

            conflicts = []
            bulk_judge_running = False

            for job in running_jobs:
                job_info = {
                    "job_id": str(job['id']),
                    "job_type": job['job_type'],
                    "started_at": job['started_at'].isoformat() if job['started_at'] else None,
                    "description": _get_job_description(job['job_type'], job['configuration'])
                }

                if job['job_type'] == 'bulk_judge':
                    bulk_judge_running = True
                    # Check if it's a multi-server job
                    configuration = job['configuration']
                    if configuration and isinstance(configuration, dict) and configuration.get('use_multi_server', False):
                        job_info["multi_server"] = True
                        job_info["servers"] = configuration.get('selected_servers', [])

                conflicts.append(job_info)

            return {
                "has_conflicts": len(conflicts) > 0,
                "bulk_judge_running": bulk_judge_running,
                "conflicts": conflicts,
                "recommendations": _get_conflict_recommendations(conflicts, bulk_judge_running)
            }

    except Exception as e:
        # Return empty result on error to avoid blocking job submission
        return {
            "has_conflicts": False,
            "bulk_judge_running": False,
            "conflicts": [],
            "recommendations": []
        }