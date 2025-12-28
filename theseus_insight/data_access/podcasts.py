from __future__ import annotations

from typing import Any, Dict, List

from ..db import get_cursor
import json


class PodcastRepository:
    """CRUD operations for `podcasts` table."""

    @staticmethod
    def insert(podcast: Any) -> int:
        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO podcasts (title, date, script, description)
                VALUES (%s,%s,%s,%s)
                RETURNING id
                """,
                (
                    podcast.title,
                    podcast.date,
                    json.dumps(podcast.script),
                    podcast.description,
                ),
            )
            row = cur.fetchone()
            return row["id"] if row else 0

    @staticmethod
    def all() -> List[Dict[str, Any]]:
        with get_cursor() as cur:
            cur.execute("SELECT * FROM podcasts ORDER BY id DESC")
            return cur.fetchall()

    @staticmethod
    def get(podcast_id: int) -> Dict[str, Any] | None:
        with get_cursor() as cur:
            cur.execute("SELECT * FROM podcasts WHERE id = %s", (podcast_id,))
            return cur.fetchone()

    @staticmethod
    def delete(podcast_id: int) -> None:
        with get_cursor() as cur:
            cur.execute("DELETE FROM podcasts WHERE id = %s", (podcast_id,))

    @staticmethod
    def update_title(podcast_id: int, new_title: str) -> None:
        with get_cursor() as cur:
            cur.execute(
                "UPDATE podcasts SET title = %s WHERE id = %s", (new_title, podcast_id)
            ) 