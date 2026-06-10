from __future__ import annotations

from typing import Any, Dict, List
import json

from ..db import get_cursor
from .base import build_set_clause


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
        columns = {
            ("tags_json" if key == "tags" else key):
                (json.dumps(value) if key == "tags" else value)
            for key, value in updates.items()
        }
        set_sql, params = build_set_clause(columns, extra=("updated_at = now()",))
        with get_cursor() as cur:
            cur.execute(
                f"UPDATE model_catalog SET {set_sql} WHERE id = %s", [*params, model_id]
            )

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
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        conditions: List[str] = []
        params: List[Any] = []
        
        # Build WHERE conditions
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
        
        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
        
        with get_cursor() as cur:
            # Get total count
            count_sql = f"SELECT COUNT(*) FROM model_catalog{where_clause}"
            cur.execute(count_sql, params)
            total_count = cur.fetchone()["count"]
            
            # Get paginated results
            offset = (page - 1) * page_size
            data_sql = f"SELECT * FROM model_catalog{where_clause} ORDER BY updated_at DESC LIMIT %s OFFSET %s"
            data_params = params + [page_size, offset]
            cur.execute(data_sql, data_params)
            models = cur.fetchall()
            
            # Calculate pagination info
            total_pages = (total_count + page_size - 1) // page_size
            
            return {
                "models": models,
                "total_count": total_count,
                "total_pages": total_pages,
                "current_page": page,
                "page_size": page_size
            }

    @staticmethod
    def delete(model_id: int) -> None:
        with get_cursor() as cur:
            cur.execute("DELETE FROM model_catalog WHERE id = %s", (model_id,)) 