"""Data access layer for trends and topics."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, date, timedelta
import json

from ..db import get_cursor
from .base import to_pgvector


class TopicsRepository:
    """CRUD operations for the topics table."""

    @staticmethod
    def insert(label: str, keywords: List[str], profile_id: int, centroid_embedding: List[float] | None = None, 
               embedding_model: str | None = None) -> int:
        """Insert a new topic and return its ID."""
        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO topics (label, keywords, profile_id, centroid_embedding, embedding_model)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (label, keywords, profile_id, to_pgvector(centroid_embedding), embedding_model)
            )
            row = cur.fetchone()
            return row["id"] if row else 0

    @staticmethod
    def get(topic_id: int) -> Dict[str, Any] | None:
        """Get a topic by ID."""
        with get_cursor() as cur:
            cur.execute("SELECT * FROM topics WHERE id = %s", (topic_id,))
            return cur.fetchone()

    @staticmethod
    def get_all(limit: int = 100, profile_id: Optional[int] = None, profile_ids: Optional[List[int]] = None) -> List[Dict[str, Any]]:
        """Get all topics ordered by creation date, optionally filtered by profile(s)."""
        with get_cursor() as cur:
            if profile_ids:
                placeholders = ','.join(['%s'] * len(profile_ids))
                cur.execute(
                    f"SELECT * FROM topics WHERE profile_id IN ({placeholders}) ORDER BY created_at DESC LIMIT %s",
                    (*profile_ids, limit)
                )
            elif profile_id:
                cur.execute(
                    "SELECT * FROM topics WHERE profile_id = %s ORDER BY created_at DESC LIMIT %s",
                    (profile_id, limit)
                )
            else:
                cur.execute(
                    "SELECT * FROM topics ORDER BY created_at DESC LIMIT %s",
                    (limit,)
                )
            return cur.fetchall()

    @staticmethod
    def update(topic_id: int, updates: Dict[str, Any]) -> None:
        """Update a topic with the given changes."""
        if not updates:
            return
        
        fields: List[str] = []
        params: List[Any] = []
        
        for key, value in updates.items():
            if key == "centroid_embedding":
                value = to_pgvector(value)
            fields.append(f"{key} = %s")
            params.append(value)
        
        fields.append("updated_at = now()")
        params.append(topic_id)
        
        sql = f"UPDATE topics SET {', '.join(fields)} WHERE id = %s"
        with get_cursor() as cur:
            cur.execute(sql, params)

    @staticmethod
    def delete(topic_id: int) -> None:
        """Delete a topic by ID."""
        with get_cursor() as cur:
            cur.execute("DELETE FROM topics WHERE id = %s", (topic_id,))

    @staticmethod
    def search_by_keywords(keywords: List[str], limit: int = 10, profile_id: Optional[int] = None, profile_ids: Optional[List[int]] = None) -> List[Dict[str, Any]]:
        """Search topics by keywords overlap, optionally filtered by profile(s)."""
        with get_cursor() as cur:
            if profile_ids:
                placeholders = ','.join(['%s'] * len(profile_ids))
                cur.execute(
                    f"""
                    SELECT *, array_length(keywords && %s, 1) as keyword_matches
                    FROM topics 
                    WHERE keywords && %s AND profile_id IN ({placeholders})
                    ORDER BY keyword_matches DESC, created_at DESC
                    LIMIT %s
                    """,
                    (keywords, keywords, *profile_ids, limit)
                )
            elif profile_id:
                cur.execute(
                    """
                    SELECT *, array_length(keywords && %s, 1) as keyword_matches
                    FROM topics 
                    WHERE keywords && %s AND profile_id = %s
                    ORDER BY keyword_matches DESC, created_at DESC
                    LIMIT %s
                    """,
                    (keywords, keywords, profile_id, limit)
                )
            else:
                cur.execute(
                    """
                    SELECT *, array_length(keywords && %s, 1) as keyword_matches
                    FROM topics 
                    WHERE keywords && %s
                    ORDER BY keyword_matches DESC, created_at DESC
                    LIMIT %s
                    """,
                    (keywords, keywords, limit)
                )
            return cur.fetchall()


class TopicMetricsRepository:
    """CRUD operations for the topic_metrics table."""

    @staticmethod
    def insert(topic_id: int, period_start: date, period_end: date, period_type: str,
               doc_count: int, avg_score: float | None = None, growth_rate: float | None = None,
               forecast_1m: int | None = None, forecast_3m: int | None = None, 
               forecast_6m: int | None = None) -> int:
        """Insert new topic metrics."""
        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO topic_metrics 
                (topic_id, period_start, period_end, period_type, doc_count, avg_score, 
                 growth_rate, forecast_1m, forecast_3m, forecast_6m)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (topic_id, period_start, period_end, period_type) 
                DO UPDATE SET
                    doc_count = EXCLUDED.doc_count,
                    avg_score = EXCLUDED.avg_score,
                    growth_rate = EXCLUDED.growth_rate,
                    forecast_1m = EXCLUDED.forecast_1m,
                    forecast_3m = EXCLUDED.forecast_3m,
                    forecast_6m = EXCLUDED.forecast_6m,
                    created_at = now()
                RETURNING id
                """,
                (topic_id, period_start, period_end, period_type, doc_count, avg_score,
                 growth_rate, forecast_1m, forecast_3m, forecast_6m)
            )
            row = cur.fetchone()
            return row["id"] if row else 0

    @staticmethod
    def get_topic_timeline(topic_id: int, period_type: str = "month", 
                          limit: int = 24) -> List[Dict[str, Any]]:
        """Get historical metrics for a topic."""
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT * FROM topic_metrics 
                WHERE topic_id = %s AND period_type = %s
                ORDER BY period_start DESC
                LIMIT %s
                """,
                (topic_id, period_type, limit)
            )
            return cur.fetchall()

    @staticmethod
    def get_trending_topics(period_type: str = "month", limit: int = 10,
                           min_doc_count: int = 5, profile_id: Optional[int] = None, profile_ids: Optional[List[int]] = None) -> List[Dict[str, Any]]:
        """Get topics with highest growth rates in the latest period, optionally filtered by profile(s)."""
        with get_cursor() as cur:
            if profile_ids:
                placeholders = ','.join(['%s'] * len(profile_ids))
                cur.execute(
                    f"""
                    WITH latest_metrics AS (
                        SELECT DISTINCT ON (topic_id) 
                            tm.*, t.label, t.keywords, t.profile_id
                        FROM topic_metrics tm
                        JOIN topics t ON tm.topic_id = t.id
                        WHERE tm.period_type = %s AND tm.doc_count >= %s AND t.profile_id IN ({placeholders})
                        ORDER BY topic_id, period_start DESC
                    )
                    SELECT * FROM latest_metrics
                    ORDER BY growth_rate DESC NULLS LAST, doc_count DESC
                    LIMIT %s
                    """,
                    (period_type, min_doc_count, *profile_ids, limit)
                )
            elif profile_id:
                cur.execute(
                    """
                    WITH latest_metrics AS (
                        SELECT DISTINCT ON (topic_id) 
                            tm.*, t.label, t.keywords, t.profile_id
                        FROM topic_metrics tm
                        JOIN topics t ON tm.topic_id = t.id
                        WHERE tm.period_type = %s AND tm.doc_count >= %s AND t.profile_id = %s
                        ORDER BY topic_id, period_start DESC
                    )
                    SELECT * FROM latest_metrics
                    ORDER BY growth_rate DESC NULLS LAST, doc_count DESC
                    LIMIT %s
                    """,
                    (period_type, min_doc_count, profile_id, limit)
                )
            else:
                cur.execute(
                    """
                    WITH latest_metrics AS (
                        SELECT DISTINCT ON (topic_id) 
                            tm.*, t.label, t.keywords, t.profile_id
                        FROM topic_metrics tm
                        JOIN topics t ON tm.topic_id = t.id
                        WHERE tm.period_type = %s AND tm.doc_count >= %s
                        ORDER BY topic_id, period_start DESC
                    )
                    SELECT * FROM latest_metrics
                    ORDER BY growth_rate DESC NULLS LAST, doc_count DESC
                    LIMIT %s
                    """,
                    (period_type, min_doc_count, limit)
                )
            return cur.fetchall()

    @staticmethod
    def get_emerging_topics(period_type: str = "month", limit: int = 10,
                           min_growth_rate: float = 0.5, profile_id: Optional[int] = None, profile_ids: Optional[List[int]] = None) -> List[Dict[str, Any]]:
        """Get topics with high growth rates and forecasts, optionally filtered by profile(s)."""
        with get_cursor() as cur:
            if profile_ids:
                placeholders = ','.join(['%s'] * len(profile_ids))
                cur.execute(
                    f"""
                    WITH latest_metrics AS (
                        SELECT DISTINCT ON (topic_id) 
                            tm.*, t.label, t.keywords, t.profile_id
                        FROM topic_metrics tm
                        JOIN topics t ON tm.topic_id = t.id
                        WHERE tm.period_type = %s 
                        AND tm.growth_rate >= %s
                        AND tm.forecast_3m IS NOT NULL
                        AND t.profile_id IN ({placeholders})
                        ORDER BY topic_id, period_start DESC
                    )
                    SELECT * FROM latest_metrics
                    ORDER BY (growth_rate * forecast_3m) DESC, doc_count DESC
                    LIMIT %s
                    """,
                    (period_type, min_growth_rate, *profile_ids, limit)
                )
            elif profile_id:
                cur.execute(
                    """
                    WITH latest_metrics AS (
                        SELECT DISTINCT ON (topic_id) 
                            tm.*, t.label, t.keywords, t.profile_id
                        FROM topic_metrics tm
                        JOIN topics t ON tm.topic_id = t.id
                        WHERE tm.period_type = %s 
                        AND tm.growth_rate >= %s
                        AND tm.forecast_3m IS NOT NULL
                        AND t.profile_id = %s
                        ORDER BY topic_id, period_start DESC
                    )
                    SELECT * FROM latest_metrics
                    ORDER BY (growth_rate * forecast_3m) DESC, doc_count DESC
                    LIMIT %s
                    """,
                    (period_type, min_growth_rate, profile_id, limit)
                )
            else:
                cur.execute(
                    """
                    WITH latest_metrics AS (
                        SELECT DISTINCT ON (topic_id) 
                            tm.*, t.label, t.keywords, t.profile_id
                        FROM topic_metrics tm
                        JOIN topics t ON tm.topic_id = t.id
                        WHERE tm.period_type = %s 
                        AND tm.growth_rate >= %s
                        AND tm.forecast_3m IS NOT NULL
                        ORDER BY topic_id, period_start DESC
                    )
                    SELECT * FROM latest_metrics
                    ORDER BY (growth_rate * forecast_3m) DESC, doc_count DESC
                    LIMIT %s
                    """,
                    (period_type, min_growth_rate, limit)
                )
            return cur.fetchall()

    @staticmethod
    def update_forecasts(topic_id: int, period_start: date, period_end: date, 
                        period_type: str, forecast_1m: int | None = None,
                        forecast_3m: int | None = None, forecast_6m: int | None = None) -> None:
        """Update forecast values for a specific metric record."""
        with get_cursor() as cur:
            cur.execute(
                """
                UPDATE topic_metrics 
                SET forecast_1m = %s, forecast_3m = %s, forecast_6m = %s
                WHERE topic_id = %s AND period_start = %s AND period_end = %s AND period_type = %s
                """,
                (forecast_1m, forecast_3m, forecast_6m, topic_id, period_start, period_end, period_type)
            )

    @staticmethod
    def delete_for_period_type(period_type: str) -> int:
        """Delete all metrics for a specific period type."""
        with get_cursor() as cur:
            cur.execute(
                "DELETE FROM topic_metrics WHERE period_type = %s",
                (period_type,)
            )
            return cur.rowcount

    @staticmethod
    def delete_recent_periods(period_type: str, cutoff_date: date) -> int:
        """Delete metrics for recent periods that need recalculation."""
        with get_cursor() as cur:
            cur.execute(
                "DELETE FROM topic_metrics WHERE period_type = %s AND period_start >= %s",
                (period_type, cutoff_date)
            )
            return cur.rowcount

    @staticmethod
    def get_latest_period_end(period_type: str) -> date | None:
        """Get the end date of the most recent period for incremental processing."""
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT MAX(period_end) as latest_end 
                FROM topic_metrics 
                WHERE period_type = %s
                """,
                (period_type,)
            )
            row = cur.fetchone()
            return row["latest_end"] if row and row["latest_end"] else None

    @staticmethod
    def periods_exist_for_topic(topic_id: int, period_type: str) -> bool:
        """Check if any metrics exist for a topic and period type."""
        with get_cursor() as cur:
            cur.execute(
                "SELECT 1 FROM topic_metrics WHERE topic_id = %s AND period_type = %s LIMIT 1",
                (topic_id, period_type)
            )
            return cur.fetchone() is not None


