from __future__ import annotations

from typing import List, Dict

from ..db import get_cursor


class ModelProviderRepository:
    """CRUD for `model_providers` table."""

    @staticmethod
    def all() -> List[Dict[str, str]]:
        with get_cursor() as cur:
            cur.execute("SELECT id, name FROM model_providers ORDER BY id")
            return cur.fetchall()

    @staticmethod
    def add(provider_id: int, name: str) -> None:
        with get_cursor() as cur:
            cur.execute(
                "INSERT INTO model_providers (id, name) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (provider_id, name),
            )

    @staticmethod
    def delete(provider_id: int) -> None:
        with get_cursor() as cur:
            cur.execute("DELETE FROM model_providers WHERE id = %s", (provider_id,)) 