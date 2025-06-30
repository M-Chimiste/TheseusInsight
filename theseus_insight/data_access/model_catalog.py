from __future__ import annotations

from typing import Any, Dict, List
import json

from ..db import get_cursor


class ModelCatalogRepository:
    """CRUD for the `model_catalog` table."""

    @staticmethod
    def insert(entry: Dict[str, Any]) -> int:
        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO model_catalog (alias, model_string, provider_name, model_type, description,
                    max_new_tokens, temperature, num_ctx, trust_remote_code, tags_json, is_favorite)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id
                """,
                (
                    entry["alias"],
                    entry["model_string"],
                    entry["provider_name"],
                    entry["model_type"],
                    entry.get("description"),
                    entry.get("max_new_tokens"),
                    entry.get("temperature"),
                    entry.get("num_ctx"),
                    bool(entry.get("trust_remote_code", False)),
                    json.dumps(entry.get("tags", [])),
                    bool(entry.get("is_favorite", False)),
                ),
            )
            row = cur.fetchone()
            return row["id"] if row else 0

    @staticmethod
    def update(model_id: int, updates: Dict[str, Any]) -> None:
        if not updates:
            return
        fields: List[str] = []
        params: List[Any] = []
        for key, value in updates.items():
            if key == "tags":
                value = json.dumps(value)
                column = "tags_json"
            else:
                column = key
            fields.append(f"{column} = %s")
            params.append(value)
        fields.append("updated_at = now()")
        params.append(model_id)
        sql = f"UPDATE model_catalog SET {', '.join(fields)} WHERE id = %s"
        with get_cursor() as cur:
            cur.execute(sql, params)

    @staticmethod
    def toggle_favorite(model_id: int) -> None:
        with get_cursor() as cur:
            cur.execute(
                "UPDATE model_catalog SET is_favorite = NOT is_favorite, updated_at = now() WHERE id = %s",
                (model_id,),
            )

    @staticmethod
    def get(model_id: int) -> Dict[str, Any] | None:
        with get_cursor() as cur:
            cur.execute("SELECT * FROM model_catalog WHERE id = %s", (model_id,))
            return cur.fetchone()

    @staticmethod
    def search(
        *,
        search: str | None = None,
        provider: str | None = None,
        model_type: str | None = None,
        is_favorite: bool | None = None,
        tags: List[str] | None = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM model_catalog"
        conditions: List[str] = []
        params: List[Any] = []
        if search:
            conditions.append("(alias ILIKE %s OR model_string ILIKE %s OR description ILIKE %s)")
            pattern = f"%{search}%"
            params.extend([pattern, pattern, pattern])
        if provider:
            conditions.append("provider_name = %s")
            params.append(provider)
        if model_type:
            conditions.append("model_type = %s")
            params.append(model_type)
        if is_favorite is not None:
            conditions.append("is_favorite = %s")
            params.append(is_favorite)
        if tags:
            tag_conditions = ["tags_json @> %s"] * len(tags)
            conditions.append("(" + " OR ".join(tag_conditions) + ")")
            params.extend([json.dumps([tag]) for tag in tags])
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY updated_at DESC LIMIT %s"
        params.append(limit)
        with get_cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()

    @staticmethod
    def delete(model_id: int) -> None:
        with get_cursor() as cur:
            cur.execute("DELETE FROM model_catalog WHERE id = %s", (model_id,)) 