class PaperTopicsRepository:
    """CRUD operations for the paper_topics junction table."""

    @staticmethod
    def insert(paper_id: int, topic_id: int, relevance_score: float = 0.0) -> int:
        """Link a paper to a topic with relevance score."""
        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO paper_topics (paper_id, topic_id, relevance_score)
                VALUES (%s, %s, %s)
                ON CONFLICT (paper_id, topic_id) 
                DO UPDATE SET relevance_score = EXCLUDED.relevance_score, created_at = now()
                RETURNING id
                """,
                (paper_id, topic_id, relevance_score)
            )
            row = cur.fetchone()
            return row["id"] if row else 0

    @staticmethod
    def get_papers_for_topic(topic_id: int, limit: int = 50, 
                            min_relevance: float = 0.1) -> List[Dict[str, Any]]:
        """Get papers associated with a topic, ordered by relevance."""
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT p.*, pt.relevance_score
                FROM papers p
                JOIN paper_topics pt ON p.id = pt.paper_id
                WHERE pt.topic_id = %s AND pt.relevance_score >= %s
                ORDER BY pt.relevance_score DESC, p.score DESC
                LIMIT %s
                """,
                (topic_id, min_relevance, limit)
            )
            return cur.fetchall()

    @staticmethod
    def get_topics_for_paper(paper_id: int) -> List[Dict[str, Any]]:
        """Get topics associated with a paper."""
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT t.*, pt.relevance_score
                FROM topics t
                JOIN paper_topics pt ON t.id = pt.topic_id
                WHERE pt.paper_id = %s
                ORDER BY pt.relevance_score DESC
                """,
                (paper_id,)
            )
            return cur.fetchall()

    @staticmethod
    def bulk_insert(paper_topic_pairs: List[Tuple[int, int, float]]) -> None:
        """Bulk insert paper-topic relationships."""
        if not paper_topic_pairs:
            return
        
        with get_cursor() as cur:
            cur.executemany(
                """
                INSERT INTO paper_topics (paper_id, topic_id, relevance_score)
                VALUES (%s, %s, %s)
                ON CONFLICT (paper_id, topic_id) 
                DO UPDATE SET relevance_score = EXCLUDED.relevance_score, created_at = now()
                """,
                paper_topic_pairs
            )

    @staticmethod
    def delete_for_topic(topic_id: int) -> None:
        """Remove all paper associations for a topic."""
        with get_cursor() as cur:
            cur.execute("DELETE FROM paper_topics WHERE topic_id = %s", (topic_id,))

    @staticmethod
    def delete_for_paper(paper_id: int) -> None:
        """Remove all topic associations for a paper."""
        with get_cursor() as cur:
            cur.execute("DELETE FROM paper_topics WHERE paper_id = %s", (paper_id,))

    @staticmethod
    def get_papers_needing_topic_assignment(cutoff_date: date | None = None) -> List[Dict[str, Any]]:
        """Get papers that don't have topic assignments yet."""
        with get_cursor() as cur:
            if cutoff_date:
                cur.execute(
                    """
                    SELECT p.* FROM papers p
                    LEFT JOIN paper_topics pt ON p.id = pt.paper_id
                    WHERE pt.paper_id IS NULL 
                    AND p.embedding IS NOT NULL
                    AND p.date >= %s
                    ORDER BY p.date DESC
                    """,
                    (cutoff_date,)
                )
            else:
                cur.execute(
                    """
                    SELECT p.* FROM papers p
                    LEFT JOIN paper_topics pt ON p.id = pt.paper_id
                    WHERE pt.paper_id IS NULL 
                    AND p.embedding IS NOT NULL
                    ORDER BY p.date DESC
                    """
                )
            return cur.fetchall()

    @staticmethod
    def get_papers_with_topics_since(cutoff_date: date) -> List[Dict[str, Any]]:
        """Get papers that have topic assignments and were published since cutoff date."""
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT p.* FROM papers p
                JOIN paper_topics pt ON p.id = pt.paper_id
                WHERE p.date >= %s AND p.embedding IS NOT NULL
                ORDER BY p.date DESC
                """,
                (cutoff_date,)
            )
            return cur.fetchall()

    @staticmethod 
    def count_papers_by_topic_since(cutoff_date: date) -> Dict[int, int]:
        """Count how many papers each topic has since a given date."""
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT pt.topic_id, COUNT(*) as paper_count
                FROM paper_topics pt
                JOIN papers p ON pt.paper_id = p.id
                WHERE p.date >= %s
                GROUP BY pt.topic_id
                """,
                (cutoff_date,)
            )
            return {row['topic_id']: row['paper_count'] for row in cur.fetchall()}


