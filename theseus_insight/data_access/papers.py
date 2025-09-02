from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple
import json

from psycopg import sql

from ..db import get_cursor
from .base import to_pgvector

VECTOR_DIM = 768  # TODO configurable


class PaperRepository:
    """CRUD and search operations for the `papers` table."""

    # ---------------------------------------------------------------------
    # Existence helpers
    # ---------------------------------------------------------------------

    @staticmethod
    def exists_by_url(url: str) -> bool:
        with get_cursor() as cur:
            cur.execute("SELECT 1 FROM papers WHERE url = %s LIMIT 1", (url,))
            return cur.fetchone() is not None

    @staticmethod
    def exists_by_title(title: str) -> bool:
        with get_cursor() as cur:
            cur.execute("SELECT 1 FROM papers WHERE title = %s LIMIT 1", (title,))
            return cur.fetchone() is not None

    @staticmethod
    def bulk_check_existence(urls: Optional[List[str]] = None, titles: Optional[List[str]] = None) -> Tuple[Set[str], Set[str]]:
        """
        Check existence of multiple papers by URLs and/or titles in a single query.
        
        Args:
            urls: List of URLs to check (optional)
            titles: List of titles to check (optional)
            
        Returns:
            Tuple of (existing_urls, existing_titles)
        """
        existing_urls = set()
        existing_titles = set()
        
        with get_cursor() as cur:
            # Check URLs if provided
            if urls:
                # Use ANY for efficient bulk checking
                cur.execute(
                    "SELECT DISTINCT url FROM papers WHERE url = ANY(%s) AND url IS NOT NULL",
                    (urls,)
                )
                existing_urls = {row["url"] for row in cur.fetchall()}
            
            # Check titles if provided
            if titles:
                cur.execute(
                    "SELECT DISTINCT title FROM papers WHERE title = ANY(%s) AND title IS NOT NULL",
                    (titles,)
                )
                existing_titles = {row["title"] for row in cur.fetchall()}
        
        return existing_urls, existing_titles

    @staticmethod
    def get_all_urls_and_titles() -> Tuple[Set[str], Set[str]]:
        """
        Get all existing URLs and titles for duplicate checking.
        More efficient for large-scale duplicate checking than individual queries.
        
        Returns:
            Tuple of (all_urls, all_titles)
        """
        with get_cursor() as cur:
            cur.execute("SELECT url FROM papers WHERE url IS NOT NULL")
            all_urls = {row["url"] for row in cur.fetchall()}
            
            cur.execute("SELECT title FROM papers WHERE title IS NOT NULL")
            all_titles = {row["title"] for row in cur.fetchall()}
            
        return all_urls, all_titles

    # ---------------------------------------------------------------------
    # Inserts
    # ---------------------------------------------------------------------

    @staticmethod
    def insert(paper: Any, *, skip_duplicates: bool = True) -> bool:
        """Insert a new paper row.

        The `paper` argument may be a dataclass from existing models or any
        object exposing the expected attributes.
        """
        if skip_duplicates and PaperRepository.exists_by_url(paper.url):
            return False

        emb_literal = to_pgvector(getattr(paper, "embedding", None))

        with get_cursor() as cur:
            cur.execute(
                sql.SQL(
                    """
                    INSERT INTO papers
                        (title, abstract, date, date_run, score, rationale, related,
                         cosine_similarity, url, embedding_model, embedding, text)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """
                ),
                (
                    paper.title,
                    paper.abstract,
                    paper.date,
                    paper.date_run,
                    float(paper.score) if paper.score is not None else None,
                    paper.rationale,
                    bool(paper.related),
                    float(paper.cosine_similarity) if paper.cosine_similarity is not None else None,
                    paper.url,
                    paper.embedding_model,
                    emb_literal,
                    getattr(paper, "text", None),
                ),
            )
        return True

    @staticmethod
    def bulk_insert(papers: List[Any], *, skip_duplicates: bool = True, progress_callback=None) -> Dict[str, int]:
        """Bulk insert papers in a single transaction for improved performance.
        
        Args:
            papers: List of Paper objects to insert
            skip_duplicates: Whether to skip papers that already exist
            progress_callback: Optional callback function(current, total, message)
            
        Returns:
            Dictionary with statistics: {"total": int, "imported": int, "skipped": int, "errors": int}
        """
        stats = {"total": len(papers), "imported": 0, "skipped": 0, "errors": 0}
        
        if not papers:
            return stats
            
        # Get existing URLs for duplicate checking if needed
        existing_urls = set()
        existing_titles = set()
        if skip_duplicates:
            # Use optimized method to get all URLs and titles at once
            existing_urls, existing_titles = PaperRepository.get_all_urls_and_titles()
        
        # Process papers in batches to avoid memory issues
        batch_size = 1000
        for batch_start in range(0, len(papers), batch_size):
            batch_end = min(batch_start + batch_size, len(papers))
            batch = papers[batch_start:batch_end]
            
            # Prepare batch data
            batch_data = []
            for paper in batch:
                # Skip duplicates if requested
                if skip_duplicates:
                    if (paper.url in existing_urls or paper.title in existing_titles):
                        stats["skipped"] += 1
                        continue
                
                try:
                    emb_literal = to_pgvector(getattr(paper, "embedding", None))
                    batch_data.append((
                        paper.title,
                        paper.abstract,
                        paper.date,
                        paper.date_run,
                        float(paper.score) if paper.score is not None else None,
                        paper.rationale,
                        bool(paper.related),
                        float(paper.cosine_similarity) if paper.cosine_similarity is not None else None,
                        paper.url,
                        paper.embedding_model,
                        emb_literal,
                        getattr(paper, "text", None),
                    ))
                    
                    # Add to existing sets to prevent duplicates within this batch
                    if skip_duplicates:
                        existing_urls.add(paper.url)
                        existing_titles.add(paper.title)
                        
                except Exception as e:
                    print(f"Error preparing paper '{getattr(paper, 'title', 'Unknown')}': {e}")
                    print(f"Paper data: title={getattr(paper, 'title', None)}, url={getattr(paper, 'url', None)}")
                    import traceback
                    print(f"Full traceback: {traceback.format_exc()}")
                    stats["errors"] += 1
            
            # Bulk insert this batch
            if batch_data:
                try:
                    with get_cursor() as cur:
                        cur.executemany(
                            """
                            INSERT INTO papers
                                (title, abstract, date, date_run, score, rationale, related,
                                 cosine_similarity, url, embedding_model, embedding, text)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                            """,
                            batch_data
                        )
                    stats["imported"] += len(batch_data)
                except Exception as e:
                    print(f"Error during batch insert: {e}")
                    import traceback
                    print(f"Batch insert traceback: {traceback.format_exc()}")
                    print(f"Batch size: {len(batch_data)}")
                    if batch_data:
                        print(f"Sample batch item: {batch_data[0]}")
                    stats["errors"] += len(batch_data)
            
            # Report progress
            if progress_callback:
                progress_callback(batch_end, len(papers), f"Bulk importing papers: {batch_end}/{len(papers)}")
        
        return stats

    # ---------------------------------------------------------------------
    # Retrieval
    # ---------------------------------------------------------------------

    @staticmethod
    def get_by_id(paper_id: int) -> Dict[str, Any] | None:
        with get_cursor() as cur:
            cur.execute(
                "SELECT * FROM papers WHERE id = %s", (paper_id,)
            )
            return cur.fetchone()

    # ---------------------------------------------------------------------
    # Similarity search
    # ---------------------------------------------------------------------

    @staticmethod
    def find_similar(
        query_embedding: List[float],
        *,
        limit: int = 10,
        similarity_threshold: float = 0.7,
    ) -> List[Dict[str, Any]]:
        # Use the same pgvector format as the working insert method
        emb_literal = to_pgvector(query_embedding)
        
        with get_cursor() as cur:
            cur.execute(
                sql.SQL(
                    """
                    SELECT *, (1 - (embedding <=> %s::vector))::float AS similarity_score
                    FROM papers
                    WHERE embedding IS NOT NULL
                      AND (1 - (embedding <=> %s::vector))::float >= %s
                    ORDER BY similarity_score DESC
                    LIMIT %s
                    """
                ),
                (emb_literal, emb_literal, similarity_threshold, limit),
            )
            rows = cur.fetchall()

        results: List[Dict[str, Any]] = []
        for row in rows:
            row = dict(row)
            row["similarity_distance"] = 1 - row["similarity_score"]
            results.append(row)
        return results

    @staticmethod
    def find_similar_existing(paper_id: int, *, limit: int = 10, similarity_threshold: float = 0.7):
        # Get reference paper embedding
        with get_cursor() as cur:
            cur.execute("SELECT * FROM papers WHERE id = %s AND embedding IS NOT NULL", (paper_id,))
            ref = cur.fetchone()
        if not ref:
            return None

        ref_embedding = ref["embedding"]
        if ref_embedding is None:
            return None

        query_embedding = ref_embedding  # already stored literal string like '[...]'
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT *, 1 - (embedding <=> %s)::float AS similarity_score
                FROM papers
                WHERE id != %s AND embedding IS NOT NULL AND (1 - (embedding <=> %s)::float) >= %s
                ORDER BY similarity_score DESC LIMIT %s
                """,
                (query_embedding, paper_id, query_embedding, similarity_threshold, limit),
            )
            similars = cur.fetchall()

        return {
            "reference_paper": ref,
            "similar_papers": similars,
            "total_similar": len(similars),
        }

    # ---------------------------------------------------------------------
    # Pagination & filtering
    # ---------------------------------------------------------------------

    @staticmethod
    def paginate(
        *,
        page: int = 1,
        page_size: int = 10,
        min_score: float | None = None,
        max_score: float | None = None,
        sort_field: str = "score",
        sort_direction: str = "desc",
        search: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        profile_ids: List[int] | None = None,
        min_profile_score: float | None = None,
        max_profile_score: float | None = None,
        profile_related_only: bool = False,
    ) -> Dict[str, Any]:
        
        # Determine if we need profile filtering
        has_profile_filters = (
            profile_ids is not None or 
            min_profile_score is not None or 
            max_profile_score is not None or 
            profile_related_only
        )
        
        if has_profile_filters:
            # Use profile-aware query with joins
            if profile_ids:
                # Join with paper_profile_scores for specific profiles
                sql = """
                    SELECT DISTINCT p.*, 
                           pps.score as profile_score,
                           pps.related as profile_related,
                           pps.rationale as profile_rationale,
                           pps.date_scored as profile_date_scored,
                           pps.judge_model as profile_judge_model,
                           pps.profile_id
                    FROM papers p
                    INNER JOIN paper_profile_scores pps ON p.id = pps.paper_id
                """
            else:
                # Just regular papers query - profile filters will be ignored
                sql = "SELECT * FROM papers"
        else:
            # Regular papers query without profile data
            sql = "SELECT * FROM papers"
        
        conditions: List[str] = []
        params: List[Any] = []

        # Regular paper filters
        if min_score is not None:
            conditions.append("p.score >= %s" if has_profile_filters and profile_ids else "score >= %s")
            params.append(min_score)
        if max_score is not None:
            conditions.append("p.score <= %s" if has_profile_filters and profile_ids else "score <= %s")
            params.append(max_score)
        if from_date:
            conditions.append("p.date >= %s" if has_profile_filters and profile_ids else "date >= %s")
            params.append(from_date)
        if to_date:
            conditions.append("p.date <= %s" if has_profile_filters and profile_ids else "date <= %s")
            params.append(to_date)
        if search:
            conditions.append("p.fts @@ plainto_tsquery('english', %s)" if has_profile_filters and profile_ids else "fts @@ plainto_tsquery('english', %s)")
            params.append(search)
        
        # Profile-specific filters
        if has_profile_filters and profile_ids:
            # Filter by specific profiles
            placeholders = ', '.join(['%s'] * len(profile_ids))
            conditions.append(f"pps.profile_id IN ({placeholders})")
            params.extend(profile_ids)
            
            # Profile score filters
            if min_profile_score is not None:
                conditions.append("pps.score >= %s")
                params.append(min_profile_score)
            if max_profile_score is not None:
                conditions.append("pps.score <= %s")
                params.append(max_profile_score)
            if profile_related_only:
                conditions.append("pps.related = TRUE")
        
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)

        # Build count query separately to avoid string replacement issues
        if has_profile_filters and profile_ids:
            sql_count = """
                SELECT COUNT(DISTINCT p.id) as count
                FROM papers p
                INNER JOIN paper_profile_scores pps ON p.id = pps.paper_id
            """
        else:
            sql_count = "SELECT COUNT(*) as count FROM papers"
        
        # Add the same WHERE conditions to count query
        if conditions:
            sql_count += " WHERE " + " AND ".join(conditions)

        # Sorting
        if sort_field not in {"score", "date", "id", "profile_score"}:
            sort_field = "score"
        
        # Adjust sort field for profile queries
        if has_profile_filters and profile_ids:
            if sort_field == "score":
                sort_field = "p.score"
            elif sort_field == "date":
                sort_field = "p.date"
            elif sort_field == "id":
                sort_field = "p.id"
            elif sort_field == "profile_score":
                sort_field = "pps.score"
        
        direction = "DESC" if sort_direction.lower() == "desc" else "ASC"
        sql += f" ORDER BY {sort_field} {direction} LIMIT %s OFFSET %s"
        offset = (page - 1) * page_size
        params_count = list(params)  # copy for count query
        params.extend([page_size, offset])

        with get_cursor() as cur:
            cur.execute(sql_count, params_count)
            total_items = cur.fetchone()["count"]
            cur.execute(sql, params)
            items = cur.fetchall()

        total_pages = (total_items + page_size - 1) // page_size if total_items else 0
        return {
            "items": items,
            "total_items": total_items,
            "total_pages": total_pages,
            "has_next_page": page < total_pages,
        }

    # ---------------------------------------------------------------------
    # Embedding helpers
    # ---------------------------------------------------------------------

    @staticmethod
    def without_embeddings() -> List[Dict[str, Any]]:
        with get_cursor() as cur:
            cur.execute("SELECT * FROM papers WHERE embedding IS NULL ORDER BY id DESC")
            return cur.fetchall()

    @staticmethod
    def update_embedding(paper_id: int, embedding: List[float]):
        emb_literal = to_pgvector(embedding)
        with get_cursor() as cur:
            cur.execute(
                "UPDATE papers SET embedding = %s WHERE id = %s",
                (emb_literal, paper_id),
            )

    @staticmethod
    def bulk_update_embeddings(updates: List[Tuple[int, List[float]]]):
        """
        Bulk update embeddings for multiple papers.
        
        Args:
            updates: List of tuples (paper_id, embedding)
        """
        if not updates:
            return
        
        with get_cursor() as cur:
            # Build arrays for bulk update
            paper_ids = []
            embedding_strs = []
            
            for paper_id, embedding in updates:
                paper_ids.append(paper_id)
                # Convert embedding to PostgreSQL vector format
                emb_literal = to_pgvector(embedding)
                embedding_strs.append(emb_literal)
            
            # Use UNNEST to perform bulk update
            query = """
                UPDATE papers 
                SET embedding = data.embedding::vector
                FROM (
                    SELECT unnest(%s::int[]) as id,
                           unnest(%s::text[]::vector[]) as embedding
                ) as data
                WHERE papers.id = data.id
            """
            
            cur.execute(query, (paper_ids, embedding_strs))

    # ---------------------------------------------------------------------
    # Convenience wrappers for router compatibility
    # ---------------------------------------------------------------------

    @staticmethod
    def semantic_search(query_text: str, embedding_model, *, limit: int = 10, similarity_threshold: float = 0.7):
        query_embedding = embedding_model.invoke(query_text)
        if hasattr(query_embedding, "tolist"):
            query_embedding = query_embedding.tolist()
        return PaperRepository.find_similar(query_embedding, limit=limit, similarity_threshold=similarity_threshold)

    @staticmethod
    def hybrid_search(
        query_text: str,
        embedding_model,
        *,
        page: int = 1,
        page_size: int = 10,
        semantic_weight: float = 0.6,
        keyword_weight: float = 0.4,
        min_score: float | None = None,
        max_score: float | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        similarity_threshold: float = 0.3,
    ) -> Dict[str, Any]:
        query_embedding = embedding_model.invoke(query_text)
        if hasattr(query_embedding, "tolist"):
            query_embedding = query_embedding.tolist()

        # Use the same pgvector format as the working insert method
        emb_literal = to_pgvector(query_embedding)
        
        sql_inner = (
            "SELECT *, (1 - (embedding <=> %s::vector))::float AS semantic_score, "
            "ts_rank(fts, plainto_tsquery('english', %s)) AS keyword_score "
            "FROM papers WHERE embedding IS NOT NULL"
        )
        params: List[Any] = [emb_literal, query_text]
        conditions: List[str] = []
        if min_score is not None:
            conditions.append("score >= %s")
            params.append(min_score)
        if max_score is not None:
            conditions.append("score <= %s")
            params.append(max_score)
        if from_date:
            conditions.append("date >= %s")
            params.append(from_date)
        if to_date:
            conditions.append("date <= %s")
            params.append(to_date)
        if conditions:
            sql_inner += " AND " + " AND ".join(conditions)

        # Embed scalar weights/threshold directly to avoid placeholder confusion
        sql_outer = (
            f"SELECT sub.*, (sub.semantic_score * {semantic_weight} + "
            f"sub.keyword_score * {keyword_weight}) AS hybrid_score "
            f"FROM ({sql_inner}) sub WHERE sub.semantic_score >= {similarity_threshold} "
            "ORDER BY hybrid_score DESC"
        )

        offset = (page - 1) * page_size
        sql_paginated = sql_outer + " LIMIT %s OFFSET %s"

        params_inner = list(params)  # copy for count query
        params_paginated = list(params) + [page_size, offset]

        with get_cursor() as cur:
            cur.execute("SELECT count(*) FROM (" + sql_outer + ") AS cnt", params_inner)
            total_items = cur.fetchone()["count"]
            cur.execute(sql_paginated, params_paginated)
            items = cur.fetchall()

        total_pages = (total_items + page_size - 1) // page_size if total_items else 0
        return {
            "items": items,
            "total_items": total_items,
            "total_pages": total_pages,
            "current_page": page,
        }

    @staticmethod
    def search_seed(query: str, limit: int = 10):
        """Search papers by title/abstract for mind-map seed selection."""
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT id, title, abstract, date, score, url
                FROM papers
                WHERE fts @@ plainto_tsquery('english', %s)
                ORDER BY ts_rank(fts, plainto_tsquery('english', %s)) DESC
                LIMIT %s
                """,
                (query, query, limit),
            )
            return cur.fetchall()

    # ---------------------------------------------------------------------
    # Alias methods for compatibility with legacy code
    # ---------------------------------------------------------------------

    @staticmethod
    def insert_paper(paper: Any, *, skip_duplicates: bool = True) -> bool:
        """Alias for insert method."""
        return PaperRepository.insert(paper, skip_duplicates=skip_duplicates)

    @staticmethod
    def get_by_url(url: str) -> Dict[str, Any] | None:
        """Get paper by URL."""
        with get_cursor() as cur:
            cur.execute("SELECT * FROM papers WHERE url = %s", (url,))
            return cur.fetchone()

    @staticmethod
    def get_all() -> List[Dict[str, Any]]:
        """Get all papers."""
        with get_cursor() as cur:
            cur.execute("SELECT * FROM papers ORDER BY id DESC")
            return cur.fetchall()

    @staticmethod
    def update_keywords(paper_id: int, keywords: List[str]) -> None:
        """Update keywords for a paper."""
        keywords_json = json.dumps(keywords) if keywords else None
        with get_cursor() as cur:
            cur.execute(
                "UPDATE papers SET keywords_json = %s WHERE id = %s",
                (keywords_json, paper_id)
            )

    @staticmethod
    def bulk_update_keywords(updates: List[Tuple[int, List[str]]]) -> int:
        """
        Update keywords for multiple papers in a single batch.
        
        Args:
            updates: List of tuples containing (paper_id, keywords_list)
            
        Returns:
            Number of papers updated
        """
        if not updates:
            return 0
            
        with get_cursor() as cur:
            # Prepare data for executemany
            values = []
            for paper_id, keywords in updates:
                keywords_json = json.dumps(keywords) if keywords else None
                values.append((keywords_json, paper_id))
            
            cur.executemany(
                "UPDATE papers SET keywords_json = %s WHERE id = %s",
                values
            )
            return cur.rowcount

    # For backward compatibility
    paper_exists_by_url = exists_by_url 

    # ---------------------------------------------------------------------
    # Mindmap-specific methods
    # ---------------------------------------------------------------------

    @staticmethod
    def find_similar_mindmap(
        seed_paper_id: int, *, k: int = 15, similarity_threshold: float = 0.3,
        profile_ids: Optional[List[int]] = None, min_profile_score: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """Find similar papers for mindmap generation with optional profile filtering."""
        # Get seed paper embedding
        with get_cursor() as cur:
            cur.execute(
                "SELECT embedding FROM papers WHERE id = %s AND embedding IS NOT NULL", 
                (seed_paper_id,)
            )
            seed_row = cur.fetchone()
            
        if not seed_row or not seed_row["embedding"]:
            return []
            
        seed_embedding = seed_row["embedding"]
        
        # Base query for similarity search
        if profile_ids:
            # Profile-filtered query
            query = """
                SELECT DISTINCT p.*, 1 - (p.embedding <=> %s)::float AS similarity_score,
                       pps.score as profile_score, pps.related as profile_related
                FROM papers p
                INNER JOIN paper_profile_scores pps ON p.id = pps.paper_id
                WHERE p.id != %s 
                  AND p.embedding IS NOT NULL 
                  AND (1 - (p.embedding <=> %s)::float) >= %s
                  AND pps.profile_id = ANY(%s)
            """
            params = [seed_embedding, seed_paper_id, seed_embedding, similarity_threshold, profile_ids]
            
            if min_profile_score is not None:
                query += " AND pps.score >= %s"
                params.append(min_profile_score)
                
            query += " ORDER BY similarity_score DESC LIMIT %s"
            params.append(k)
        else:
            # Regular similarity search without profile filtering
            query = """
                SELECT *, 1 - (embedding <=> %s)::float AS similarity_score
                FROM papers 
                WHERE id != %s 
                  AND embedding IS NOT NULL 
                  AND (1 - (embedding <=> %s)::float) >= %s
                ORDER BY similarity_score DESC 
                LIMIT %s
            """
            params = [seed_embedding, seed_paper_id, seed_embedding, similarity_threshold, k]
        
        with get_cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()

    @staticmethod
    def get_keywords(paper_id: int) -> List[str] | None:
        """Get keywords for a paper."""
        with get_cursor() as cur:
            cur.execute("SELECT keywords_json FROM papers WHERE id = %s", (paper_id,))
            row = cur.fetchone()
            if row and row["keywords_json"]:
                try:
                    return json.loads(row["keywords_json"])
                except (json.JSONDecodeError, TypeError):
                    return []
            return []

    @staticmethod
    def get_summary(paper_id: int) -> str | None:
        """Get paper summary/text."""
        with get_cursor() as cur:
            cur.execute("SELECT summary FROM papers WHERE id = %s", (paper_id,))
            row = cur.fetchone()
            return row["summary"] if row else None

    @staticmethod
    def update_summary(paper_id: int, summary: str) -> None:
        """Update paper summary/text."""
        with get_cursor() as cur:
            cur.execute(
                "UPDATE papers SET summary = %s WHERE id = %s",
                (summary, paper_id)
            )

    @staticmethod
    def get_text(paper_id: int) -> str | None:
        """Get paper full text."""
        with get_cursor() as cur:
            cur.execute("SELECT text FROM papers WHERE id = %s", (paper_id,))
            row = cur.fetchone()
            return row["text"] if row else None

    @staticmethod
    def update_text(paper_id: int, text: str) -> None:
        """Update paper full text."""
        with get_cursor() as cur:
            cur.execute(
                "UPDATE papers SET text = %s WHERE id = %s",
                (text, paper_id)
            )

    # ---------------------------------------------------------------------
    # Legacy compatibility aliases for mindmap conversion
    # ---------------------------------------------------------------------

    @staticmethod
    def get(paper_id: int) -> Dict[str, Any] | None:
        """Alias for get_by_id() - legacy compatibility."""
        return PaperRepository.get_by_id(paper_id)

    @staticmethod
    def get_paper_by_id(paper_id: int) -> Dict[str, Any] | None:
        """Legacy method name - use get_by_id() instead."""
        return PaperRepository.get_by_id(paper_id)

    @staticmethod
    def update_paper_embedding(paper_id: int, embedding: List[float]) -> None:
        """Legacy method name - use update_embedding() instead."""
        return PaperRepository.update_embedding(paper_id, embedding)

    @staticmethod
    def get_paper_keywords(paper_id: int) -> List[str] | None:
        """Legacy method name - use get_keywords() instead."""
        return PaperRepository.get_keywords(paper_id)

    @staticmethod
    def update_paper_keywords(paper_id: int, keywords: List[str]) -> None:
        """Legacy method name - use update_keywords() instead."""
        return PaperRepository.update_keywords(paper_id, keywords)

    @staticmethod
    def get_paper_summary(paper_id: int) -> str | None:
        """Legacy method name - use get_summary() instead."""
        return PaperRepository.get_summary(paper_id)

    @staticmethod
    def update_paper_summary(paper_id: int, summary: str) -> None:
        """Legacy method name - use update_summary() instead."""
        return PaperRepository.update_summary(paper_id, summary)

    @staticmethod
    def get_paper_text(paper_id: int) -> str | None:
        """Legacy method name - use get_text() instead."""
        return PaperRepository.get_text(paper_id)

    @staticmethod
    def update_paper_text(paper_id: int, text: str) -> None:
        """Legacy method name - use update_text() instead."""
        return PaperRepository.update_text(paper_id, text)

    @staticmethod
    def find_similar_papers_mindmap(
        seed_paper_id: int, k: int = 15, similarity_threshold: float = 0.3,
        profile_ids: Optional[List[int]] = None, min_profile_score: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """Legacy method name - use find_similar_mindmap() instead."""
        return PaperRepository.find_similar_mindmap(
            seed_paper_id, k=k, similarity_threshold=similarity_threshold,
            profile_ids=profile_ids, min_profile_score=min_profile_score
        )

    # ---------------------------------------------------------------------
    # Utility script support methods
    # ---------------------------------------------------------------------

    @staticmethod
    def get_papers_without_embeddings() -> List[Dict[str, Any]]:
        """Get papers that don't have embeddings yet - used by backfill utility."""
        return PaperRepository.without_embeddings()

    @staticmethod
    def get_papers_without_keywords() -> List[Dict[str, Any]]:
        """Get papers that don't have keywords yet - used by backfill utility."""
        with get_cursor() as cur:
            cur.execute(
                "SELECT id, title, abstract FROM papers WHERE keywords_json IS NULL OR keywords_json = '' ORDER BY id DESC"
            )
            return cur.fetchall()

    @staticmethod
    def get_papers_with_embeddings(limit: int = 10000, offset: int = 0) -> List[Dict[str, Any]]:
        """Get papers that have embeddings for trend analysis."""
        with get_cursor() as cur:
            # If limit is very large (100000+), remove it to get all papers
            if limit >= 100000:
                cur.execute(
                    "SELECT * FROM papers WHERE embedding IS NOT NULL ORDER BY date DESC OFFSET %s",
                    (offset,)
                )
            else:
                cur.execute(
                    "SELECT * FROM papers WHERE embedding IS NOT NULL ORDER BY date DESC LIMIT %s OFFSET %s",
                    (limit, offset)
                )
            return cur.fetchall()

    @staticmethod
    def get_papers_in_date_range(start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get papers within a date range.

        Args:
            start_date: Start date in YYYY-MM-DD format (inclusive)
            end_date: End date in YYYY-MM-DD format (inclusive)

        Returns:
            List of paper dictionaries
        """
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"PaperRepository.get_papers_in_date_range called with start_date={start_date}, end_date={end_date}")

        with get_cursor() as cur:
            query = """
                SELECT id, title, abstract, date, url, score, related, rationale, 
                       cosine_similarity, embedding_model, date_run
                FROM papers 
                WHERE 1=1
            """
            params = []
            
            if start_date:
                query += " AND date >= %s"
                params.append(start_date)
                
            if end_date:
                query += " AND date <= %s"
                params.append(end_date)
                
            query += " ORDER BY date DESC"
            
            cur.execute(query, params)
            rows = cur.fetchall()
            logger.info(f"Query executed with params: {params}")
            logger.info(f"Query returned {len(rows)} rows")

            return [
                {
                    'id': row['id'],
                    'title': row['title'],
                    'abstract': row['abstract'],
                    'date': row['date'],
                    'url': row['url'],
                    'score': row['score'],
                    'related': row['related'],
                    'rationale': row['rationale'],
                    'cosine_similarity': row['cosine_similarity'],
                    'embedding_model': row['embedding_model'],
                    'date_run': row['date_run']
                }
                for row in rows
            ]
    
    @staticmethod
    def get_paper_ids_in_date_range(start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[int]:
        """
        Get only paper IDs within a date range for efficient filtering.
        
        Args:
            start_date: Start date in YYYY-MM-DD format (inclusive)
            end_date: End date in YYYY-MM-DD format (inclusive)
            
        Returns:
            List of paper IDs
        """
        with get_cursor() as cur:
            query = "SELECT id FROM papers WHERE 1=1"
            params = []
            
            if start_date:
                query += " AND date >= %s"
                params.append(start_date)
                
            if end_date:
                query += " AND date <= %s"
                params.append(end_date)
                
            cur.execute(query, params)
            return [row['id'] for row in cur.fetchall()] 