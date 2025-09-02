"""Data access layer for judge task queue management."""

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from uuid import UUID
from ..db import get_cursor
import asyncio


class JudgeTask:
    """Represents a judge task in the queue."""

    def __init__(
        self,
        id: int,
        job_id: UUID,
        paper_id: int,
        profile_id: int,
        status: str = 'pending',
        attempts: int = 0,
        last_error: Optional[str] = None,
        assigned_server_url: Optional[str] = None,
        leased_until: Optional[datetime] = None,
        leased_by_worker: Optional[str] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None
    ):
        self.id = id
        self.job_id = job_id
        self.paper_id = paper_id
        self.profile_id = profile_id
        self.status = status
        self.attempts = attempts
        self.last_error = last_error
        self.assigned_server_url = assigned_server_url
        self.leased_until = leased_until
        self.leased_by_worker = leased_by_worker
        self.created_at = created_at
        self.updated_at = updated_at

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'JudgeTask':
        """Create a JudgeTask instance from a dictionary."""
        return cls(
            id=data['id'],
            job_id=data['job_id'],
            paper_id=data['paper_id'],
            profile_id=data['profile_id'],
            status=data.get('status', 'pending'),
            attempts=data.get('attempts', 0),
            last_error=data.get('last_error'),
            assigned_server_url=data.get('assigned_server_url'),
            leased_until=data.get('leased_until'),
            leased_by_worker=data.get('leased_by_worker'),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at')
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'id': self.id,
            'job_id': str(self.job_id),
            'paper_id': self.paper_id,
            'profile_id': self.profile_id,
            'status': self.status,
            'attempts': self.attempts,
            'last_error': self.last_error,
            'assigned_server_url': self.assigned_server_url,
            'leased_until': self.leased_until.isoformat() if self.leased_until else None,
            'leased_by_worker': self.leased_by_worker,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class JudgeTaskQueueRepository:
    """Repository for managing judge task queue operations."""

    @staticmethod
    def enqueue_tasks(job_id: UUID, paper_profile_pairs: List[Tuple[int, int]], server_urls: Optional[List[str]] = None) -> int:
        """Enqueue multiple tasks for a job. Returns count of tasks enqueued.
        
        If server_urls are provided, tasks will be distributed round-robin across servers.
        """
        if not paper_profile_pairs:
            return 0

        with get_cursor() as cursor:
            if server_urls:
                # Distribute tasks round-robin across servers
                values = []
                for i, (paper_id, profile_id) in enumerate(paper_profile_pairs):
                    server_url = server_urls[i % len(server_urls)]
                    values.append((str(job_id), paper_id, profile_id, server_url))
                
                cursor.executemany("""
                    INSERT INTO judge_task_queue (job_id, paper_id, profile_id, assigned_server_url)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (job_id, paper_id, profile_id) DO NOTHING
                """, values)
            else:
                # Use bulk insert for efficiency without server assignment
                values = [(str(job_id), paper_id, profile_id) for paper_id, profile_id in paper_profile_pairs]

                cursor.executemany("""
                    INSERT INTO judge_task_queue (job_id, paper_id, profile_id)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (job_id, paper_id, profile_id) DO NOTHING
                """, values)

            return cursor.rowcount

    @staticmethod
    def lease_next_task(server_url: str, worker_id: str, lease_duration_minutes: int = 5) -> Optional[JudgeTask]:
        """Lease the next available task using SKIP LOCKED for concurrency safety."""
        leased_until = datetime.now() + timedelta(minutes=lease_duration_minutes)

        with get_cursor() as cursor:
            # Use SKIP LOCKED to prevent multiple workers from getting the same task
            cursor.execute("""
                UPDATE judge_task_queue
                SET status = 'leased',
                    assigned_server_url = %s,
                    leased_until = %s,
                    leased_by_worker = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = (
                    SELECT id FROM judge_task_queue
                    WHERE status = 'pending'
                    AND (assigned_server_url IS NULL OR assigned_server_url = %s)
                    ORDER BY created_at ASC
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                RETURNING id, job_id, paper_id, profile_id, status, attempts,
                          last_error, assigned_server_url, leased_until,
                          leased_by_worker, created_at, updated_at
            """, (server_url, leased_until, worker_id, server_url))

            row = cursor.fetchone()
            return JudgeTask.from_dict(dict(row)) if row else None

    @staticmethod
    def get_expired_leases() -> List[JudgeTask]:
        """Get tasks with expired leases that should be re-queued."""
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT id, job_id, paper_id, profile_id, status, attempts,
                       last_error, assigned_server_url, leased_until,
                       leased_by_worker, created_at, updated_at
                FROM judge_task_queue
                WHERE status = 'leased'
                  AND leased_until < CURRENT_TIMESTAMP
            """)
            rows = cursor.fetchall()
            return [JudgeTask.from_dict(dict(row)) for row in rows]

    @staticmethod
    def requeue_expired_leases() -> int:
        """Re-queue tasks with expired leases. Returns count of tasks re-queued."""
        with get_cursor() as cursor:
            cursor.execute("""
                UPDATE judge_task_queue
                SET status = 'pending',
                    assigned_server_url = NULL,
                    leased_until = NULL,
                    leased_by_worker = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE status = 'leased'
                  AND leased_until < CURRENT_TIMESTAMP
            """)
            return cursor.rowcount

    @staticmethod
    def mark_task_in_progress(task_id: int, worker_id: str) -> bool:
        """Mark a leased task as in progress."""
        with get_cursor() as cursor:
            cursor.execute("""
                UPDATE judge_task_queue
                SET status = 'in_progress',
                    leased_by_worker = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s AND status = 'leased'
            """, (worker_id, task_id))
            return cursor.rowcount > 0

    @staticmethod
    def mark_task_completed(task_id: int) -> bool:
        """Mark a task as completed."""
        with get_cursor() as cursor:
            cursor.execute("""
                UPDATE judge_task_queue
                SET status = 'completed',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (task_id,))
            return cursor.rowcount > 0

    @staticmethod
    def mark_task_failed(task_id: int, error_message: str, increment_attempts: bool = True) -> bool:
        """Mark a task as failed with error message."""
        with get_cursor() as cursor:
            if increment_attempts:
                cursor.execute("""
                    UPDATE judge_task_queue
                    SET status = 'failed',
                        last_error = %s,
                        attempts = attempts + 1,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (error_message, task_id))
            else:
                cursor.execute("""
                    UPDATE judge_task_queue
                    SET status = 'failed',
                        last_error = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (error_message, task_id))
            return cursor.rowcount > 0

    @staticmethod
    def requeue_failed_task(task_id: int) -> bool:
        """Re-queue a failed task for retry."""
        with get_cursor() as cursor:
            cursor.execute("""
                UPDATE judge_task_queue
                SET status = 'pending',
                    assigned_server_url = NULL,
                    leased_until = NULL,
                    leased_by_worker = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s AND status = 'failed'
            """, (task_id,))
            return cursor.rowcount > 0

    @staticmethod
    def cancel_job_tasks(job_id: UUID) -> int:
        """Cancel all tasks for a specific job. Returns count of tasks cancelled."""
        with get_cursor() as cursor:
            cursor.execute("""
                UPDATE judge_task_queue
                SET status = 'canceled',
                    updated_at = CURRENT_TIMESTAMP
                WHERE job_id = %s AND status IN ('pending', 'leased', 'in_progress')
            """, (str(job_id),))
            return cursor.rowcount

    @staticmethod
    def get_job_progress(job_id: UUID) -> Dict[str, Any]:
        """Get progress statistics for a job."""
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT
                    COUNT(*) as total_tasks,
                    COUNT(*) FILTER (WHERE status = 'completed') as completed_tasks,
                    COUNT(*) FILTER (WHERE status = 'failed') as failed_tasks,
                    COUNT(*) FILTER (WHERE status = 'pending') as pending_tasks,
                    COUNT(*) FILTER (WHERE status = 'leased') as leased_tasks,
                    COUNT(*) FILTER (WHERE status = 'in_progress') as in_progress_tasks,
                    COUNT(*) FILTER (WHERE status = 'canceled') as canceled_tasks,
                    AVG(attempts) as avg_attempts,
                    MAX(attempts) as max_attempts
                FROM judge_task_queue
                WHERE job_id = %s
            """, (str(job_id),))
            row = cursor.fetchone()
            return dict(row) if row else {}

    @staticmethod
    def get_job_server_stats(job_id: UUID) -> List[Dict[str, Any]]:
        """Get per-server statistics for a job."""
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT
                    assigned_server_url,
                    COUNT(*) as total_tasks,
                    COUNT(*) FILTER (WHERE status = 'completed') as completed_tasks,
                    COUNT(*) FILTER (WHERE status = 'failed') as failed_tasks,
                    AVG(attempts) as avg_attempts,
                    MAX(attempts) as max_attempts,
                    MIN(created_at) as first_task_at,
                    MAX(updated_at) as last_update_at
                FROM judge_task_queue
                WHERE job_id = %s AND assigned_server_url IS NOT NULL
                GROUP BY assigned_server_url
                ORDER BY completed_tasks DESC
            """, (str(job_id),))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_pending_task_count(job_id: Optional[UUID] = None) -> int:
        """Get count of pending tasks, optionally for a specific job."""
        with get_cursor() as cursor:
            if job_id:
                cursor.execute("""
                    SELECT COUNT(*) FROM judge_task_queue
                    WHERE status = 'pending' AND job_id = %s
                """, (str(job_id),))
            else:
                cursor.execute("""
                    SELECT COUNT(*) FROM judge_task_queue WHERE status = 'pending'
                """)
            row = cursor.fetchone()
            return row['count'] if row else 0

    @staticmethod
    def cleanup_old_tasks(days_old: int = 30) -> int:
        """Clean up old completed/failed/canceled tasks. Returns count deleted."""
        with get_cursor() as cursor:
            cursor.execute("""
                DELETE FROM judge_task_queue
                WHERE status IN ('completed', 'failed', 'canceled')
                  AND updated_at < CURRENT_TIMESTAMP - INTERVAL '%s days'
            """, (days_old,))
            return cursor.rowcount

    @staticmethod
    def get_active_jobs() -> List[UUID]:
        """Get list of job IDs that have active (non-terminal) tasks."""
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT DISTINCT job_id
                FROM judge_task_queue
                WHERE status NOT IN ('completed', 'failed', 'canceled')
            """)
            rows = cursor.fetchall()
            return [UUID(row['job_id']) for row in rows]

    @staticmethod
    async def _clear_pending_tasks_for_job(job_id: UUID) -> int:
        """Clear pending tasks for a specific job."""
        with get_cursor() as cursor:
            cursor.execute("""
                DELETE FROM judge_task_queue
                WHERE job_id = %s AND status = 'pending'
            """, (str(job_id),))
            return cursor.rowcount

    @staticmethod
    async def _clear_leased_tasks_for_job(job_id: UUID) -> int:
        """Clear leased tasks for a specific job."""
        with get_cursor() as cursor:
            cursor.execute("""
                DELETE FROM judge_task_queue
                WHERE job_id = %s AND status = 'leased'
            """, (str(job_id),))
            return cursor.rowcount

    @staticmethod
    async def _clear_in_progress_tasks_for_job(job_id: UUID) -> int:
        """Clear in-progress tasks for a specific job."""
        with get_cursor() as cursor:
            cursor.execute("""
                DELETE FROM judge_task_queue
                WHERE job_id = %s AND status = 'in_progress'
            """, (str(job_id),))
            return cursor.rowcount

    @staticmethod
    async def _clear_failed_tasks_for_job(job_id: UUID) -> int:
        """Clear failed tasks for a specific job."""
        with get_cursor() as cursor:
            cursor.execute("""
                DELETE FROM judge_task_queue
                WHERE job_id = %s AND status = 'failed'
            """, (str(job_id),))
            return cursor.rowcount

    @staticmethod
    async def _clear_all_pending_tasks() -> int:
        """Clear all pending tasks from the queue."""
        with get_cursor() as cursor:
            cursor.execute("DELETE FROM judge_task_queue WHERE status = 'pending'")
            return cursor.rowcount

    @staticmethod
    async def _clear_all_leased_tasks() -> int:
        """Clear all leased tasks from the queue."""
        with get_cursor() as cursor:
            cursor.execute("DELETE FROM judge_task_queue WHERE status = 'leased'")
            return cursor.rowcount

    @staticmethod
    async def _clear_all_in_progress_tasks() -> int:
        """Clear all in-progress tasks from the queue."""
        with get_cursor() as cursor:
            cursor.execute("DELETE FROM judge_task_queue WHERE status = 'in_progress'")
            return cursor.rowcount

    @staticmethod
    async def _clear_all_failed_tasks() -> int:
        """Clear all failed tasks from the queue."""
        with get_cursor() as cursor:
            cursor.execute("DELETE FROM judge_task_queue WHERE status = 'failed'")
            return cursor.rowcount

    @staticmethod
    async def _clear_all_tasks() -> int:
        """Clear all tasks from the queue (use with caution!)."""
        with get_cursor() as cursor:
            cursor.execute("DELETE FROM judge_task_queue")
            return cursor.rowcount

    @staticmethod
    def get_queue_stats() -> Dict[str, Any]:
        """Get overall queue statistics."""
        with get_cursor() as cursor:
            # Get total counts by status
            cursor.execute("""
                SELECT
                    COUNT(*) as total_tasks,
                    COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_tasks,
                    COUNT(CASE WHEN status = 'leased' THEN 1 END) as leased_tasks,
                    COUNT(CASE WHEN status = 'in_progress' THEN 1 END) as in_progress_tasks,
                    COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_tasks,
                    COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_tasks,
                    COUNT(CASE WHEN status = 'canceled' THEN 1 END) as canceled_tasks
                FROM judge_task_queue
            """)
            stats = cursor.fetchone()

            return {
                'total_tasks': stats['total_tasks'] or 0,
                'pending_tasks': stats['pending_tasks'] or 0,
                'leased_tasks': stats['leased_tasks'] or 0,
                'in_progress_tasks': stats['in_progress_tasks'] or 0,
                'completed_tasks': stats['completed_tasks'] or 0,
                'failed_tasks': stats['failed_tasks'] or 0,
                'canceled_tasks': stats['canceled_tasks'] or 0
            }

    @staticmethod
    def get_active_jobs_with_queue_info() -> List[Dict[str, Any]]:
        """Get active jobs with their queue information."""
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT
                    jt.job_id,
                    COUNT(*) as total_tasks,
                    COUNT(CASE WHEN jt.status = 'pending' THEN 1 END) as pending_tasks,
                    COUNT(CASE WHEN jt.status = 'leased' THEN 1 END) as leased_tasks,
                    COUNT(CASE WHEN jt.status = 'in_progress' THEN 1 END) as in_progress_tasks,
                    COUNT(CASE WHEN jt.status = 'completed' THEN 1 END) as completed_tasks,
                    COUNT(CASE WHEN jt.status = 'failed' THEN 1 END) as failed_tasks,
                    COUNT(CASE WHEN jt.status = 'canceled' THEN 1 END) as canceled_tasks,
                    MIN(jt.created_at) as oldest_task,
                    MAX(jt.updated_at) as newest_update
                FROM judge_task_queue jt
                WHERE jt.job_id IN (
                    SELECT DISTINCT job_id
                    FROM judge_task_queue
                    WHERE status NOT IN ('completed', 'failed', 'canceled')
                )
                GROUP BY jt.job_id
                ORDER BY oldest_task DESC
            """)
            rows = cursor.fetchall()

            jobs = []
            for row in rows:
                jobs.append({
                    'job_id': str(row['job_id']),
                    'total_tasks': row['total_tasks'] or 0,
                    'pending_tasks': row['pending_tasks'] or 0,
                    'leased_tasks': row['leased_tasks'] or 0,
                    'in_progress_tasks': row['in_progress_tasks'] or 0,
                    'completed_tasks': row['completed_tasks'] or 0,
                    'failed_tasks': row['failed_tasks'] or 0,
                    'canceled_tasks': row['canceled_tasks'] or 0,
                    'oldest_task': row['oldest_task'].isoformat() if row['oldest_task'] else None,
                    'newest_update': row['newest_update'].isoformat() if row['newest_update'] else None
                })

            return jobs
