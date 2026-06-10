"""Topic repositories: topics CRUD, topic metrics, paper-topic links."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, date, timedelta
import json

from ...db import get_cursor
from ..base import build_set_clause, to_pgvector
from ._profile_filters import profile_filter_clause


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
        filter_sql, filter_params = profile_filter_clause(
            profile_id, profile_ids, column="profile_id", prefix=" WHERE ")
        with get_cursor() as cur:
            cur.execute(
                f"SELECT * FROM topics{filter_sql} ORDER BY created_at DESC LIMIT %s",
                (*filter_params, limit),
            )
            return cur.fetchall()

    @staticmethod
    def update(topic_id: int, updates: Dict[str, Any]) -> None:
        """Update a topic with the given changes."""
        if not updates:
            return
        
        columns = {
            key: to_pgvector(value) if key == "centroid_embedding" else value
            for key, value in updates.items()
        }
        set_sql, params = build_set_clause(columns, extra=("updated_at = now()",))
        with get_cursor() as cur:
            cur.execute(f"UPDATE topics SET {set_sql} WHERE id = %s", [*params, topic_id])

    @staticmethod
    def delete(topic_id: int) -> None:
        """Delete a topic by ID."""
        with get_cursor() as cur:
            cur.execute("DELETE FROM topics WHERE id = %s", (topic_id,))

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
        filter_sql, filter_params = profile_filter_clause(profile_id, profile_ids)
        with get_cursor() as cur:
            cur.execute(
                f"""
                WITH latest_metrics AS (
                    SELECT DISTINCT ON (topic_id) 
                        tm.*, t.label, t.keywords, t.profile_id
                    FROM topic_metrics tm
                    JOIN topics t ON tm.topic_id = t.id
                    WHERE tm.period_type = %s AND tm.doc_count >= %s{filter_sql}
                    ORDER BY topic_id, period_start DESC
                )
                SELECT * FROM latest_metrics
                ORDER BY growth_rate DESC NULLS LAST, doc_count DESC
                LIMIT %s
                """,
                (period_type, min_doc_count, *filter_params, limit),
            )
            return cur.fetchall()

    @staticmethod
    def get_emerging_topics(period_type: str = "month", limit: int = 10,
                           min_growth_rate: float = 0.5, profile_id: Optional[int] = None, profile_ids: Optional[List[int]] = None) -> List[Dict[str, Any]]:
        """Get topics with high growth rates and forecasts, optionally filtered by profile(s)."""
        filter_sql, filter_params = profile_filter_clause(profile_id, profile_ids)
        with get_cursor() as cur:
            cur.execute(
                f"""
                WITH latest_metrics AS (
                    SELECT DISTINCT ON (topic_id) 
                        tm.*, t.label, t.keywords, t.profile_id
                    FROM topic_metrics tm
                    JOIN topics t ON tm.topic_id = t.id
                    WHERE tm.period_type = %s 
                    AND tm.growth_rate >= %s
                    AND tm.forecast_3m IS NOT NULL{filter_sql}
                    ORDER BY topic_id, period_start DESC
                )
                SELECT * FROM latest_metrics
                ORDER BY (growth_rate * forecast_3m) DESC, doc_count DESC
                LIMIT %s
                """,
                (period_type, min_growth_rate, *filter_params, limit),
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

    @staticmethod
    def get_timeline_with_papers(
        topic_ids: List[int] | None = None,
        period_type: str = "month",
        start_date: date | None = None,
        end_date: date | None = None,
        key_papers_limit: int = 3,
        include_key_papers: bool = True
    ) -> Dict[int, Dict[str, Any]]:
        """
        Get timeline metrics for multiple topics with key papers per period.

        Returns a dict keyed by topic_id containing:
        - topic info (label, keywords, total_papers)
        - periods: list of period data with optional key_papers
        """
        result: Dict[int, Dict[str, Any]] = {}

        with get_cursor() as cur:
            # Build the query for topic metrics
            topic_filter = ""
            params: List[Any] = [period_type]

            if topic_ids:
                placeholders = ','.join(['%s'] * len(topic_ids))
                topic_filter = f"AND t.id IN ({placeholders})"
                params.extend(topic_ids)

            date_filter = ""
            if start_date:
                date_filter += " AND tm.period_start >= %s"
                params.append(start_date)
            if end_date:
                date_filter += " AND tm.period_end <= %s"
                params.append(end_date)

            # Get topics and their metrics
            cur.execute(
                f"""
                SELECT
                    t.id as topic_id,
                    t.label,
                    t.keywords,
                    tm.id as metric_id,
                    tm.period_start,
                    tm.period_end,
                    tm.period_type,
                    tm.doc_count,
                    tm.avg_score,
                    tm.growth_rate,
                    tm.forecast_1m,
                    tm.forecast_3m,
                    tm.forecast_6m,
                    tm.created_at,
                    (SELECT COUNT(*) FROM paper_topics WHERE topic_id = t.id) as total_papers
                FROM topics t
                JOIN topic_metrics tm ON t.id = tm.topic_id
                WHERE tm.period_type = %s {topic_filter} {date_filter}
                ORDER BY t.id, tm.period_start ASC
                """,
                params
            )
            metrics_rows = cur.fetchall()

            # Build result structure
            for row in metrics_rows:
                topic_id = row["topic_id"]

                if topic_id not in result:
                    result[topic_id] = {
                        "topic_id": topic_id,
                        "label": row["label"],
                        "keywords": row["keywords"] or [],
                        "total_papers": row["total_papers"] or 0,
                        "periods": []
                    }

                # Calculate phase based on growth_rate and doc_count
                growth_rate = row["growth_rate"]
                doc_count = row["doc_count"]
                phase = TopicMetricsRepository._calculate_phase(growth_rate, doc_count)

                period_data = {
                    "period_start": row["period_start"].isoformat() if isinstance(row["period_start"], date) else str(row["period_start"]),
                    "period_end": row["period_end"].isoformat() if isinstance(row["period_end"], date) else str(row["period_end"]),
                    "period_type": row["period_type"],
                    "doc_count": doc_count,
                    "growth_rate": growth_rate,
                    "phase": phase,
                    "forecast_1m": row["forecast_1m"],
                    "forecast_3m": row["forecast_3m"],
                    "forecast_6m": row["forecast_6m"],
                    "is_forecast": False,
                    "key_papers": None
                }

                result[topic_id]["periods"].append(period_data)

            # Get key papers for each period if requested
            if include_key_papers and result:
                for topic_id, topic_data in result.items():
                    for period in topic_data["periods"]:
                        period_start = period["period_start"]
                        period_end = period["period_end"]

                        cur.execute(
                            """
                            SELECT
                                p.id, p.title, p.date, p.score, pt.relevance_score
                            FROM papers p
                            JOIN paper_topics pt ON p.id = pt.paper_id
                            WHERE pt.topic_id = %s
                                AND p.date >= %s
                                AND p.date <= %s
                            ORDER BY pt.relevance_score DESC, p.score DESC NULLS LAST
                            LIMIT %s
                            """,
                            (topic_id, period_start, period_end, key_papers_limit)
                        )
                        papers = cur.fetchall()

                        period["key_papers"] = [
                            {
                                "id": p["id"],
                                "title": p["title"],
                                "date": p["date"].isoformat() if isinstance(p["date"], date) else str(p["date"]),
                                "score": p["score"],
                                "relevance_score": p["relevance_score"]
                            }
                            for p in papers
                        ]

        return result

    @staticmethod
    def _calculate_phase(growth_rate: float | None, doc_count: int) -> str:
        """
        Calculate the growth phase based on growth rate and doc count.

        Phases:
        - emerging: High growth (>50%) with relatively low volume
        - growth: Positive growth (>10%)
        - stable: Near-zero growth (-10% to 10%)
        - declining: Negative growth (<-10%)
        """
        if growth_rate is None:
            return "stable"

        if growth_rate > 0.5:  # >50% growth
            return "emerging"
        elif growth_rate > 0.1:  # >10% growth
            return "growth"
        elif growth_rate >= -0.1:  # -10% to 10%
            return "stable"
        else:  # <-10% growth
            return "declining"


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


