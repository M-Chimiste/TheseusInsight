"""
Data access layer for scheduled tasks.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
import json
from ..db import get_cursor
from .base import build_set_clause


class ScheduledTasksRepository:
    """Repository for scheduled tasks operations."""
    
    @staticmethod
    def get_all(
        profile_id: Optional[int] = None,
        task_type: Optional[str] = None,
        is_enabled: Optional[bool] = None
    ) -> List[Dict[str, Any]]:
        """Get all scheduled tasks with optional filtering."""
        with get_cursor() as cursor:
            query = """
                SELECT st.*, p.name as profile_name
                FROM scheduled_tasks st
                LEFT JOIN profiles p ON st.profile_id = p.id
                WHERE 1=1
            """
            params = []
            
            if profile_id is not None:
                query += " AND st.profile_id = %s"
                params.append(profile_id)
            
            if task_type:
                query += " AND st.task_type = %s"
                params.append(task_type)
                
            if is_enabled is not None:
                query += " AND st.is_enabled = %s"
                params.append(is_enabled)
                
            query += " ORDER BY st.created_at DESC"
            
            cursor.execute(query, params)
            return cursor.fetchall()
    
    @staticmethod
    def get_by_id(task_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific scheduled task by ID."""
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT st.*, p.name as profile_name
                FROM scheduled_tasks st
                LEFT JOIN profiles p ON st.profile_id = p.id
                WHERE st.id = %s
            """, (task_id,))
            return cursor.fetchone()
    
    @staticmethod
    def create(
        name: str,
        task_type: str,
        frequency: str,
        hour: int,
        minute: int = 0,
        profile_id: Optional[int] = None,
        is_enabled: bool = True,
        day_of_week: Optional[int] = None,
        day_of_month: Optional[int] = None,
        timezone: str = "UTC",
        config: Optional[Dict[str, Any]] = None,
        next_run_at: Optional[datetime] = None
    ) -> int:
        """Create a new scheduled task."""
        with get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO scheduled_tasks (
                    name, task_type, profile_id, is_enabled, frequency,
                    day_of_week, day_of_month, hour, minute, timezone,
                    config, next_run_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                ) RETURNING id
            """, (
                name,
                task_type,
                profile_id,
                is_enabled,
                frequency,
                day_of_week,
                day_of_month,
                hour,
                minute,
                timezone,
                json.dumps(config or {}),
                next_run_at
            ))
            return cursor.fetchone()['id']
    
    @staticmethod
    def update(
        task_id: int,
        name: Optional[str] = None,
        is_enabled: Optional[bool] = None,
        frequency: Optional[str] = None,
        hour: Optional[int] = None,
        minute: Optional[int] = None,
        day_of_week: Optional[int] = None,
        day_of_month: Optional[int] = None,
        timezone: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        next_run_at: Optional[datetime] = None
    ) -> bool:
        """Update a scheduled task."""
        candidates = {
            "name": name,
            "is_enabled": is_enabled,
            "frequency": frequency,
            "hour": hour,
            "minute": minute,
            "day_of_week": day_of_week,
            "day_of_month": day_of_month,
            "timezone": timezone,
            "config": json.dumps(config) if config is not None else None,
            "next_run_at": next_run_at,
        }
        updates = {k: v for k, v in candidates.items() if v is not None}
        if not updates:
            return True

        set_sql, values = build_set_clause(updates)
        with get_cursor() as cursor:
            cursor.execute(
                f"UPDATE scheduled_tasks SET {set_sql} WHERE id = %s",
                [*values, task_id],
            )
            return cursor.rowcount > 0
    
    @staticmethod
    def delete(task_id: int) -> bool:
        """Delete a scheduled task."""
        with get_cursor() as cursor:
            cursor.execute("DELETE FROM scheduled_tasks WHERE id = %s", (task_id,))
            return cursor.rowcount > 0
    
    @staticmethod
    def update_run_info(
        task_id: int,
        last_run_at: datetime,
        last_run_task_id: str,
        last_run_status: str,
        next_run_at: Optional[datetime] = None,
        increment_run_count: bool = False,
        increment_error_count: bool = False
    ):
        """Update run information for a scheduled task."""
        updates = {
            "last_run_at": last_run_at,
            "last_run_task_id": last_run_task_id,
            "last_run_status": last_run_status,
        }
        if next_run_at is not None:
            updates["next_run_at"] = next_run_at

        extra = []
        if increment_run_count:
            extra.append("run_count = run_count + 1")
        if increment_error_count:
            extra.append("error_count = error_count + 1")

        set_sql, values = build_set_clause(updates, extra=extra)
        with get_cursor() as cursor:
            cursor.execute(
                f"UPDATE scheduled_tasks SET {set_sql} WHERE id = %s",
                [*values, task_id],
            )
    
    @staticmethod
    def get_enabled_tasks() -> List[Dict[str, Any]]:
        """Get all enabled scheduled tasks."""
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM scheduled_tasks
                WHERE is_enabled = true
                ORDER BY next_run_at
            """)
            return cursor.fetchall()


class ScheduledTaskRunsRepository:
    """Repository for scheduled task run history."""
    
    @staticmethod
    def create(
        scheduled_task_id: int,
        task_id: str,
        started_at: datetime,
        status: str = 'running'
    ) -> int:
        """Create a new task run record."""
        with get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO scheduled_task_runs (
                    scheduled_task_id, task_id, started_at, status
                ) VALUES (%s, %s, %s, %s)
                RETURNING id
            """, (scheduled_task_id, task_id, started_at, status))
            return cursor.fetchone()['id']
    
    @staticmethod
    def update(
        run_id: int,
        completed_at: Optional[datetime] = None,
        status: Optional[str] = None,
        error_message: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None
    ):
        """Update a task run record."""
        candidates = {
            "completed_at": completed_at,
            "status": status,
            "error_message": error_message,
            "result": json.dumps(result) if result is not None else None,
        }
        updates = {k: v for k, v in candidates.items() if v is not None}
        if updates:
            set_sql, values = build_set_clause(updates)
            with get_cursor() as cursor:
                cursor.execute(
                    f"UPDATE scheduled_task_runs SET {set_sql} WHERE id = %s",
                    [*values, run_id],
                )
    
    @staticmethod
    def get_by_task_id(scheduled_task_id: int, limit: int = 10, offset: int = 0) -> List[Dict[str, Any]]:
        """Get run history for a scheduled task."""
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM scheduled_task_runs
                WHERE scheduled_task_id = %s
                ORDER BY started_at DESC
                LIMIT %s OFFSET %s
            """, (scheduled_task_id, limit, offset))
            return cursor.fetchall()
    
    @staticmethod
    def get_latest_run(scheduled_task_id: int) -> Optional[Dict[str, Any]]:
        """Get the latest run for a scheduled task."""
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM scheduled_task_runs
                WHERE scheduled_task_id = %s
                ORDER BY started_at DESC
                LIMIT 1
            """, (scheduled_task_id,))
            return cursor.fetchone()