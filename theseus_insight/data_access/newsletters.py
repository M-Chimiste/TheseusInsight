from __future__ import annotations

from typing import Any, Dict, List

from ..db import get_cursor


class NewsletterRepository:
    """CRUD for `newsletters` table."""

    @staticmethod
    def insert(newsletter: Any) -> int:
        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO newsletters (content, start_date, end_date, date_sent)
                VALUES (%s,%s,%s,%s)
                RETURNING id
                """,
                (
                    newsletter.content,
                    newsletter.start_date,
                    newsletter.end_date,
                    newsletter.date_sent,
                ),
            )
            row = cur.fetchone()
            return row["id"] if row else 0

    @staticmethod
    def all() -> List[Dict[str, Any]]:
        with get_cursor() as cur:
            cur.execute("SELECT * FROM newsletters ORDER BY id DESC")
            return cur.fetchall() 