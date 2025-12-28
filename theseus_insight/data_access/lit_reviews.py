from __future__ import annotations

from typing import Any, Dict, List
import json

from ..db import get_cursor


class LitReviewRepository:
    """CRUD for `lit_reviews` table."""

    @staticmethod
    def insert(research_question: str, summary_json: Dict[str, Any], trace_json: Dict[str, Any], report_text: str | None = None) -> int:
        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO lit_reviews (research_question, summary_json, trace_json, report_text, created_ts)
                VALUES (%s,%s,%s,%s, now())
                RETURNING id
                """,
                (
                    research_question,
                    json.dumps(summary_json),
                    json.dumps(trace_json),
                    report_text,
                ),
            )
            row = cur.fetchone()
            return row["id"] if row else 0

    @staticmethod
    def get(review_id: int) -> Dict[str, Any] | None:
        with get_cursor() as cur:
            cur.execute("SELECT * FROM lit_reviews WHERE id = %s", (review_id,))
            return cur.fetchone()

    @staticmethod
    def recent(limit: int = 10) -> List[Dict[str, Any]]:
        with get_cursor() as cur:
            cur.execute("SELECT * FROM lit_reviews ORDER BY created_ts DESC LIMIT %s", (limit,))
            return cur.fetchall()

    @staticmethod
    def all() -> List[Dict[str, Any]]:
        with get_cursor() as cur:
            cur.execute("SELECT * FROM lit_reviews ORDER BY created_ts")
            return cur.fetchall() 