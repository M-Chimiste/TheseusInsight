"""TrendsRepository: dashboard aggregation and metrics cleanup."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, date, timedelta
import json

from ...db import get_cursor
from ..base import build_set_clause, to_pgvector



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

