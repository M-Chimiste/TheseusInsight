"""Data access layer for worker heartbeat monitoring."""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from uuid import UUID
from ..db import get_cursor


class WorkerHeartbeat:
    """Represents a worker heartbeat entry."""

    def __init__(
        self,
        id: int,
        worker_id: str,
        server_url: str,
        job_id: Optional[UUID] = None,
        status: str = 'active',
        last_heartbeat: Optional[datetime] = None,
        tasks_processed: int = 0,
        current_task_id: Optional[int] = None,
        created_at: Optional[datetime] = None
    ):
        self.id = id
        self.worker_id = worker_id
        self.server_url = server_url
        self.job_id = job_id
        self.status = status
        self.last_heartbeat = last_heartbeat
        self.tasks_processed = tasks_processed
        self.current_task_id = current_task_id
        self.created_at = created_at

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkerHeartbeat':
        """Create a WorkerHeartbeat instance from a dictionary."""
        job_id = data.get('job_id')
        if job_id:
            # Handle both string and UUID types
            if isinstance(job_id, str):
                job_id = UUID(job_id)
            elif isinstance(job_id, UUID):
                job_id = job_id  # Already a UUID
            else:
                job_id = None
        
        return cls(
            id=data['id'],
            worker_id=data['worker_id'],
            server_url=data['server_url'],
            job_id=job_id,
            status=data.get('status', 'active'),
            last_heartbeat=data.get('last_heartbeat'),
            tasks_processed=data.get('tasks_processed', 0),
            current_task_id=data.get('current_task_id'),
            created_at=data.get('created_at')
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'id': self.id,
            'worker_id': self.worker_id,
            'server_url': self.server_url,
            'job_id': str(self.job_id) if self.job_id else None,
            'status': self.status,
            'last_heartbeat': self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            'tasks_processed': self.tasks_processed,
            'current_task_id': self.current_task_id,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class WorkerHeartbeatsRepository:
    """Repository for managing worker heartbeat monitoring."""

    @staticmethod
    def upsert_heartbeat(
        worker_id: str,
        server_url: str,
        job_id: Optional[UUID] = None,
        status: str = 'active',
        tasks_processed: int = 0,
        current_task_id: Optional[int] = None
    ) -> WorkerHeartbeat:
        """Upsert a worker heartbeat entry."""
        with get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO worker_heartbeats (
                    worker_id, server_url, job_id, status,
                    last_heartbeat, tasks_processed, current_task_id
                ) VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP, %s, %s)
                ON CONFLICT (worker_id, server_url, job_id)
                DO UPDATE SET
                    status = EXCLUDED.status,
                    last_heartbeat = CURRENT_TIMESTAMP,
                    tasks_processed = EXCLUDED.tasks_processed,
                    current_task_id = EXCLUDED.current_task_id
                RETURNING id, worker_id, server_url, job_id, status,
                          last_heartbeat, tasks_processed, current_task_id, created_at
            """, (worker_id, server_url, str(job_id) if job_id else None,
                  status, tasks_processed, current_task_id))
            row = cursor.fetchone()
            return WorkerHeartbeat.from_dict(dict(row))

    @staticmethod
    def get_active_workers(job_id: Optional[UUID] = None, max_age_minutes: int = 10) -> List[WorkerHeartbeat]:
        """Get active workers based on recent heartbeats."""
        cutoff_time = datetime.now() - timedelta(minutes=max_age_minutes)

        with get_cursor() as cursor:
            if job_id:
                cursor.execute("""
                    SELECT id, worker_id, server_url, job_id, status,
                           last_heartbeat, tasks_processed, current_task_id, created_at
                    FROM worker_heartbeats
                    WHERE job_id = %s
                      AND last_heartbeat > %s
                      AND status = 'active'
                    ORDER BY last_heartbeat DESC
                """, (str(job_id), cutoff_time))
            else:
                cursor.execute("""
                    SELECT id, worker_id, server_url, job_id, status,
                           last_heartbeat, tasks_processed, current_task_id, created_at
                    FROM worker_heartbeats
                    WHERE last_heartbeat > %s
                      AND status = 'active'
                    ORDER BY last_heartbeat DESC
                """, (cutoff_time,))

            rows = cursor.fetchall()
            return [WorkerHeartbeat.from_dict(dict(row)) for row in rows]

    @staticmethod
    def get_worker_status(worker_id: str, server_url: str, job_id: Optional[UUID] = None) -> Optional[WorkerHeartbeat]:
        """Get the status of a specific worker."""
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT id, worker_id, server_url, job_id, status,
                       last_heartbeat, tasks_processed, current_task_id, created_at
                FROM worker_heartbeats
                WHERE worker_id = %s AND server_url = %s AND job_id = %s
            """, (worker_id, server_url, str(job_id) if job_id else None))
            row = cursor.fetchone()
            return WorkerHeartbeat.from_dict(dict(row)) if row else None

    @staticmethod
    def mark_worker_inactive(worker_id: str, server_url: str, job_id: Optional[UUID] = None) -> bool:
        """Mark a worker as inactive."""
        with get_cursor() as cursor:
            cursor.execute("""
                UPDATE worker_heartbeats
                SET status = 'inactive', last_heartbeat = CURRENT_TIMESTAMP
                WHERE worker_id = %s AND server_url = %s AND job_id = %s
            """, (worker_id, server_url, str(job_id) if job_id else None))
            return cursor.rowcount > 0

    @staticmethod
    def cleanup_stale_heartbeats(max_age_hours: int = 24) -> int:
        """Clean up stale heartbeat entries. Returns count deleted."""
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)

        with get_cursor() as cursor:
            cursor.execute("""
                DELETE FROM worker_heartbeats
                WHERE last_heartbeat < %s
            """, (cutoff_time,))
            return cursor.rowcount

    @staticmethod
    def get_job_worker_stats(job_id: UUID) -> Dict[str, Any]:
        """Get worker statistics for a specific job."""
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT
                    COUNT(*) as total_workers,
                    COUNT(*) FILTER (WHERE status = 'active') as active_workers,
                    SUM(tasks_processed) as total_tasks_processed,
                    AVG(tasks_processed) as avg_tasks_per_worker,
                    MAX(tasks_processed) as max_tasks_per_worker,
                    MIN(last_heartbeat) as oldest_heartbeat,
                    MAX(last_heartbeat) as newest_heartbeat
                FROM worker_heartbeats
                WHERE job_id = %s
            """, (str(job_id),))
            row = cursor.fetchone()
            return dict(row) if row else {}

    @staticmethod
    def get_server_worker_stats(job_id: UUID) -> List[Dict[str, Any]]:
        """Get per-server worker statistics for a job."""
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT
                    server_url,
                    COUNT(*) as worker_count,
                    COUNT(*) FILTER (WHERE status = 'active') as active_workers,
                    SUM(tasks_processed) as total_tasks_processed,
                    AVG(tasks_processed) as avg_tasks_per_worker,
                    MAX(last_heartbeat) as last_heartbeat
                FROM worker_heartbeats
                WHERE job_id = %s
                GROUP BY server_url
                ORDER BY total_tasks_processed DESC
            """, (str(job_id),))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_stale_workers(max_age_minutes: int = 10) -> List[WorkerHeartbeat]:
        """Get workers with stale heartbeats."""
        cutoff_time = datetime.now() - timedelta(minutes=max_age_minutes)

        with get_cursor() as cursor:
            cursor.execute("""
                SELECT id, worker_id, server_url, job_id, status,
                       last_heartbeat, tasks_processed, current_task_id, created_at
                FROM worker_heartbeats
                WHERE last_heartbeat < %s AND status = 'active'
                ORDER BY last_heartbeat ASC
            """, (cutoff_time,))
            rows = cursor.fetchall()
            return [WorkerHeartbeat.from_dict(dict(row)) for row in rows]

    @staticmethod
    def update_worker_status(worker_id: str, status: str) -> bool:
        """Update the status of a worker."""
        with get_cursor() as cursor:
            cursor.execute("""
                UPDATE worker_heartbeats
                SET status = %s, last_heartbeat = CURRENT_TIMESTAMP
                WHERE worker_id = %s
            """, (status, worker_id))
            return cursor.rowcount > 0
