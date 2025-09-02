"""Data access layer for research profiles and related functionality."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from psycopg import sql

from ..db import get_cursor
from .base import to_pgvector


class ProfileRepository:
    """CRUD operations for the `research_profiles` table."""

    # ---------------------------------------------------------------------
    # Basic CRUD Operations
    # ---------------------------------------------------------------------

    @staticmethod
    def create(
        name: str,
        description: Optional[str] = None,
        color: Optional[str] = None,
        tags: Optional[List[str]] = None,
        email_recipients: Optional[List[str]] = None,
        arxiv_filters: Optional[Dict[str, Any]] = None,
        is_default: bool = False
    ) -> Dict[str, Any]:
        """Create a new research profile."""
        tags_json = json.dumps(tags) if tags else None
        recipients_json = json.dumps(email_recipients) if email_recipients else None
        filters_json = json.dumps(arxiv_filters) if arxiv_filters else None
        
        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO research_profiles 
                (name, description, color, tags, email_recipients, arxiv_filters, is_default, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (name, description, color, tags_json, recipients_json, filters_json, is_default, True)
            )
            return cur.fetchone()

    @staticmethod
    def get_by_id(profile_id: int) -> Optional[Dict[str, Any]]:
        """Get a profile by its ID."""
        with get_cursor() as cur:
            cur.execute(
                "SELECT * FROM research_profiles WHERE id = %s",
                (profile_id,)
            )
            return cur.fetchone()

    @staticmethod
    def get_by_name(name: str) -> Optional[Dict[str, Any]]:
        """Get a profile by its name."""
        with get_cursor() as cur:
            cur.execute(
                "SELECT * FROM research_profiles WHERE name = %s",
                (name,)
            )
            return cur.fetchone()

    @staticmethod
    def get_default() -> Optional[Dict[str, Any]]:
        """Get the default profile."""
        with get_cursor() as cur:
            cur.execute(
                "SELECT * FROM research_profiles WHERE is_default = TRUE"
            )
            return cur.fetchone()

    @staticmethod
    def get_all(include_inactive: bool = False) -> List[Dict[str, Any]]:
        """Get all profiles, optionally including inactive ones."""
        conditions = ["TRUE"]
        if not include_inactive:
            conditions.append("is_active = TRUE")
        
        with get_cursor() as cur:
            cur.execute(
                f"SELECT * FROM research_profiles WHERE {' AND '.join(conditions)} ORDER BY name"
            )
            return cur.fetchall()

    @staticmethod
    def update(
        profile_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        color: Optional[str] = None,
        tags: Optional[List[str]] = None,
        email_recipients: Optional[List[str]] = None,
        arxiv_filters: Optional[Dict[str, Any]] = None,
        is_active: Optional[bool] = None
    ) -> Optional[Dict[str, Any]]:
        """Update a profile. Only provided fields are updated."""
        updates = []
        params = []
        
        if name is not None:
            updates.append("name = %s")
            params.append(name)
        if description is not None:
            updates.append("description = %s")
            params.append(description)
        if color is not None:
            updates.append("color = %s")
            params.append(color)
        if tags is not None:
            updates.append("tags = %s")
            params.append(json.dumps(tags))
        if email_recipients is not None:
            updates.append("email_recipients = %s")
            params.append(json.dumps(email_recipients))
        if arxiv_filters is not None:
            updates.append("arxiv_filters = %s")
            params.append(json.dumps(arxiv_filters))
        if is_active is not None:
            updates.append("is_active = %s")
            params.append(is_active)
        
        if not updates:
            return ProfileRepository.get_by_id(profile_id)
        
        updates.append("updated_at = %s")
        params.append(datetime.now())
        params.append(profile_id)
        
        with get_cursor() as cur:
            cur.execute(
                f"UPDATE research_profiles SET {', '.join(updates)} WHERE id = %s RETURNING *",
                params
            )
            return cur.fetchone()

    @staticmethod
    def delete(profile_id: int) -> bool:
        """Delete a profile. Returns True if successful."""
        with get_cursor() as cur:
            # Check if it's the default profile
            cur.execute("SELECT is_default FROM research_profiles WHERE id = %s", (profile_id,))
            result = cur.fetchone()
            if result and result["is_default"]:
                raise ValueError("Cannot delete the default profile")
            
            cur.execute("DELETE FROM research_profiles WHERE id = %s", (profile_id,))
            return cur.rowcount > 0

    @staticmethod
    def deactivate(profile_id: int) -> Optional[Dict[str, Any]]:
        """Mark a profile as inactive instead of deleting it."""
        return ProfileRepository.update(profile_id, is_active=False)

    # ---------------------------------------------------------------------
    # Tag-based Operations
    # ---------------------------------------------------------------------

    @staticmethod
    def get_all_tags() -> List[str]:
        """Get all unique tags across all profiles."""
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT jsonb_array_elements_text(tags) as tag 
                FROM research_profiles 
                WHERE tags IS NOT NULL AND tags != 'null'::jsonb
                ORDER BY tag
                """
            )
            return [row["tag"] for row in cur.fetchall()]

    @staticmethod
    def search_tags(query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search for tags matching a query with usage counts."""
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT tag, COUNT(*) as usage_count
                FROM (
                    SELECT jsonb_array_elements_text(tags) as tag 
                    FROM research_profiles 
                    WHERE tags IS NOT NULL AND tags != 'null'::jsonb
                ) tag_list
                WHERE tag ILIKE %s
                GROUP BY tag
                ORDER BY usage_count DESC, tag
                LIMIT %s
                """,
                (f"%{query}%", limit)
            )
            return [{"tag": row["tag"], "usage_count": row["usage_count"]} 
                   for row in cur.fetchall()]

    @staticmethod
    def get_by_tag(tag: str) -> List[Dict[str, Any]]:
        """Get all profiles that have a specific tag."""
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT * FROM research_profiles 
                WHERE tags ? %s AND is_active = TRUE
                ORDER BY name
                """,
                (tag,)
            )
            return cur.fetchall()

    @staticmethod
    def get_by_tags(tags: List[str]) -> List[Dict[str, Any]]:
        """
        Get profiles that have any of the specified tags.
        
        Args:
            tags: List of tag names to search for
            
        Returns:
            List of profile dictionaries
        """
        if not tags:
            return []
            
        with get_cursor() as cur:
            # Use JSONB array operations to find profiles with any of the specified tags
            placeholders = ', '.join(['%s'] * len(tags))
            cur.execute(f"""
                SELECT id, name, description, color, tags, email_recipients, 
                       arxiv_filters, is_active, is_default, created_at, updated_at
                FROM research_profiles
                WHERE is_active = TRUE 
                  AND tags ?| ARRAY[{placeholders}]
                ORDER BY is_default DESC, name ASC
            """, tags)
            
            rows = cur.fetchall()
            return [
                {
                    'id': row['id'],
                    'name': row['name'],
                    'description': row['description'],
                    'color': row['color'],
                    'tags': row['tags'],
                    'email_recipients': row['email_recipients'],
                    'arxiv_filters': row['arxiv_filters'],
                    'is_active': row['is_active'],
                    'is_default': row['is_default'],
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at']
                }
                for row in rows
            ]

    # ---------------------------------------------------------------------
    # Utility Methods
    # ---------------------------------------------------------------------

    @staticmethod
    def exists_by_name(name: str, exclude_id: Optional[int] = None) -> bool:
        """Check if a profile with the given name exists."""
        conditions = ["name = %s"]
        params = [name]
        
        if exclude_id is not None:
            conditions.append("id != %s")
            params.append(exclude_id)
        
        with get_cursor() as cur:
            cur.execute(
                f"SELECT 1 FROM research_profiles WHERE {' AND '.join(conditions)} LIMIT 1",
                params
            )
            return cur.fetchone() is not None

    @staticmethod
    def clone(source_profile_id: int, new_name: str) -> Dict[str, Any]:
        """Create a copy of an existing profile with a new name."""
        source = ProfileRepository.get_by_id(source_profile_id)
        if not source:
            raise ValueError(f"Source profile {source_profile_id} not found")
        
        if ProfileRepository.exists_by_name(new_name):
            raise ValueError(f"Profile with name '{new_name}' already exists")
        
        # Create new profile with same settings
        new_profile = ProfileRepository.create(
            name=new_name,
            description=f"Cloned from {source['name']}",
            color=source.get("color"),
            tags=json.loads(source["tags"]) if source.get("tags") else None,
            email_recipients=json.loads(source["email_recipients"]) if source.get("email_recipients") else None,
            arxiv_filters=json.loads(source["arxiv_filters"]) if source.get("arxiv_filters") else None,
            is_default=False
        )
        
        # Clone research interests
        ProfileInterestsRepository.clone_interests(source_profile_id, new_profile["id"])
        
        return new_profile

    @staticmethod
    def get_stats(profile_id: int) -> Dict[str, Any]:
        """Get statistics for a profile."""
        with get_cursor() as cur:
            # Get interest count
            cur.execute(
                "SELECT COUNT(*) as interest_count FROM profile_research_interests WHERE profile_id = %s",
                (profile_id,)
            )
            interest_count = cur.fetchone()["interest_count"]
            
            # Get paper score count
            cur.execute(
                "SELECT COUNT(*) as score_count FROM paper_profile_scores WHERE profile_id = %s",
                (profile_id,)
            )
            score_count = cur.fetchone()["score_count"]
            
            # Get relevant papers count
            cur.execute(
                "SELECT COUNT(*) as relevant_count FROM paper_profile_scores WHERE profile_id = %s AND related = TRUE",
                (profile_id,)
            )
            relevant_count = cur.fetchone()["relevant_count"]
            
            # Get average score
            cur.execute(
                "SELECT AVG(score) as avg_score FROM paper_profile_scores WHERE profile_id = %s AND score IS NOT NULL",
                (profile_id,)
            )
            avg_score_result = cur.fetchone()
            avg_score = float(avg_score_result["avg_score"]) if avg_score_result["avg_score"] is not None else None
            
        return {
            "interest_count": interest_count,
            "total_scored_papers": score_count,
            "relevant_papers": relevant_count,
            "average_score": avg_score
        }

    @staticmethod
    def get_all_active() -> List[Dict[str, Any]]:
        """Get all active profiles."""
        with get_cursor() as cur:
            cur.execute("""
                SELECT id, name, description, color, tags, email_recipients, 
                       arxiv_filters, is_active, is_default, created_at, updated_at
                FROM research_profiles
                WHERE is_active = TRUE
                ORDER BY is_default DESC, name ASC
            """)
            
            rows = cur.fetchall()
            return [
                {
                    'id': row['id'],
                    'name': row['name'],
                    'description': row['description'],
                    'color': row['color'],
                    'tags': row['tags'],
                    'email_recipients': row['email_recipients'],
                    'arxiv_filters': row['arxiv_filters'],
                    'is_active': row['is_active'],
                    'is_default': row['is_default'],
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at']
                }
                for row in rows
            ]

    @staticmethod
    def get_papers_for_profile(
        profile_id: int,
        min_score: Optional[float] = None,
        related_only: bool = False,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get papers scored for a specific profile.
        
        Args:
            profile_id: ID of the profile
            min_score: Minimum score filter
            related_only: Only return papers marked as related
            limit: Maximum number of papers to return
            offset: Number of papers to skip for pagination
            
        Returns:
            List of papers with profile-specific scoring
        """
        with get_cursor() as cur:
            query = """
                SELECT p.*, pps.score as profile_score, pps.related as profile_related,
                       pps.rationale as profile_rationale, pps.date_scored as profile_date_scored,
                       pps.judge_model as profile_judge_model
                FROM papers p
                INNER JOIN paper_profile_scores pps ON p.id = pps.paper_id
                WHERE pps.profile_id = %s
            """
            params = [profile_id]
            
            if min_score is not None:
                query += " AND pps.score >= %s"
                params.append(min_score)
                
            if related_only:
                query += " AND pps.related = TRUE"
                
            query += " ORDER BY pps.score DESC, p.date DESC LIMIT %s OFFSET %s"
            params.extend([limit, offset])
            
            cur.execute(query, params)
            return cur.fetchall()

    @staticmethod
    def get_profile_scores_for_paper(paper_id: int) -> List[Dict[str, Any]]:
        """
        Get all profile scores for a specific paper.
        
        Args:
            paper_id: ID of the paper
            
        Returns:
            List of profile scores for the paper
        """
        with get_cursor() as cur:
            cur.execute("""
                SELECT pps.*, rp.name as profile_name, rp.description as profile_description
                FROM paper_profile_scores pps
                INNER JOIN research_profiles rp ON pps.profile_id = rp.id
                WHERE pps.paper_id = %s AND rp.is_active = TRUE
                ORDER BY pps.score DESC
            """, (paper_id,))
            
            return cur.fetchall()

    @staticmethod
    def remove_profile_scores(profile_id: int) -> int:
        """
        Remove all scores for a specific profile.
        
        Args:
            profile_id: ID of the profile
            
        Returns:
            Number of scores removed
        """
        with get_cursor() as cur:
            cur.execute("""
                DELETE FROM paper_profile_scores
                WHERE profile_id = %s
            """, (profile_id,))
            
            return cur.rowcount

    @staticmethod
    def remove_paper_scores(paper_id: int) -> int:
        """
        Remove all profile scores for a specific paper.
        
        Args:
            paper_id: ID of the paper
            
        Returns:
            Number of scores removed
        """
        with get_cursor() as cur:
            cur.execute("""
                DELETE FROM paper_profile_scores
                WHERE paper_id = %s
            """, (paper_id,))
            
            return cur.rowcount

    @staticmethod
    def get_unscored_papers_for_profile(
        profile_id: int,
        limit: int = 100,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get papers that don't have scores for a specific profile.
        
        Args:
            profile_id: ID of the profile
            limit: Maximum number of papers to return
            from_date: Start date filter (YYYY-MM-DD)
            to_date: End date filter (YYYY-MM-DD)
            
        Returns:
            List of papers without scores for the profile
        """
        with get_cursor() as cur:
            query = """
                SELECT p.*
                FROM papers p
                WHERE p.id NOT IN (
                    SELECT pps.paper_id 
                    FROM paper_profile_scores pps 
                    WHERE pps.profile_id = %s
                )
            """
            params = [profile_id]
            
            if from_date:
                query += " AND p.date >= %s"
                params.append(from_date)
                
            if to_date:
                query += " AND p.date <= %s"
                params.append(to_date)
                
            query += " ORDER BY p.date DESC LIMIT %s"
            params.append(limit)
            
            cur.execute(query, params)
            return cur.fetchall()


class ProfileInterestsRepository:
    """CRUD operations for the `profile_research_interests` table."""

    @staticmethod
    def create(
        profile_id: int,
        interest_text: str,
        embedding: Optional[List[float]] = None,
        embedding_model: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new research interest for a profile."""
        emb_literal = to_pgvector(embedding) if embedding else None
        
        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO profile_research_interests 
                (profile_id, interest_text, embedding, embedding_model)
                VALUES (%s, %s, %s, %s)
                RETURNING *
                """,
                (profile_id, interest_text, emb_literal, embedding_model)
            )
            return cur.fetchone()

    @staticmethod
    def get_by_profile(profile_id: int) -> List[Dict[str, Any]]:
        """Get all research interests for a profile."""
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT * FROM profile_research_interests 
                WHERE profile_id = %s 
                ORDER BY created_at
                """,
                (profile_id,)
            )
            return cur.fetchall()

    @staticmethod
    def update_embedding(
        interest_id: int,
        embedding: List[float],
        embedding_model: str
    ) -> Optional[Dict[str, Any]]:
        """Update the embedding for a research interest."""
        emb_literal = to_pgvector(embedding)
        
        with get_cursor() as cur:
            cur.execute(
                """
                UPDATE profile_research_interests 
                SET embedding = %s, embedding_model = %s, updated_at = %s
                WHERE id = %s
                RETURNING *
                """,
                (emb_literal, embedding_model, datetime.now(), interest_id)
            )
            return cur.fetchone()

    @staticmethod
    def delete(interest_id: int) -> bool:
        """Delete a research interest."""
        with get_cursor() as cur:
            cur.execute(
                "DELETE FROM profile_research_interests WHERE id = %s",
                (interest_id,)
            )
            return cur.rowcount > 0

    @staticmethod
    def delete_by_profile(profile_id: int) -> int:
        """Delete all research interests for a profile. Returns count deleted."""
        with get_cursor() as cur:
            cur.execute(
                "DELETE FROM profile_research_interests WHERE profile_id = %s",
                (profile_id,)
            )
            return cur.rowcount

    @staticmethod
    def bulk_create(profile_id: int, interests: List[str]) -> List[Dict[str, Any]]:
        """Create multiple research interests for a profile."""
        if not interests:
            return []
        
        # Filter and prepare valid interests
        valid_interests = []
        for interest_text in interests:
            interest_text = interest_text.strip()
            if interest_text:
                valid_interests.append((profile_id, interest_text))
        
        if not valid_interests:
            return []
        
        results = []
        with get_cursor() as cur:
            # Use executemany for batch insert
            try:
                cur.executemany(
                    """
                    INSERT INTO profile_research_interests (profile_id, interest_text)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    valid_interests
                )
                
                # Fetch all the newly created interests
                interest_texts = [text for _, text in valid_interests]
                placeholders = ', '.join(['%s'] * len(interest_texts))
                cur.execute(
                    f"""
                    SELECT * FROM profile_research_interests 
                    WHERE profile_id = %s AND interest_text IN ({placeholders})
                    ORDER BY id
                    """,
                    [profile_id] + interest_texts
                )
                results = cur.fetchall()
                
            except Exception as e:
                # Fall back to individual inserts if batch fails
                for profile_id, interest_text in valid_interests:
                    try:
                        cur.execute(
                            """
                            INSERT INTO profile_research_interests (profile_id, interest_text)
                            VALUES (%s, %s)
                            RETURNING *
                            """,
                            (profile_id, interest_text)
                        )
                        results.append(cur.fetchone())
                    except Exception as e:
                        if "unique constraint" in str(e).lower():
                            continue
                        raise
        
        return results

    @staticmethod
    def clone_interests(source_profile_id: int, target_profile_id: int) -> List[Dict[str, Any]]:
        """Clone all interests from one profile to another."""
        source_interests = ProfileInterestsRepository.get_by_profile(source_profile_id)
        
        results = []
        for interest in source_interests:
            try:
                new_interest = ProfileInterestsRepository.create(
                    target_profile_id,
                    interest["interest_text"],
                    # Note: embeddings are stored as pgvector strings, we'll regenerate them
                    embedding=None,
                    embedding_model=interest.get("embedding_model")
                )
                results.append(new_interest)
            except Exception as e:
                # Skip duplicates
                if "unique constraint" in str(e).lower():
                    continue
                raise
        
        return results

    @staticmethod
    def get_interests_text_by_profile(profile_id: int) -> str:
        """
        Get all research interests for a profile concatenated as a single text string.
        
        Args:
            profile_id: ID of the profile
            
        Returns:
            Concatenated research interests text, newline-separated
        """
        with get_cursor() as cur:
            cur.execute("""
                SELECT interest_text 
                FROM profile_research_interests 
                WHERE profile_id = %s 
                ORDER BY id
            """, (profile_id,))
            
            rows = cur.fetchall()
            interests = [row['interest_text'] for row in rows]
            return '\n'.join(interests)


class ProfileScoreRepository:
    """CRUD operations for the `paper_profile_scores` table."""

    @staticmethod
    def create_or_update(
        paper_id: int,
        profile_id: int,
        score: Optional[float] = None,
        rationale: Optional[str] = None,
        related: Optional[bool] = None,
        similarity_score: Optional[float] = None
    ) -> Dict[str, Any]:
        """Create or update a paper score for a profile."""
        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO paper_profile_scores 
                (paper_id, profile_id, score, rationale, related, similarity_score)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (paper_id, profile_id) 
                DO UPDATE SET 
                    score = COALESCE(EXCLUDED.score, paper_profile_scores.score),
                    rationale = COALESCE(EXCLUDED.rationale, paper_profile_scores.rationale),
                    related = COALESCE(EXCLUDED.related, paper_profile_scores.related),
                    similarity_score = COALESCE(EXCLUDED.similarity_score, paper_profile_scores.similarity_score),
                    updated_at = %s
                RETURNING *
                """,
                (paper_id, profile_id, score, rationale, related, similarity_score, datetime.now())
            )
            return cur.fetchone()

    @staticmethod
    def get_by_paper_and_profile(paper_id: int, profile_id: int) -> Optional[Dict[str, Any]]:
        """Get score for a specific paper and profile."""
        with get_cursor() as cur:
            cur.execute(
                "SELECT * FROM paper_profile_scores WHERE paper_id = %s AND profile_id = %s",
                (paper_id, profile_id)
            )
            return cur.fetchone()

    @staticmethod
    def get_by_profile(
        profile_id: int,
        min_score: Optional[float] = None,
        related_only: bool = False,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get all scores for a profile with optional filtering."""
        conditions = ["profile_id = %s"]
        params = [profile_id]
        
        if min_score is not None:
            conditions.append("score >= %s")
            params.append(min_score)
        
        if related_only:
            conditions.append("related = TRUE")
        
        query = f"SELECT * FROM paper_profile_scores WHERE {' AND '.join(conditions)} ORDER BY score DESC"
        
        if limit is not None:
            query += " LIMIT %s"
            params.append(limit)
        
        if offset > 0:
            query += " OFFSET %s"
            params.append(offset)
        
        with get_cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()

    @staticmethod
    def get_papers_for_profile(
        profile_id: int,
        min_score: Optional[float] = None,
        related_only: bool = False,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get papers with their scores for a profile."""
        conditions = ["pps.profile_id = %s"]
        params = [profile_id]
        
        if min_score is not None:
            conditions.append("pps.score >= %s")
            params.append(min_score)
        
        if related_only:
            conditions.append("pps.related = TRUE")
        
        query = f"""
            SELECT p.*, pps.score, pps.rationale, pps.related, pps.similarity_score
            FROM papers p
            JOIN paper_profile_scores pps ON p.id = pps.paper_id
            WHERE {' AND '.join(conditions)}
            ORDER BY pps.score DESC
        """
        
        if limit is not None:
            query += " LIMIT %s"
            params.append(limit)
        
        if offset > 0:
            query += " OFFSET %s"
            params.append(offset)
        
        with get_cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()

    @staticmethod
    def bulk_insert(scores: List[Dict[str, Any]]) -> int:
        """Bulk insert paper scores. Returns count of inserted records."""
        if not scores:
            return 0
        
        with get_cursor() as cur:
            values = []
            for score_data in scores:
                values.append((
                    score_data["paper_id"],
                    score_data["profile_id"],
                    score_data.get("score"),
                    score_data.get("rationale"),
                    score_data.get("related", False),
                    score_data.get("similarity_score"),
                    datetime.now(),
                    datetime.now()
                ))
            
            cur.executemany(
                """
                INSERT INTO paper_profile_scores 
                (paper_id, profile_id, score, rationale, related, similarity_score, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (paper_id, profile_id) DO NOTHING
                """,
                values
            )
            return cur.rowcount

    @staticmethod
    def delete_by_profile(profile_id: int) -> int:
        """Delete all scores for a profile. Returns count deleted."""
        with get_cursor() as cur:
            cur.execute(
                "DELETE FROM paper_profile_scores WHERE profile_id = %s",
                (profile_id,)
            )
            return cur.rowcount

    @staticmethod
    def has_score_for_profile(paper_id: int, profile_id: int) -> bool:
        """
        Check if a paper has a score for a specific profile.
        
        Args:
            paper_id: ID of the paper
            profile_id: ID of the profile
            
        Returns:
            True if score exists, False otherwise
        """
        with get_cursor() as cur:
            cur.execute("""
                SELECT 1 FROM paper_profile_scores
                WHERE paper_id = %s AND profile_id = %s
                LIMIT 1
            """, (paper_id, profile_id))
            
            return cur.fetchone() is not None

    @staticmethod
    def has_scores_for_profiles(paper_id: int, profile_ids: List[int]) -> bool:
        """
        Check if a paper has scores for any of the specified profiles.
        
        Args:
            paper_id: ID of the paper
            profile_ids: List of profile IDs to check
            
        Returns:
            True if paper has scores for any of the profiles, False otherwise
        """
        if not profile_ids:
            return False
            
        with get_cursor() as cur:
            placeholders = ', '.join(['%s'] * len(profile_ids))
            cur.execute(f"""
                SELECT 1 FROM paper_profile_scores
                WHERE paper_id = %s AND profile_id IN ({placeholders})
                LIMIT 1
            """, [paper_id] + profile_ids)
            
            return cur.fetchone() is not None

    @staticmethod
    def create_or_update_score(
        paper_id: int,
        profile_id: int,
        score: int,
        related: bool,
        rationale: str,
        judge_model: str
    ) -> bool:
        """
        Create or update a paper score for a profile.
        
        Args:
            paper_id: ID of the paper
            profile_id: ID of the profile
            score: LLM judge score (1-10)
            related: Whether paper is related to profile interests
            rationale: LLM judge rationale
            judge_model: Name of the judge model used
            
        Returns:
            True if operation was successful
        """
        with get_cursor() as cur:
            cur.execute("""
                INSERT INTO paper_profile_scores 
                (paper_id, profile_id, score, related, rationale, judge_model, date_scored)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (paper_id, profile_id) 
                DO UPDATE SET 
                    score = EXCLUDED.score,
                    related = EXCLUDED.related,
                    rationale = EXCLUDED.rationale,
                    judge_model = EXCLUDED.judge_model,
                    date_scored = NOW()
            """, (paper_id, profile_id, score, related, rationale, judge_model))
            
            return cur.rowcount > 0

    @staticmethod
    def bulk_create_or_update_scores(
        scores_data: List[Dict[str, Any]]
    ) -> Tuple[int, int]:
        """
        Create or update multiple paper scores for profiles in a single batch.
        
        Args:
            scores_data: List of dictionaries containing:
                - paper_id: ID of the paper
                - profile_id: ID of the profile
                - score: LLM judge score (1-10)
                - related: Whether paper is related to profile interests
                - rationale: LLM judge rationale
                - judge_model: Name of the judge model used
                
        Returns:
            Tuple of (successful_count, failed_count)
        """
        if not scores_data:
            return 0, 0
            
        successful = 0
        failed = 0
        
        with get_cursor() as cur:
            # Prepare values for executemany
            values = []
            for score_item in scores_data:
                try:
                    values.append((
                        score_item['paper_id'],
                        score_item['profile_id'],
                        score_item['score'],
                        score_item['related'],
                        score_item['rationale'],
                        score_item['judge_model']
                    ))
                except KeyError as e:
                    failed += 1
                    continue
            
            if values:
                try:
                    cur.executemany("""
                        INSERT INTO paper_profile_scores 
                        (paper_id, profile_id, score, related, rationale, judge_model, date_scored)
                        VALUES (%s, %s, %s, %s, %s, %s, NOW())
                        ON CONFLICT (paper_id, profile_id) 
                        DO UPDATE SET 
                            score = EXCLUDED.score,
                            related = EXCLUDED.related,
                            rationale = EXCLUDED.rationale,
                            judge_model = EXCLUDED.judge_model,
                            date_scored = NOW()
                    """, values)
                    successful = cur.rowcount
                except Exception as e:
                    failed += len(values)
                    raise
                    
        return successful, failed

    @staticmethod
    def get_profile_paper_stats(profile_id: int) -> Dict[str, Any]:
        """
        Get statistics about papers for a specific profile.
        
        Args:
            profile_id: ID of the profile
            
        Returns:
            Dictionary with paper statistics for the profile
        """
        with get_cursor() as cur:
            # Get basic counts and score stats
            cur.execute("""
                SELECT 
                    COUNT(*) as total_papers,
                    COUNT(CASE WHEN related = TRUE THEN 1 END) as related_papers,
                    AVG(score) as avg_score,
                    MIN(score) as min_score,
                    MAX(score) as max_score,
                    STDDEV(score) as score_stddev
                FROM paper_profile_scores
                WHERE profile_id = %s
            """, (profile_id,))
            
            basic_stats = cur.fetchone()
            
            # Get score distribution (buckets)
            cur.execute("""
                SELECT 
                    CASE 
                        WHEN score >= 9 THEN '9-10'
                        WHEN score >= 7 THEN '7-8'
                        WHEN score >= 5 THEN '5-6'
                        WHEN score >= 3 THEN '3-4'
                        ELSE '1-2'
                    END as score_range,
                    COUNT(*) as count
                FROM paper_profile_scores
                WHERE profile_id = %s
                GROUP BY score_range
                ORDER BY score_range DESC
            """, (profile_id,))
            
            score_distribution = cur.fetchall()
            
            # Get papers by month (last 12 months)
            cur.execute("""
                SELECT 
                    DATE_TRUNC('month', p.date) as month,
                    COUNT(*) as paper_count,
                    AVG(pps.score) as avg_score
                FROM paper_profile_scores pps
                JOIN papers p ON pps.paper_id = p.id
                WHERE pps.profile_id = %s 
                  AND p.date >= CURRENT_DATE - INTERVAL '12 months'
                GROUP BY DATE_TRUNC('month', p.date)
                ORDER BY month DESC
            """, (profile_id,))
            
            monthly_stats = cur.fetchall()
            
            # Get recent high-scoring papers
            cur.execute("""
                SELECT p.id, p.title, pps.score, pps.related, p.date
                FROM paper_profile_scores pps
                JOIN papers p ON pps.paper_id = p.id
                WHERE pps.profile_id = %s AND pps.score >= 8
                ORDER BY pps.score DESC, p.date DESC
                LIMIT 10
            """, (profile_id,))
            
            top_papers = cur.fetchall()
            
            return {
                "basic_stats": {
                    "total_papers": basic_stats['total_papers'] or 0,
                    "related_papers": basic_stats['related_papers'] or 0,
                    "unrelated_papers": (basic_stats['total_papers'] or 0) - (basic_stats['related_papers'] or 0),
                    "avg_score": float(basic_stats['avg_score']) if basic_stats['avg_score'] else 0.0,
                    "min_score": float(basic_stats['min_score']) if basic_stats['min_score'] else 0.0,
                    "max_score": float(basic_stats['max_score']) if basic_stats['max_score'] else 0.0,
                    "score_stddev": float(basic_stats['score_stddev']) if basic_stats['score_stddev'] else 0.0
                },
                "score_distribution": [
                    {
                        "range": row['score_range'],
                        "count": row['count']
                    }
                    for row in score_distribution
                ],
                "monthly_stats": [
                    {
                        "month": row['month'].strftime('%Y-%m') if row['month'] else None,
                        "paper_count": row['paper_count'],
                        "avg_score": float(row['avg_score']) if row['avg_score'] else 0.0
                    }
                    for row in monthly_stats
                ],
                "top_papers": [
                    {
                        "id": row['id'],
                        "title": row['title'],
                        "score": float(row['score']) if row['score'] else 0.0,
                        "related": row['related'],
                        "date": row['date'].strftime('%Y-%m-%d') if row['date'] else None
                    }
                    for row in top_papers
                ]
            } 