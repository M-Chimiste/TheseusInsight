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
            reports = cur.fetchall()
            
            # Parse JSON fields for each report
            for report in reports:
                # Handle both string (from database) and already-parsed dict cases
                mindmap_data_raw = report.get('mindmap_data_json')
                if isinstance(mindmap_data_raw, str):
                    report['mindmap_data'] = json.loads(mindmap_data_raw) if mindmap_data_raw else {}
                elif isinstance(mindmap_data_raw, dict):
                    report['mindmap_data'] = mindmap_data_raw
                else:
                    report['mindmap_data'] = {}
                    
                parameters_raw = report.get('parameters_json')
                if isinstance(parameters_raw, str):
                    report['parameters'] = json.loads(parameters_raw) if parameters_raw else {}
                elif isinstance(parameters_raw, dict):
                    report['parameters'] = parameters_raw
                else:
                    report['parameters'] = {}
                    
                statistics_raw = report.get('statistics_json')
                if isinstance(statistics_raw, str):
                    report['statistics'] = json.loads(statistics_raw) if statistics_raw else {}
                elif isinstance(statistics_raw, dict):
                    report['statistics'] = statistics_raw
                else:
                    report['statistics'] = {}
                
            return reports

    @staticmethod
    def get(report_id: int) -> Dict[str, Any] | None:
        with get_cursor() as cur:
            cur.execute("SELECT * FROM mindmap_reports WHERE id = %s", (report_id,))
            report = cur.fetchone()
            
            if report:
                # Parse JSON fields with type checking
                mindmap_data_raw = report.get('mindmap_data_json')
                if isinstance(mindmap_data_raw, str):
                    report['mindmap_data'] = json.loads(mindmap_data_raw) if mindmap_data_raw else {}
                elif isinstance(mindmap_data_raw, dict):
                    report['mindmap_data'] = mindmap_data_raw
                else:
                    report['mindmap_data'] = {}
                    
                parameters_raw = report.get('parameters_json')
                if isinstance(parameters_raw, str):
                    report['parameters'] = json.loads(parameters_raw) if parameters_raw else {}
                elif isinstance(parameters_raw, dict):
                    report['parameters'] = parameters_raw
                else:
                    report['parameters'] = {}
                    
                statistics_raw = report.get('statistics_json')
                if isinstance(statistics_raw, str):
                    report['statistics'] = json.loads(statistics_raw) if statistics_raw else {}
                elif isinstance(statistics_raw, dict):
                    report['statistics'] = statistics_raw
                else:
                    report['statistics'] = {}
                
            return report

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
    def update_data(
        report_id: int,
        mindmap_data: Dict[str, Any],
        parameters: Dict[str, Any],
        statistics: Dict[str, Any] | None = None,
        title: str | None = None,
        description: str | None = None,
    ) -> bool:
        with get_cursor() as cur:
            # Build dynamic SET clause based on provided fields
            set_parts = [
                "mindmap_data_json = %s",
                "parameters_json = %s",
                "statistics_json = %s",
            ]
            values: list = [
                json.dumps(mindmap_data),
                json.dumps(parameters),
                json.dumps(statistics) if statistics else None,
            ]

            if title is not None:
                set_parts.append("title = %s")
                values.append(title)
            if description is not None:
                set_parts.append("description = %s")
                values.append(description)

            values.append(report_id)

            cur.execute(
                f"UPDATE mindmap_reports SET {', '.join(set_parts)} WHERE id = %s",
                tuple(values),
            )
            return cur.rowcount > 0 