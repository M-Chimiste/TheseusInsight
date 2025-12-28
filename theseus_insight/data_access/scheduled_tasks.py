"""
Data access layer for scheduled tasks.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
import json
from ..db import get_cursor


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
        update_fields = []
        update_values = []
        
        if name is not None:
            update_fields.append("name = %s")
            update_values.append(name)
            
        if is_enabled is not None:
            update_fields.append("is_enabled = %s")
            update_values.append(is_enabled)
            
        if frequency is not None:
            update_fields.append("frequency = %s")
            update_values.append(frequency)
            
        if hour is not None:
            update_fields.append("hour = %s")
            update_values.append(hour)
            
        if minute is not None:
            update_fields.append("minute = %s")
            update_values.append(minute)
            
        if day_of_week is not None:
            update_fields.append("day_of_week = %s")
            update_values.append(day_of_week)
            
        if day_of_month is not None:
            update_fields.append("day_of_month = %s")
            update_values.append(day_of_month)
            
        if timezone is not None:
            update_fields.append("timezone = %s")
            update_values.append(timezone)
            
        if config is not None:
            update_fields.append("config = %s")
            update_values.append(json.dumps(config))
            
        if next_run_at is not None:
            update_fields.append("next_run_at = %s")
            update_values.append(next_run_at)
        
        if not update_fields:
            return True
        
        with get_cursor() as cursor:
            update_values.append(task_id)
            cursor.execute(f"""
                UPDATE scheduled_tasks 
                SET {', '.join(update_fields)}
                WHERE id = %s
            """, update_values)
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
        with get_cursor() as cursor:
            query_parts = [
                "last_run_at = %s",
                "last_run_task_id = %s",
                "last_run_status = %s"
            ]
            params = [last_run_at, last_run_task_id, last_run_status]
            
            if next_run_at is not None:
                query_parts.append("next_run_at = %s")
                params.append(next_run_at)
            
            if increment_run_count:
                query_parts.append("run_count = run_count + 1")
                
            if increment_error_count:
                query_parts.append("error_count = error_count + 1")
            
            params.append(task_id)
            cursor.execute(f"""
                UPDATE scheduled_tasks 
                SET {', '.join(query_parts)}
                WHERE id = %s
            """, params)
    
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
        update_fields = []
        update_values = []
        
        if completed_at is not None:
            update_fields.append("completed_at = %s")
            update_values.append(completed_at)
            
        if status is not None:
            update_fields.append("status = %s")
            update_values.append(status)
            
        if error_message is not None:
            update_fields.append("error_message = %s")
            update_values.append(error_message)
            
        if result is not None:
            update_fields.append("result = %s")
            update_values.append(json.dumps(result))
        
        if update_fields:
            update_values.append(run_id)
            with get_cursor() as cursor:
                cursor.execute(f"""
                    UPDATE scheduled_task_runs
                    SET {', '.join(update_fields)}
                    WHERE id = %s
                """, update_values)
    
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