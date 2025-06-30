from __future__ import annotations

from typing import Any, Dict, List
import numpy as np
import json

from ..db import get_cursor
from .base import to_pgvector


class PaperFulltextRepository:
    """CRUD for paper_fulltext table (full text and embedding)."""

    @staticmethod
    def insert_or_update(paper_id: int, content: str, embedding: List[float] | None = None, embedding_model: str | None = None) -> int:
        emb_literal = to_pgvector(embedding)
        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO paper_fulltext (paper_id, content, embedding, embedding_model, created_at)
                VALUES (%s,%s,%s,%s, now())
                ON CONFLICT (paper_id) DO UPDATE SET
                    content = EXCLUDED.content,
                    embedding = EXCLUDED.embedding,
                    embedding_model = EXCLUDED.embedding_model,
                    created_at = EXCLUDED.created_at
                RETURNING id
                """,
                (paper_id, content, emb_literal, embedding_model),
            )
            row = cur.fetchone()
            return row["id"] if row else 0

    @staticmethod
    def insert(paper_id: int, content: str, embedding: str | List[float] | None = None, 
               embedding_model: str | None = None, extraction_method: str = "unknown", 
               metadata: str | None = None) -> int:
        """Insert new paper fulltext record."""
        # Handle embedding conversion
        emb_literal = None
        if embedding:
            if isinstance(embedding, str):
                # Try to parse JSON string to list, then convert to pgvector
                try:
                    emb_list = json.loads(embedding)
                    emb_literal = to_pgvector(emb_list)
                except:
                    # If not JSON, assume it's already in pgvector format
                    emb_literal = embedding
            elif isinstance(embedding, (list, tuple)):
                emb_literal = to_pgvector(embedding)
        
        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO paper_fulltext (paper_id, content, embedding, embedding_model, extraction_method, metadata, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, now())
                RETURNING id
                """,
                (paper_id, content, emb_literal, embedding_model, extraction_method, metadata),
            )
            row = cur.fetchone()
            return row["id"] if row else 0

    @staticmethod
    def get(paper_id: int) -> Dict[str, Any] | None:
        with get_cursor() as cur:
            cur.execute("SELECT * FROM paper_fulltext WHERE paper_id = %s", (paper_id,))
            return cur.fetchone()

    @staticmethod
    def has_fulltext(paper_id: int) -> bool:
        with get_cursor() as cur:
            cur.execute("SELECT 1 FROM paper_fulltext WHERE paper_id = %s", (paper_id,))
            return cur.fetchone() is not None 

    @staticmethod
    def exists(paper_id: int) -> bool:
        """Check if paper fulltext exists for given paper_id."""
        return PaperFulltextRepository.has_fulltext(paper_id) 