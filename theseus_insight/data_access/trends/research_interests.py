"""Research-interest repositories (global, non-profile-scoped)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, date, timedelta
import json

from ...db import get_cursor
from ..base import build_set_clause, to_pgvector

from .topics import TopicMetricsRepository


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

    @staticmethod
    def get_timeline_with_papers(
        interest_ids: List[int] | None = None,
        period_type: str = "month",
        start_date: date | None = None,
        end_date: date | None = None,
        key_papers_limit: int = 3,
        include_key_papers: bool = True
    ) -> Dict[int, Dict[str, Any]]:
        """
        Get timeline metrics for research interests with key papers per period.

        Returns a dict keyed by research_interest_id containing:
        - interest info (interest_text, total_papers)
        - periods: list of period data with optional key_papers
        """
        result: Dict[int, Dict[str, Any]] = {}

        with get_cursor() as cur:
            # Build the query for interest metrics
            interest_filter = ""
            params: List[Any] = [period_type]

            if interest_ids:
                placeholders = ','.join(['%s'] * len(interest_ids))
                interest_filter = f"AND ri.id IN ({placeholders})"
                params.extend(interest_ids)

            date_filter = ""
            if start_date:
                date_filter += " AND rim.period_start >= %s"
                params.append(start_date)
            if end_date:
                date_filter += " AND rim.period_end <= %s"
                params.append(end_date)

            # Get research interests and their metrics
            cur.execute(
                f"""
                SELECT
                    ri.id as interest_id,
                    ri.interest_text,
                    rim.id as metric_id,
                    rim.period_start,
                    rim.period_end,
                    rim.period_type,
                    rim.doc_count,
                    rim.avg_relevance_score,
                    rim.avg_paper_score,
                    rim.growth_rate,
                    rim.forecast_1m,
                    rim.forecast_3m,
                    rim.forecast_6m,
                    rim.created_at,
                    (SELECT COUNT(*) FROM paper_research_interests WHERE research_interest_id = ri.id) as total_papers
                FROM research_interests ri
                JOIN research_interest_metrics rim ON ri.id = rim.research_interest_id
                WHERE rim.period_type = %s {interest_filter} {date_filter}
                ORDER BY ri.id, rim.period_start ASC
                """,
                params
            )
            metrics_rows = cur.fetchall()

            # Build result structure
            for row in metrics_rows:
                interest_id = row["interest_id"]

                if interest_id not in result:
                    # Create short label from interest_text (first ~50 chars or first sentence)
                    interest_text = row["interest_text"]
                    label = interest_text[:50] + "..." if len(interest_text) > 50 else interest_text

                    result[interest_id] = {
                        "topic_id": interest_id,  # Use topic_id for compatibility with timeline
                        "topic_label": label,  # Use topic_label for compatibility
                        "interest_text": interest_text,  # Full text
                        "keywords": [],  # Research interests don't have keywords
                        "total_papers": row["total_papers"] or 0,
                        "periods": []
                    }

                # Calculate phase based on growth_rate
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

                result[interest_id]["periods"].append(period_data)

            # Get key papers for each period if requested
            if include_key_papers and result:
                for interest_id, interest_data in result.items():
                    for period in interest_data["periods"]:
                        period_start = period["period_start"]
                        period_end = period["period_end"]

                        cur.execute(
                            """
                            SELECT
                                p.id, p.title, p.date, p.score, pri.similarity_score as relevance_score
                            FROM papers p
                            JOIN paper_research_interests pri ON p.id = pri.paper_id
                            WHERE pri.research_interest_id = %s
                                AND p.date >= %s
                                AND p.date <= %s
                            ORDER BY pri.similarity_score DESC, p.score DESC NULLS LAST
                            LIMIT %s
                            """,
                            (interest_id, period_start, period_end, key_papers_limit)
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


# === Profile-Aware Research Interest Repositories ===
# These work with profile_research_interests table and new profile_* tables