class TrendsRepository:
    """High-level operations combining topics and metrics."""

    @staticmethod
    def get_dashboard_data(limit: int = 20, period_type: str = "month", duration_months: int = 6, 
                          profile_id: Optional[int] = None, profile_ids: Optional[List[int]] = None) -> Dict[str, Any]:
        """Get comprehensive dashboard data for trends page with duration filtering, optionally filtered by profile(s)."""
        with get_cursor() as cur:
            # Build SQL query with proper parameter handling
            if profile_ids:
                placeholders = ','.join(['%s'] * len(profile_ids))
                query = f"""
                WITH latest_metrics AS (
                    SELECT DISTINCT ON (tm.topic_id) 
                        tm.id, tm.topic_id, tm.period_start, tm.period_end, tm.period_type,
                        tm.doc_count, tm.avg_score, tm.growth_rate, tm.forecast_1m, tm.forecast_3m, tm.forecast_6m,
                        tm.created_at, t.label, t.keywords, t.profile_id
                    FROM topic_metrics tm
                    JOIN topics t ON tm.topic_id = t.id
                    WHERE tm.period_type = %s AND t.profile_id IN ({placeholders})
                    ORDER BY tm.topic_id, tm.period_start DESC
                ),
                topic_paper_counts AS (
                    SELECT pt.topic_id, COUNT(*) as total_papers
                    FROM paper_topics pt
                    JOIN topics t ON pt.topic_id = t.id
                    WHERE t.profile_id IN ({placeholders})
                    GROUP BY pt.topic_id
                )
                SELECT 
                    lm.id,
                    lm.topic_id,
                    lm.period_start,
                    lm.period_end,
                    lm.period_type,
                    lm.doc_count,
                    lm.avg_score,
                    lm.growth_rate,
                    lm.forecast_1m,
                    lm.forecast_3m,
                    lm.forecast_6m,
                    lm.created_at,
                    lm.label,
                    lm.keywords,
                    lm.profile_id,
                    COALESCE(tpc.total_papers, 0) as total_papers,
                    lm.doc_count as latest_doc_count,
                    lm.growth_rate as latest_growth_rate
                FROM latest_metrics lm
                LEFT JOIN topic_paper_counts tpc ON lm.topic_id = tpc.topic_id
                WHERE lm.doc_count > 0
                ORDER BY lm.doc_count DESC, lm.growth_rate DESC NULLS LAST
                LIMIT %s
                """
                params = [period_type] + profile_ids + profile_ids + [limit]
            elif profile_id:
                query = """
                WITH latest_metrics AS (
                    SELECT DISTINCT ON (tm.topic_id) 
                        tm.id, tm.topic_id, tm.period_start, tm.period_end, tm.period_type,
                        tm.doc_count, tm.avg_score, tm.growth_rate, tm.forecast_1m, tm.forecast_3m, tm.forecast_6m,
                        tm.created_at, t.label, t.keywords, t.profile_id
                    FROM topic_metrics tm
                    JOIN topics t ON tm.topic_id = t.id
                    WHERE tm.period_type = %s AND t.profile_id = %s
                    ORDER BY tm.topic_id, tm.period_start DESC
                ),
                topic_paper_counts AS (
                    SELECT pt.topic_id, COUNT(*) as total_papers
                    FROM paper_topics pt
                    JOIN topics t ON pt.topic_id = t.id
                    WHERE t.profile_id = %s
                    GROUP BY pt.topic_id
                )
                SELECT 
                    lm.id,
                    lm.topic_id,
                    lm.period_start,
                    lm.period_end,
                    lm.period_type,
                    lm.doc_count,
                    lm.avg_score,
                    lm.growth_rate,
                    lm.forecast_1m,
                    lm.forecast_3m,
                    lm.forecast_6m,
                    lm.created_at,
                    lm.label,
                    lm.keywords,
                    lm.profile_id,
                    COALESCE(tpc.total_papers, 0) as total_papers,
                    lm.doc_count as latest_doc_count,
                    lm.growth_rate as latest_growth_rate
                FROM latest_metrics lm
                LEFT JOIN topic_paper_counts tpc ON lm.topic_id = tpc.topic_id
                WHERE lm.doc_count > 0
                ORDER BY lm.doc_count DESC, lm.growth_rate DESC NULLS LAST
                LIMIT %s
                """
                params = [period_type, profile_id, profile_id, limit]
            else:
                query = """
                WITH latest_metrics AS (
                    SELECT DISTINCT ON (tm.topic_id) 
                        tm.id, tm.topic_id, tm.period_start, tm.period_end, tm.period_type,
                        tm.doc_count, tm.avg_score, tm.growth_rate, tm.forecast_1m, tm.forecast_3m, tm.forecast_6m,
                        tm.created_at, t.label, t.keywords, t.profile_id
                    FROM topic_metrics tm
                    JOIN topics t ON tm.topic_id = t.id
                    WHERE tm.period_type = %s
                    ORDER BY tm.topic_id, tm.period_start DESC
                ),
                topic_paper_counts AS (
                    SELECT pt.topic_id, COUNT(*) as total_papers
                    FROM paper_topics pt
                    GROUP BY pt.topic_id
                )
                SELECT 
                    lm.id,
                    lm.topic_id,
                    lm.period_start,
                    lm.period_end,
                    lm.period_type,
                    lm.doc_count,
                    lm.avg_score,
                    lm.growth_rate,
                    lm.forecast_1m,
                    lm.forecast_3m,
                    lm.forecast_6m,
                    lm.created_at,
                    lm.label,
                    lm.keywords,
                    lm.profile_id,
                    COALESCE(tpc.total_papers, 0) as total_papers,
                    lm.doc_count as latest_doc_count,
                    lm.growth_rate as latest_growth_rate
                FROM latest_metrics lm
                LEFT JOIN topic_paper_counts tpc ON lm.topic_id = tpc.topic_id
                WHERE lm.doc_count > 0
                ORDER BY lm.doc_count DESC, lm.growth_rate DESC NULLS LAST
                LIMIT %s
                """
                params = [period_type, limit]
            
            cur.execute(query, params)
            trending_topics = cur.fetchall()

            # Get overall statistics with profile filtering
            if profile_ids:
                placeholders = ','.join(['%s'] * len(profile_ids))
                cur.execute(f"SELECT COUNT(*) as total_topics FROM topics WHERE profile_id IN ({placeholders})", profile_ids)
            elif profile_id:
                cur.execute("SELECT COUNT(*) as total_topics FROM topics WHERE profile_id = %s", (profile_id,))
            else:
                cur.execute("SELECT COUNT(*) as total_topics FROM topics")
            total_topics = cur.fetchone()["total_topics"]

            # Count papers with topics, filtered by profile
            if profile_ids:
                placeholders = ','.join(['%s'] * len(profile_ids))
                cur.execute(
                    f"""
                    SELECT COUNT(*) as total_papers_with_topics 
                    FROM (SELECT DISTINCT pt.paper_id 
                          FROM paper_topics pt 
                          JOIN topics t ON pt.topic_id = t.id 
                          WHERE t.profile_id IN ({placeholders})) pt
                    """,
                    profile_ids
                )
            elif profile_id:
                cur.execute(
                    """
                    SELECT COUNT(*) as total_papers_with_topics 
                    FROM (SELECT DISTINCT pt.paper_id 
                          FROM paper_topics pt 
                          JOIN topics t ON pt.topic_id = t.id 
                          WHERE t.profile_id = %s) pt
                    """,
                    (profile_id,)
                )
            else:
                cur.execute(
                    """
                    SELECT COUNT(*) as total_papers_with_topics 
                    FROM (SELECT DISTINCT paper_id FROM paper_topics) pt
                    """
                )
            total_papers_with_topics = cur.fetchone()["total_papers_with_topics"]

            return {
                "trending_topics": trending_topics,
                "total_topics": total_topics,
                "total_papers_with_topics": total_papers_with_topics,
                "period_type": period_type,
                "duration_months": duration_months,
                "profile_id": profile_id,
                "profile_ids": profile_ids
            }

    @staticmethod
    def cleanup_old_metrics(months_to_keep: int = 24) -> int:
        """
        Clean up old topic metrics to keep database size manageable.
        Keeps only the most recent metrics for each topic within the specified timeframe.
        
        Args:
            months_to_keep: Number of months of data to retain
            
        Returns:
            Number of records deleted
        """
        with get_cursor() as cur:
            # Calculate cutoff date
            cutoff_query = """
            SELECT NOW() - INTERVAL '%s months' as cutoff_date
            """
            cur.execute(cutoff_query, (months_to_keep,))
            cutoff_date = cur.fetchone()['cutoff_date']
            
            # Delete old metrics
            delete_query = """
            DELETE FROM topic_metrics 
            WHERE period_start < %s
            """
            cur.execute(delete_query, (cutoff_date,))
            return cur.rowcount

    @staticmethod
    def nuclear_cleanup_all_data() -> Dict[str, int]:
        """
        NUCLEAR OPTION: Delete ALL trends-related data for complete recalculation.
        This is intended for development/testing when you want a completely fresh start.
        
        Returns:
            Dictionary with counts of deleted records by table
        """
        deleted_counts = {}
        
        with get_cursor() as cur:
            # Delete all paper-topic relationships
            cur.execute("DELETE FROM paper_topics")
            deleted_counts['paper_topics'] = cur.rowcount
            
            # Delete all topic metrics
            cur.execute("DELETE FROM topic_metrics")
            deleted_counts['topic_metrics'] = cur.rowcount
            
            # Delete all topics
            cur.execute("DELETE FROM topics")
            deleted_counts['topics'] = cur.rowcount
            
        return deleted_counts

    @staticmethod
    def search_topics(query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search topics by label or keywords."""
        with get_cursor() as cur:
            cur.execute(
                """
                WITH topic_paper_counts AS (
                    SELECT topic_id, COUNT(*) as total_papers
                    FROM paper_topics
                    GROUP BY topic_id
                )
                SELECT t.*, 
                       COALESCE(latest_metrics.doc_count, 0) as latest_doc_count,
                       COALESCE(latest_metrics.growth_rate, 0) as latest_growth_rate,
                       COALESCE(tpc.total_papers, 0) as total_papers
                FROM topics t
                LEFT JOIN LATERAL (
                    SELECT doc_count, growth_rate
                    FROM topic_metrics tm
                    WHERE tm.topic_id = t.id
                    ORDER BY period_start DESC
                    LIMIT 1
                ) latest_metrics ON true
                LEFT JOIN topic_paper_counts tpc ON t.id = tpc.topic_id
                WHERE t.label ILIKE %s 
                   OR array_to_string(t.keywords, ' ') ILIKE %s
                ORDER BY latest_doc_count DESC, t.created_at DESC
                LIMIT %s
                """,
                (f"%{query}%", f"%{query}%", limit)
            )
            return cur.fetchall()


# === Research Interest Clustering Repositories ===
# Separate from automatic topic discovery, these handle research interest based analysis

class ResearchInterestsRepository:
    """Repository for research interests management."""
    
    @staticmethod
    def insert(interest_text: str, embedding: Optional[List[float]] = None, 
               embedding_model: Optional[str] = None) -> int:
        """Insert a new research interest."""
        with get_cursor() as cur:
            cur.execute("""
                INSERT INTO research_interests (interest_text, embedding, embedding_model)
                VALUES (%s, %s, %s)
                RETURNING id
            """, (interest_text, embedding, embedding_model))
            result = cur.fetchone()
            return result['id'] if result else None
    
    @staticmethod
    def get_all() -> List[Dict[str, Any]]:
        """Get all research interests."""
        with get_cursor() as cur:
            cur.execute("""
                SELECT id, interest_text, embedding, embedding_model, created_at, updated_at
                FROM research_interests
                ORDER BY id
            """)
            
            return cur.fetchall()
    
    @staticmethod
    def get(research_interest_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific research interest by ID."""
        with get_cursor() as cur:
            cur.execute("""
                SELECT id, interest_text, embedding, embedding_model, created_at, updated_at
                FROM research_interests
                WHERE id = %s
            """, (research_interest_id,))
            
            return cur.fetchone()
    
    @staticmethod
    def delete_all() -> int:
        """Delete all research interests."""
        with get_cursor() as cur:
            cur.execute("DELETE FROM research_interests")
            return cur.rowcount
    
    @staticmethod
    def update_embedding(research_interest_id: int, embedding: List[float], 
                        embedding_model: str):
        """Update the embedding for a research interest."""
        with get_cursor() as cur:
            cur.execute("""
                UPDATE research_interests 
                SET embedding = %s, embedding_model = %s, updated_at = now()
                WHERE id = %s
            """, (embedding, embedding_model, research_interest_id))


class ResearchInterestMetricsRepository:
    """Repository for research interest temporal metrics."""
    
    @staticmethod
    def insert(research_interest_id: int, period_start: date, period_end: date,
               period_type: str, doc_count: int, avg_relevance_score: Optional[float] = None,
               avg_paper_score: Optional[float] = None, growth_rate: Optional[float] = None,
               forecast_1m: Optional[int] = None, forecast_3m: Optional[int] = None,
               forecast_6m: Optional[int] = None) -> int:
        """Insert temporal metrics for a research interest."""
        with get_cursor() as cur:
            cur.execute("""
                INSERT INTO research_interest_metrics 
                (research_interest_id, period_start, period_end, period_type, doc_count,
                 avg_relevance_score, avg_paper_score, growth_rate, forecast_1m, forecast_3m, forecast_6m)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (research_interest_id, period_start, period_end, period_type)
                DO UPDATE SET 
                    doc_count = EXCLUDED.doc_count,
                    avg_relevance_score = EXCLUDED.avg_relevance_score,
                    avg_paper_score = EXCLUDED.avg_paper_score,
                    growth_rate = EXCLUDED.growth_rate,
                    forecast_1m = EXCLUDED.forecast_1m,
                    forecast_3m = EXCLUDED.forecast_3m,
                    forecast_6m = EXCLUDED.forecast_6m,
                    created_at = now()
                RETURNING id
            """, (research_interest_id, period_start, period_end, period_type, doc_count,
                  avg_relevance_score, avg_paper_score, growth_rate, 
                  forecast_1m, forecast_3m, forecast_6m))
            result = cur.fetchone()
            return result['id'] if result else None
    
    @staticmethod
    def get_interest_timeline(research_interest_id: int, period_type: str, 
                             limit: int = 24) -> List[Dict[str, Any]]:
        """Get timeline metrics for a specific research interest."""
        with get_cursor() as cur:
            cur.execute("""
                SELECT id, research_interest_id, period_start, period_end, period_type,
                       doc_count, avg_relevance_score, avg_paper_score, growth_rate,
                       forecast_1m, forecast_3m, forecast_6m, created_at
                FROM research_interest_metrics
                WHERE research_interest_id = %s AND period_type = %s
                ORDER BY period_start DESC
                LIMIT %s
            """, (research_interest_id, period_type, limit))
            
            return cur.fetchall()
    
    @staticmethod
    def delete_for_period_type(period_type: str) -> int:
        """Delete all metrics for a specific period type."""
        with get_cursor() as cur:
            cur.execute("""
                DELETE FROM research_interest_metrics 
                WHERE period_type = %s
            """, (period_type,))
            return cur.rowcount
    
    @staticmethod
    def get_latest_period_end(period_type: str) -> Optional[date]:
        """Get the latest period end date for incremental processing."""
        with get_cursor() as cur:
            cur.execute("""
                SELECT MAX(period_end) 
                FROM research_interest_metrics 
                WHERE period_type = %s
            """, (period_type,))
            
            result = cur.fetchone()
            return result[0] if result and result[0] else None


class PaperResearchInterestsRepository:
    """Repository for paper-research_interest relationships."""
    
    @staticmethod
    def insert(paper_id: int, research_interest_id: int, similarity_score: float) -> int:
        """Insert a paper-research_interest relationship."""
        with get_cursor() as cur:
            cur.execute("""
                INSERT INTO paper_research_interests (paper_id, research_interest_id, similarity_score)
                VALUES (%s, %s, %s)
                ON CONFLICT (paper_id, research_interest_id)
                DO UPDATE SET 
                    similarity_score = EXCLUDED.similarity_score,
                    created_at = now()
                RETURNING id
            """, (paper_id, research_interest_id, similarity_score))
            result = cur.fetchone()
            return result['id'] if result else None
    
    @staticmethod
    def bulk_insert(relationships: List[Tuple[int, int, float]]) -> int:
        """Bulk insert paper-research_interest relationships."""
        if not relationships:
            return 0
        
        with get_cursor() as cur:
            cur.executemany("""
                INSERT INTO paper_research_interests (paper_id, research_interest_id, similarity_score)
                VALUES (%s, %s, %s)
                ON CONFLICT (paper_id, research_interest_id)
                DO UPDATE SET 
                    similarity_score = EXCLUDED.similarity_score,
                    created_at = now()
            """, relationships)
            return cur.rowcount
    
    @staticmethod
    def get_papers_for_interest(research_interest_id: int, limit: int = 100, 
                               min_similarity: float = 0.1) -> List[Dict[str, Any]]:
        """Get papers associated with a research interest."""
        with get_cursor() as cur:
            cur.execute("""
                SELECT p.id, p.title, p.abstract, p.score, p.date, p.url, p.date_run,
                       p.rationale, p.related, p.cosine_similarity, p.embedding_model,
                       p.keywords_json, pri.similarity_score
                FROM papers p
                JOIN paper_research_interests pri ON p.id = pri.paper_id
                WHERE pri.research_interest_id = %s AND pri.similarity_score >= %s
                ORDER BY pri.similarity_score DESC
                LIMIT %s
            """, (research_interest_id, min_similarity, limit))
            
            papers = cur.fetchall()
            for paper in papers:
                if paper.get('keywords_json'):
                    try:
                        paper['keywords'] = json.loads(paper['keywords_json'])
                    except:
                        paper['keywords'] = []
            return papers
    
    @staticmethod
    def get_interests_for_paper(paper_id: int) -> List[Dict[str, Any]]:
        """Get research interests associated with a paper."""
        with get_cursor() as cur:
            cur.execute("""
                SELECT ri.id, ri.interest_text, pri.similarity_score
                FROM research_interests ri
                JOIN paper_research_interests pri ON ri.id = pri.research_interest_id
                WHERE pri.paper_id = %s
                ORDER BY pri.similarity_score DESC
            """, (paper_id,))
            
            return cur.fetchall()
    
    @staticmethod
    def get_papers_needing_interest_assignment(cutoff_date: Optional[date] = None) -> List[Dict[str, Any]]:
        """Get papers that don't have research interest assignments yet."""
        with get_cursor() as cur:
            cur.execute("""
                SELECT p.id, p.title, p.abstract, p.embedding, p.date, p.score
                FROM papers p
                LEFT JOIN paper_research_interests pri ON p.id = pri.paper_id
                WHERE pri.paper_id IS NULL
                  AND p.embedding IS NOT NULL
            """)
            
            if cutoff_date:
                cur.execute("""
                    SELECT p.id, p.title, p.abstract, p.embedding, p.date, p.score
                    FROM papers p
                    LEFT JOIN paper_research_interests pri ON p.id = pri.paper_id
                    WHERE pri.paper_id IS NULL
                      AND p.embedding IS NOT NULL
                      AND p.date >= %s
                """, (cutoff_date,))
            
            return cur.fetchall()
    
    @staticmethod
    def delete_all() -> int:
        """Delete all paper-research_interest relationships."""
        with get_cursor() as cur:
            cur.execute("DELETE FROM paper_research_interests")
            return cur.rowcount


class ResearchInterestTrendsRepository:
    """Repository for research interest dashboard and trend queries."""
    
    @staticmethod
    def get_dashboard_data(limit: int = 20, period_type: str = "week", 
                          duration_months: int = 6) -> Dict[str, Any]:
        """Get research interest dashboard data with latest metrics."""
        with get_cursor() as cur:
            # Calculate date range for filtering
            end_date = date.today()
            start_date = end_date - timedelta(days=duration_months * 30)
            
            # Get research interests with their latest metrics
            cur.execute("""
                WITH latest_metrics AS (
                    SELECT 
                        rim.research_interest_id,
                        rim.doc_count,
                        rim.avg_relevance_score,
                        rim.avg_paper_score,
                        rim.growth_rate,
                        rim.forecast_1m,
                        rim.forecast_3m,
                        rim.forecast_6m,
                        ROW_NUMBER() OVER (PARTITION BY rim.research_interest_id ORDER BY rim.period_start DESC) as rn
                    FROM research_interest_metrics rim
                    WHERE rim.period_type = %s
                      AND rim.period_start >= %s
                ),
                interest_counts AS (
                    SELECT 
                        pri.research_interest_id,
                        COUNT(*) as total_papers
                    FROM paper_research_interests pri
                    GROUP BY pri.research_interest_id
                )
                SELECT 
                    ri.id as research_interest_id,
                    ri.interest_text,
                    ri.created_at,
                    ri.updated_at,
                    COALESCE(lm.doc_count, 0) as latest_doc_count,
                    lm.avg_relevance_score as latest_avg_relevance,
                    lm.avg_paper_score as latest_avg_score,
                    lm.growth_rate as latest_growth_rate,
                    lm.forecast_1m,
                    lm.forecast_3m,
                    lm.forecast_6m,
                    COALESCE(ic.total_papers, 0) as total_papers
                FROM research_interests ri
                LEFT JOIN latest_metrics lm ON ri.id = lm.research_interest_id AND lm.rn = 1
                LEFT JOIN interest_counts ic ON ri.id = ic.research_interest_id
                ORDER BY lm.growth_rate DESC NULLS LAST, lm.doc_count DESC NULLS LAST
                LIMIT %s
            """, (period_type, start_date, limit))
            
            trending_interests = cur.fetchall()
            
            # Get total counts
            cur.execute("SELECT COUNT(*) as count FROM research_interests")
            result = cur.fetchone()
            total_interests = result['count'] if result else 0
            
            cur.execute("SELECT COUNT(DISTINCT paper_id) as count FROM paper_research_interests")
            result = cur.fetchone()
            total_papers_with_interests = result['count'] if result else 0
            
            return {
                'trending_interests': trending_interests,
                'total_interests': total_interests,
                'total_papers_with_interests': total_papers_with_interests
            }
    
    @staticmethod
    def search_interests(query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search research interests by text."""
        with get_cursor() as cur:
            cur.execute("""
                WITH latest_metrics AS (
                    SELECT 
                        rim.research_interest_id,
                        rim.doc_count,
                        rim.growth_rate,
                        ROW_NUMBER() OVER (PARTITION BY rim.research_interest_id ORDER BY rim.period_start DESC) as rn
                    FROM research_interest_metrics rim
                    WHERE rim.period_type = 'week'
                ),
                interest_counts AS (
                    SELECT 
                        pri.research_interest_id,
                        COUNT(*) as total_papers
                    FROM paper_research_interests pri
                    GROUP BY pri.research_interest_id
                )
                SELECT 
                    ri.id as research_interest_id,
                    ri.interest_text,
                    ri.created_at,
                    ri.updated_at,
                    COALESCE(lm.doc_count, 0) as latest_doc_count,
                    lm.growth_rate as latest_growth_rate,
                    COALESCE(ic.total_papers, 0) as total_papers
                FROM research_interests ri
                LEFT JOIN latest_metrics lm ON ri.id = lm.research_interest_id AND lm.rn = 1
                LEFT JOIN interest_counts ic ON ri.id = ic.research_interest_id
                WHERE ri.interest_text ILIKE %s
                ORDER BY lm.growth_rate DESC NULLS LAST, lm.doc_count DESC NULLS LAST
                LIMIT %s
            """, (f'%{query}%', limit))
            
            return cur.fetchall()
    
    @staticmethod
    def nuclear_cleanup_all_data() -> Dict[str, int]:
        """NUCLEAR OPTION: Delete all research interest clustering data."""
        deleted_counts = {}
        
        with get_cursor() as cur:
            # Delete in reverse dependency order
            cur.execute("DELETE FROM paper_research_interests")
            deleted_counts['paper_research_interests'] = cur.rowcount
            
            cur.execute("DELETE FROM research_interest_metrics")
            deleted_counts['research_interest_metrics'] = cur.rowcount
            
            cur.execute("DELETE FROM research_interests")
            deleted_counts['research_interests'] = cur.rowcount
            
        return deleted_counts 