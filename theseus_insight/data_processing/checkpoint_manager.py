"""
Checkpoint Manager for resumable processing operations.
Interfaces with processing_jobs and processing_checkpoints tables.
"""
import json
import logging
from datetime import datetime, date
from typing import Any, Dict, Optional, List
from uuid import UUID, uuid4
import asyncpg
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


def make_json_serializable(obj: Any) -> Any:
    """
    Recursively convert an object to be JSON serializable.
    
    Handles common PostgreSQL types like timestamps, dates, UUIDs, etc.
    """
    if obj is None:
        return None
    elif isinstance(obj, (str, int, float, bool)):
        return obj
    elif isinstance(obj, (datetime, date)):
        return obj.isoformat()
    elif isinstance(obj, UUID):
        return str(obj)
    elif isinstance(obj, dict):
        return {k: make_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [make_json_serializable(item) for item in obj]
    else:
        # For any other type (like psycopg Timestamp), convert to string
        try:
            return str(obj)
        except Exception:
            return None


class CheckpointManager:
    """Manages job checkpoints for resumable processing operations."""
    
    def __init__(self, pool: asyncpg.Pool):
        """Initialize with an existing connection pool.
        
        Args:
            pool: AsyncPG connection pool
        """
        self.pool = pool
    
    @asynccontextmanager
    async def get_connection(self):
        """Get a database connection from the pool."""
        async with self.pool.acquire() as conn:
            yield conn
    
    async def create_job(
        self,
        job_type: str,
        configuration: Dict[str, Any],
        initial_state: Optional[Dict[str, Any]] = None
    ) -> UUID:
        """
        Create a new processing job.
        
        Args:
            job_type: Type of job (e.g., 'harvest_judge', 'bulk_judge')
            configuration: Job configuration parameters
            initial_state: Initial processing state
            
        Returns:
            Job ID
        """
        async with self.get_connection() as conn:
            # Make sure configuration is JSON serializable
            safe_configuration = make_json_serializable(configuration)
            safe_initial_state = make_json_serializable(initial_state or {})
            
            job_id = await conn.fetchval(
                """
                INSERT INTO processing_jobs 
                (job_type, configuration, state, status, started_at)
                VALUES ($1, $2, $3, 'running', CURRENT_TIMESTAMP)
                RETURNING id
                """,
                job_type,
                json.dumps(safe_configuration),
                json.dumps(safe_initial_state)
            )
            logger.info(f"Created job {job_id} of type {job_type}")
            return job_id
    
    async def save_checkpoint(
        self,
        job_id: UUID,
        checkpoint_type: str,
        checkpoint_data: Dict[str, Any],
        item_count: int = 0,
        update_state: Optional[Dict[str, Any]] = None
    ):
        """
        Save a checkpoint for a job.
        
        Args:
            job_id: Processing job ID
            checkpoint_type: Type of checkpoint (e.g., 'papers_processed')
            checkpoint_data: Data to save in checkpoint
            item_count: Number of items processed in this checkpoint
            update_state: Optional state update for the job
        """
        async with self.get_connection() as conn:
            async with conn.transaction():
                # Make sure checkpoint data is JSON serializable
                safe_checkpoint_data = make_json_serializable(checkpoint_data)
                
                # Save checkpoint using the database function
                await conn.execute(
                    "SELECT save_checkpoint($1, $2, $3, $4)",
                    job_id,
                    checkpoint_type,
                    json.dumps(safe_checkpoint_data),
                    item_count
                )
                
                # Update job state if provided
                if update_state:
                    safe_update_state = make_json_serializable(update_state)
                    await conn.execute(
                        """
                        UPDATE processing_jobs 
                        SET state = $2, updated_at = CURRENT_TIMESTAMP
                        WHERE id = $1
                        """,
                        job_id,
                        json.dumps(safe_update_state)
                    )
                
                logger.debug(f"Saved checkpoint for job {job_id}: {checkpoint_type}")
    
    async def get_latest_checkpoint(
        self,
        job_id: UUID,
        checkpoint_type: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get the latest checkpoint for a job.
        
        Args:
            job_id: Processing job ID
            checkpoint_type: Optional checkpoint type filter
            
        Returns:
            Checkpoint data or None
        """
        async with self.get_connection() as conn:
            result = await conn.fetchrow(
                "SELECT * FROM get_latest_checkpoint($1, $2)",
                job_id,
                checkpoint_type
            )
            
            if result:
                return {
                    'checkpoint_type': result['checkpoint_type'],
                    'checkpoint_data': json.loads(result['checkpoint_data']),
                    'item_count': result['item_count'],
                    'created_at': result['created_at']
                }
            return None
    
    async def get_job_state(self, job_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Get the current state of a job.
        
        Args:
            job_id: Processing job ID
            
        Returns:
            Job state including configuration and processing state
        """
        async with self.get_connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT job_type, status, configuration, state, 
                       progress_current, progress_total, error_message,
                       started_at, completed_at
                FROM processing_jobs
                WHERE id = $1
                """,
                job_id
            )
            
            if row:
                return {
                    'job_id': job_id,
                    'job_type': row['job_type'],
                    'status': row['status'],
                    'configuration': json.loads(row['configuration']),
                    'state': json.loads(row['state']) if row['state'] else {},
                    'progress': {
                        'current': row['progress_current'],
                        'total': row['progress_total']
                    },
                    'error_message': row['error_message'],
                    'started_at': row['started_at'],
                    'completed_at': row['completed_at']
                }
            return None
    
    async def update_progress(
        self,
        job_id: UUID,
        current: int,
        total: Optional[int] = None
    ):
        """
        Update job progress counters.
        
        Args:
            job_id: Processing job ID
            current: Current progress count
            total: Optional total count update
        """
        async with self.get_connection() as conn:
            await conn.execute(
                "SELECT update_job_progress($1, $2, $3)",
                job_id,
                current,
                total
            )
    
    async def complete_job(
        self,
        job_id: UUID,
        final_state: Optional[Dict[str, Any]] = None
    ):
        """
        Mark a job as completed.
        
        Args:
            job_id: Processing job ID
            final_state: Final state to save
        """
        async with self.get_connection() as conn:
            await conn.execute(
                """
                UPDATE processing_jobs
                SET status = 'completed',
                    completed_at = CURRENT_TIMESTAMP,
                    state = COALESCE($2, state),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = $1
                """,
                job_id,
                json.dumps(final_state) if final_state else None
            )
            logger.info(f"Completed job {job_id}")
    
    async def fail_job(
        self,
        job_id: UUID,
        error_message: str,
        final_state: Optional[Dict[str, Any]] = None
    ):
        """
        Mark a job as failed.
        
        Args:
            job_id: Processing job ID
            error_message: Error description
            final_state: Final state to save
        """
        async with self.get_connection() as conn:
            await conn.execute(
                """
                UPDATE processing_jobs
                SET status = 'failed',
                    error_message = $2,
                    error_count = error_count + 1,
                    completed_at = CURRENT_TIMESTAMP,
                    state = COALESCE($3, state),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = $1
                """,
                job_id,
                error_message,
                json.dumps(final_state) if final_state else None
            )
            logger.error(f"Failed job {job_id}: {error_message}")
    
    async def find_resumable_job(
        self,
        job_type: str,
        configuration: Dict[str, Any]
    ) -> Optional[UUID]:
        """
        Find a resumable job matching the type and configuration.
        
        Args:
            job_type: Type of job
            configuration: Job configuration to match
            
        Returns:
            Job ID if found, None otherwise
        """
        async with self.get_connection() as conn:
            # Look for failed or cancelled jobs with matching config
            row = await conn.fetchrow(
                """
                SELECT id FROM processing_jobs
                WHERE job_type = $1
                  AND configuration = $2
                  AND status IN ('failed', 'cancelled')
                  AND created_at > CURRENT_TIMESTAMP - INTERVAL '7 days'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                job_type,
                json.dumps(configuration)
            )
            
            if row:
                logger.info(f"Found resumable job {row['id']} for {job_type}")
                return row['id']
            return None
    
    async def resume_job(self, job_id: UUID) -> Dict[str, Any]:
        """
        Resume a job by updating its status and returning its state.
        
        Args:
            job_id: Processing job ID
            
        Returns:
            Job state for resuming
        """
        async with self.get_connection() as conn:
            async with conn.transaction():
                # Update job status
                await conn.execute(
                    """
                    UPDATE processing_jobs
                    SET status = 'running',
                        started_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = $1
                    """,
                    job_id
                )
                
                # Get job state
                state = await self.get_job_state(job_id)
                if not state:
                    raise ValueError(f"Job {job_id} not found")
                
                logger.info(f"Resumed job {job_id}")
                return state
    
    async def list_active_jobs(self) -> List[Dict[str, Any]]:
        """
        List all active (pending or running) jobs.
        
        Returns:
            List of active job details
        """
        async with self.get_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM active_jobs
                ORDER BY started_at DESC
                """
            )
            
            return [
                {
                    'job_id': row['id'],
                    'job_type': row['job_type'],
                    'status': row['status'],
                    'progress_percent': float(row['progress_percent']) if row['progress_percent'] else 0,
                    'runtime_minutes': float(row['runtime_minutes']) if row['runtime_minutes'] else 0,
                    'last_checkpoint': row['last_checkpoint_at']
                }
                for row in rows
            ]
    
    async def get_job_statistics(self, job_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get job statistics by type.
        
        Args:
            job_type: Optional filter by job type
            
        Returns:
            List of job statistics
        """
        async with self.get_connection() as conn:
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
            
            return [
                {
                    'job_type': row['job_type'],
                    'total_jobs': row['total_jobs'],
                    'completed_jobs': row['completed_jobs'],
                    'failed_jobs': row['failed_jobs'],
                    'running_jobs': row['running_jobs'],
                    'avg_runtime_minutes': float(row['avg_runtime_minutes']) if row['avg_runtime_minutes'] else 0
                }
                for row in rows
            ]
    
    async def cleanup_old_jobs(self, days: int = 30):
        """
        Clean up old completed jobs.
        
        Args:
            days: Number of days to keep completed jobs
        """
        async with self.get_connection() as conn:
            deleted = await conn.fetchval(
                """
                DELETE FROM processing_jobs
                WHERE status IN ('completed', 'cancelled')
                  AND completed_at < CURRENT_TIMESTAMP - INTERVAL '%s days'
                RETURNING COUNT(*)
                """,
                days
            )
            logger.info(f"Cleaned up {deleted} old jobs")
            return deleted