from __future__ import annotations

from typing import List, Dict, Any

from ..db import get_cursor


class LogsRepository:
    """CRUD operations for the `logs` table."""

    # ------------------------------------------------------------------
    # Insert or update
    # ------------------------------------------------------------------

    @staticmethod
    def upsert(task_id: str, status: str, datetime_run: str | None = None) -> None:
        """Insert a new log row or update status if task_id exists."""
        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO logs (task_id, status, datetime_run)
                VALUES (%s, %s, COALESCE(%s, now()))
                ON CONFLICT (task_id) DO UPDATE SET status = EXCLUDED.status
                """,
                (task_id, status, datetime_run),
            )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @staticmethod
    def recent(limit: int = 100, *, from_date: str | None = None, to_date: str | None = None) -> List[Dict[str, Any]]:
        sql = "SELECT task_id, status, datetime_run FROM logs"
        params: list[Any] = []
        conditions: list[str] = []
        if from_date:
            conditions.append("datetime_run >= %s")
            params.append(f"{from_date} 00:00:00")
        if to_date:
            conditions.append("datetime_run <= %s")
            params.append(f"{to_date} 23:59:59")
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY datetime_run DESC LIMIT %s"
        params.append(limit)
        with get_cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall() 