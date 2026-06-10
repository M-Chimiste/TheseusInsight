from __future__ import annotations

from typing import Any, Dict, List
import json

from ..db import get_cursor
from .base import build_set_clause


class TaskRepository:
    """CRUD for the `tasks` table."""

    # ------------------------------------------------------------------
    # Inserts / Updates
    # ------------------------------------------------------------------

    @staticmethod
    def upsert(
        task_id: str,
        task_type: str,
        status: str,
        config_json: Dict[str, Any],
        *,
        start_time: str | None = None,
        progress: float | None = None,
        current_step: str | None = None,
        message: str | None = None,
    ) -> None:
        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO tasks (task_id, task_type, status, config_json, start_time, progress, current_step, message)
                VALUES (%s,%s,%s,%s,COALESCE(%s, now()),%s,%s,%s)
                ON CONFLICT (task_id) DO UPDATE SET
                    task_type = EXCLUDED.task_type,
                    status = EXCLUDED.status,
                    config_json = EXCLUDED.config_json,
                    start_time = EXCLUDED.start_time,
                    progress = EXCLUDED.progress,
                    current_step = EXCLUDED.current_step,
                    message = EXCLUDED.message
                """,
                (
                    task_id,
                    task_type,
                    status,
                    json.dumps(config_json),
                    start_time,
                    progress,
                    current_step,
                    message,
                ),
            )

    @staticmethod
    def update_status(
        task_id: str,
        status: str,
        *,
        progress: float | None = None,
        current_step: str | None = None,
        message: str | None = None,
        error: str | None = None,
        result_json: Dict[str, Any] | None = None,
        end_time: str | None = None,
        metadata: Dict[str, Any] | None = None,
    ) -> None:
        candidates = {
            "progress": progress,
            "current_step": current_step,
            "message": message,
            "error": error,
            "result_json": json.dumps(result_json) if result_json is not None else None,
            "end_time": end_time,
            "metadata": json.dumps(metadata) if metadata is not None else None,
        }
        updates = {"status": status, **{k: v for k, v in candidates.items() if v is not None}}
        set_sql, params = build_set_clause(updates)
        with get_cursor() as cur:
            cur.execute(f"UPDATE tasks SET {set_sql} WHERE task_id = %s", [*params, task_id])

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @staticmethod
    def get(task_id: str) -> Dict[str, Any] | None:
        with get_cursor() as cur:
            cur.execute("SELECT * FROM tasks WHERE task_id = %s", (task_id,))
            return cur.fetchone()

    @staticmethod
    def recent(limit: int = 100, *, from_date: str | None = None, to_date: str | None = None) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM tasks"
        params: List[Any] = []
        conditions: List[str] = []
        if from_date:
            conditions.append("start_time >= %s")
            params.append(f"{from_date} 00:00:00")
        if to_date:
            conditions.append("start_time <= %s")
            params.append(f"{to_date} 23:59:59")
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY start_time DESC LIMIT %s"
        params.append(limit)
        with get_cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()

    @staticmethod
    def get_active_tasks(task_types: List[str] | None = None) -> List[Dict[str, Any]]:
        """Get all active (pending/processing) tasks, optionally filtered by type."""
        sql = "SELECT * FROM tasks WHERE status IN ('pending', 'processing')"
        params: List[Any] = []
        
        if task_types:
            placeholders = ','.join(['%s'] * len(task_types))
            sql += f" AND task_type IN ({placeholders})"
            params.extend(task_types)
        
        sql += " ORDER BY start_time DESC"
        
        with get_cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()

    @staticmethod
    def get_recent_completed_tasks(task_types: List[str] | None = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent completed tasks, optionally filtered by type."""
        sql = "SELECT * FROM tasks WHERE status = 'completed'"
        params: List[Any] = []
        
        if task_types:
            placeholders = ','.join(['%s'] * len(task_types))
            sql += f" AND task_type IN ({placeholders})"
            params.extend(task_types)
        
        sql += " ORDER BY end_time DESC LIMIT %s"
        params.append(limit)
        
        with get_cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()

    @staticmethod
    def delete(task_id: str) -> None:
        with get_cursor() as cur:
            cur.execute("DELETE FROM tasks WHERE task_id = %s", (task_id,))

    # Aliases for compatibility with research_agent.py
    @staticmethod
    def insert_task(
        task_id: str,
        task_type: str,
        status: str,
        config_json: Dict[str, Any],
        *,
        start_time: str | None = None,
        progress: float | None = None,
        current_step: str | None = None,
        message: str | None = None,
    ) -> None:
        TaskRepository.upsert(task_id, task_type, status, config_json, start_time=start_time, progress=progress, current_step=current_step, message=message)

    @staticmethod
    def update_task_status(
        task_id: str,
        status: str,
        *,
        progress: float | None = None,
        current_step: str | None = None,
        message: str | None = None,
        error: str | None = None,
        result_json: Dict[str, Any] | None = None,
        end_time: str | None = None,
        metadata: Dict[str, Any] | None = None,
    ) -> None:
        TaskRepository.update_status(task_id, status, progress=progress, current_step=current_step, message=message, error=error, result_json=result_json, end_time=end_time, metadata=metadata)

    @staticmethod
    def get_task(task_id: str) -> Dict[str, Any] | None:
        return TaskRepository.get(task_id)

    @staticmethod
    def delete_task(task_id: str) -> None:
        TaskRepository.delete(task_id) 