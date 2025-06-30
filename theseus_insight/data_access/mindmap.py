from __future__ import annotations

from typing import Any, Dict, List
import json

from ..db import get_cursor


class MindmapReportRepository:
    """CRUD for `mindmap_reports` table."""

    @staticmethod
    def insert(title: str, description: str | None, seed_paper_id: int, seed_paper_title: str, mindmap_data: Dict[str, Any], parameters: Dict[str, Any], statistics: Dict[str, Any] | None = None) -> int:
        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO mindmap_reports (title, description, seed_paper_id, seed_paper_title, mindmap_data_json, parameters_json, statistics_json, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s, now())
                RETURNING id
                """,
                (
                    title,
                    description,
                    seed_paper_id,
                    seed_paper_title,
                    json.dumps(mindmap_data),
                    json.dumps(parameters),
                    json.dumps(statistics) if statistics else None,
                ),
            )
            row = cur.fetchone()
            return row["id"] if row else 0

    @staticmethod
    def list(limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        with get_cursor() as cur:
            cur.execute(
                "SELECT * FROM mindmap_reports ORDER BY created_at DESC LIMIT %s OFFSET %s",
                (limit, offset),
            )
            return cur.fetchall()

    @staticmethod
    def get(report_id: int) -> Dict[str, Any] | None:
        with get_cursor() as cur:
            cur.execute("SELECT * FROM mindmap_reports WHERE id = %s", (report_id,))
            return cur.fetchone()

    @staticmethod
    def delete(report_id: int) -> None:
        with get_cursor() as cur:
            cur.execute("DELETE FROM mindmap_reports WHERE id = %s", (report_id,))

    @staticmethod
    def update_title(report_id: int, new_title: str) -> None:
        with get_cursor() as cur:
            cur.execute("UPDATE mindmap_reports SET title = %s WHERE id = %s", (new_title, report_id))

    @staticmethod
    def update_description(report_id: int, new_description: str | None):
        with get_cursor() as cur:
            cur.execute("UPDATE mindmap_reports SET description = %s WHERE id = %s", (new_description, report_id))

    @staticmethod
    def update_data(report_id: int, mindmap_data: Dict[str, Any], parameters: Dict[str, Any], statistics: Dict[str, Any] | None = None):
        with get_cursor() as cur:
            cur.execute(
                """
                UPDATE mindmap_reports SET mindmap_data_json = %s, parameters_json = %s, statistics_json = %s WHERE id = %s
                """,
                (json.dumps(mindmap_data), json.dumps(parameters), json.dumps(statistics) if statistics else None, report_id),
            ) 