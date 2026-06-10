"""Profile-scoped interest repositories."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, date, timedelta
import json

from ...db import get_cursor
from ..base import build_set_clause, to_pgvector

from .topics import TopicMetricsRepository


class ProfilePaperInterestsRepository:
    """Repository for profile-specific paper-interest associations."""

    @staticmethod
    def insert(paper_id: int, profile_interest_id: int, similarity_score: float) -> int:
        """Insert a paper-interest association."""
        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO profile_paper_interests (paper_id, profile_interest_id, similarity_score)
                VALUES (%s, %s, %s)
                ON CONFLICT (paper_id, profile_interest_id) DO UPDATE SET similarity_score = EXCLUDED.similarity_score
                RETURNING id
                """,
                (paper_id, profile_interest_id, similarity_score)
            )
            row = cur.fetchone()
            return row['id'] if row else 0

    @staticmethod
    def bulk_insert(associations: List[Tuple[int, int, float]]) -> int:
        """Bulk insert paper-interest associations. Returns count inserted."""
        if not associations:
            return 0

        with get_cursor() as cur:
            from psycopg.sql import SQL
            # Use executemany with ON CONFLICT
            cur.executemany(
                """
                INSERT INTO profile_paper_interests (paper_id, profile_interest_id, similarity_score)
                VALUES (%s, %s, %s)
                ON CONFLICT (paper_id, profile_interest_id) DO UPDATE SET similarity_score = EXCLUDED.similarity_score
                """,
                associations
            )
            return len(associations)

    @staticmethod
    def get_papers_for_interest(
        profile_interest_id: int,
        limit: int = 100,
        min_similarity: float = 0.0,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[Dict[str, Any]]:
        """Get papers associated with a profile interest, including profile-specific scores."""
        with get_cursor() as cur:
            # First get the profile_id from the profile interest
            cur.execute(
                "SELECT profile_id FROM profile_research_interests WHERE id = %s",
                (profile_interest_id,)
            )
            result = cur.fetchone()
            if not result:
                return []
            profile_id = result['profile_id']

            # Query papers with profile-specific scores
            query = """
                SELECT
                    p.id, p.title, p.abstract, p.date, p.url, p.date_run,
                    p.cosine_similarity, p.embedding_model, p.keywords_json,
                    ppi.similarity_score,
                    -- Use profile-specific score/related/rationale if available, otherwise base paper values
                    COALESCE(pps.score, p.score) as score,
                    COALESCE(pps.related, p.related) as related,
                    COALESCE(pps.rationale, p.rationale) as rationale,
                    -- Also include profile-specific fields for UI
                    pps.score as profile_score,
                    pps.related as profile_related,
                    pps.rationale as profile_rationale
                FROM profile_paper_interests ppi
                JOIN papers p ON ppi.paper_id = p.id
                LEFT JOIN paper_profile_scores pps ON p.id = pps.paper_id AND pps.profile_id = %s
                WHERE ppi.profile_interest_id = %s
                  AND ppi.similarity_score >= %s
            """
            params = [profile_id, profile_interest_id, min_similarity]

            if start_date:
                query += " AND p.date >= %s"
                params.append(start_date)
            if end_date:
                query += " AND p.date <= %s"
                params.append(end_date)

            query += " ORDER BY ppi.similarity_score DESC LIMIT %s"
            params.append(limit)

            cur.execute(query, params)
            papers = cur.fetchall()

            # Parse keywords JSON
            for paper in papers:
                if paper.get('keywords_json'):
                    try:
                        paper['keywords'] = json.loads(paper['keywords_json'])
                    except:
                        paper['keywords'] = []

            return papers

    @staticmethod
    def delete_for_interest(profile_interest_id: int) -> int:
        """Delete all associations for a profile interest."""
        with get_cursor() as cur:
            cur.execute(
                "DELETE FROM profile_paper_interests WHERE profile_interest_id = %s",
                (profile_interest_id,)
            )
            return cur.rowcount

    @staticmethod
    def delete_for_profile(profile_id: int) -> int:
        """Delete all paper-interest associations for a profile."""
        with get_cursor() as cur:
            cur.execute(
                """
                DELETE FROM profile_paper_interests
                WHERE profile_interest_id IN (
                    SELECT id FROM profile_research_interests WHERE profile_id = %s
                )
                """,
                (profile_id,)
            )
            return cur.rowcount


class ProfileInterestMetricsRepository:
    """Repository for profile-specific interest time-series metrics."""

    @staticmethod
    def insert(
        profile_interest_id: int,
        period_start: date,
        period_end: date,
        period_type: str,
        doc_count: int = 0,
        avg_relevance_score: Optional[float] = None,
        avg_paper_score: Optional[float] = None,
        growth_rate: Optional[float] = None
    ) -> int:
        """Insert or update a metrics record."""
        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO profile_interest_metrics
                (profile_interest_id, period_start, period_end, period_type,
                 doc_count, avg_relevance_score, avg_paper_score, growth_rate)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (profile_interest_id, period_start, period_type)
                DO UPDATE SET
                    doc_count = EXCLUDED.doc_count,
                    avg_relevance_score = EXCLUDED.avg_relevance_score,
                    avg_paper_score = EXCLUDED.avg_paper_score,
                    growth_rate = EXCLUDED.growth_rate
                RETURNING id
                """,
                (profile_interest_id, period_start, period_end, period_type,
                 doc_count, avg_relevance_score, avg_paper_score, growth_rate)
            )
            row = cur.fetchone()
            return row['id'] if row else 0

    @staticmethod
    def get_interest_timeline(
        profile_interest_id: int,
        period_type: str = 'week',
        limit: int = 52
    ) -> List[Dict[str, Any]]:
        """Get timeline metrics for a profile interest."""
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT * FROM profile_interest_metrics
                WHERE profile_interest_id = %s AND period_type = %s
                ORDER BY period_start DESC
                LIMIT %s
                """,
                (profile_interest_id, period_type, limit)
            )
            return cur.fetchall()

    @staticmethod
    def get_dashboard_data(
        profile_ids: List[int],
        limit: int = 20,
        period_type: str = 'week',
        duration_months: int = 6
    ) -> Dict[str, Any]:
        """Get dashboard data for profile interests."""
        with get_cursor() as cur:
            end_date = date.today()
            start_date = end_date - timedelta(days=duration_months * 30)

            # Create placeholders for profile IDs
            placeholders = ','.join(['%s'] * len(profile_ids))

            # Note: Metrics are always stored with period_type='week' - aggregation happens in frontend
            cur.execute(f"""
                WITH latest_metrics AS (
                    SELECT
                        pim.profile_interest_id,
                        pim.doc_count,
                        pim.avg_relevance_score,
                        pim.avg_paper_score,
                        pim.growth_rate,
                        ROW_NUMBER() OVER (PARTITION BY pim.profile_interest_id ORDER BY pim.period_start DESC) as rn
                    FROM profile_interest_metrics pim
                    JOIN profile_research_interests pri ON pim.profile_interest_id = pri.id
                    WHERE pim.period_type = 'week'
                      AND pim.period_start >= %s
                      AND pri.profile_id IN ({placeholders})
                ),
                interest_counts AS (
                    SELECT
                        ppi.profile_interest_id,
                        COUNT(*) as total_papers
                    FROM profile_paper_interests ppi
                    JOIN profile_research_interests pri ON ppi.profile_interest_id = pri.id
                    WHERE pri.profile_id IN ({placeholders})
                    GROUP BY ppi.profile_interest_id
                )
                SELECT
                    pri.id as profile_interest_id,
                    pri.profile_id,
                    pri.interest_text,
                    pri.embedding_model,
                    pri.created_at,
                    pri.updated_at,
                    COALESCE(lm.doc_count, 0) as latest_doc_count,
                    lm.avg_relevance_score as latest_avg_relevance,
                    lm.avg_paper_score as latest_avg_score,
                    lm.growth_rate as latest_growth_rate,
                    COALESCE(ic.total_papers, 0) as total_papers
                FROM profile_research_interests pri
                LEFT JOIN latest_metrics lm ON pri.id = lm.profile_interest_id AND lm.rn = 1
                LEFT JOIN interest_counts ic ON pri.id = ic.profile_interest_id
                WHERE pri.profile_id IN ({placeholders})
                ORDER BY lm.growth_rate DESC NULLS LAST, lm.doc_count DESC NULLS LAST
                LIMIT %s
            """, (start_date, *profile_ids, *profile_ids, *profile_ids, limit))

            trending_interests = cur.fetchall()

            # Get total counts
            cur.execute(f"""
                SELECT COUNT(*) as count FROM profile_research_interests
                WHERE profile_id IN ({placeholders})
            """, profile_ids)
            result = cur.fetchone()
            total_interests = result['count'] if result else 0

            cur.execute(f"""
                SELECT COUNT(DISTINCT ppi.paper_id) as count
                FROM profile_paper_interests ppi
                JOIN profile_research_interests pri ON ppi.profile_interest_id = pri.id
                WHERE pri.profile_id IN ({placeholders})
            """, profile_ids)
            result = cur.fetchone()
            total_papers_with_interests = result['count'] if result else 0

            return {
                'trending_interests': trending_interests,
                'total_interests': total_interests,
                'total_papers_with_interests': total_papers_with_interests
            }

    @staticmethod
    def delete_for_interest(profile_interest_id: int) -> int:
        """Delete all metrics for a profile interest."""
        with get_cursor() as cur:
            cur.execute(
                "DELETE FROM profile_interest_metrics WHERE profile_interest_id = %s",
                (profile_interest_id,)
            )
            return cur.rowcount

    @staticmethod
    def delete_for_profile(profile_id: int) -> int:
        """Delete all metrics for a profile."""
        with get_cursor() as cur:
            cur.execute(
                """
                DELETE FROM profile_interest_metrics
                WHERE profile_interest_id IN (
                    SELECT id FROM profile_research_interests WHERE profile_id = %s
                )
                """,
                (profile_id,)
            )
            return cur.rowcount

    @staticmethod
    def _get_period_key(d: date, period_type: str) -> tuple:
        """Get the period key for grouping dates."""
        if period_type == "week":
            # Week starts on Monday
            week_start = d - timedelta(days=d.weekday())
            return (week_start.year, week_start.month, week_start.day)
        elif period_type == "month":
            return (d.year, d.month)
        elif period_type == "quarter":
            quarter = (d.month - 1) // 3 + 1
            return (d.year, quarter)
        else:
            return (d.year,)

    @staticmethod
    def _get_period_bounds(period_key: tuple, period_type: str) -> tuple:
        """Get start and end dates for a period key."""
        if period_type == "week":
            year, month, day = period_key
            start = date(year, month, day)
            end = start + timedelta(days=6)
        elif period_type == "month":
            year, month = period_key
            start = date(year, month, 1)
            # Get last day of month
            if month == 12:
                end = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                end = date(year, month + 1, 1) - timedelta(days=1)
        elif period_type == "quarter":
            year, quarter = period_key
            start_month = (quarter - 1) * 3 + 1
            start = date(year, start_month, 1)
            end_month = quarter * 3
            if end_month == 12:
                end = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                end = date(year, end_month + 1, 1) - timedelta(days=1)
        else:
            # Year
            year = period_key[0]
            start = date(year, 1, 1)
            end = date(year, 12, 31)
        return start, end

    @staticmethod
    def get_timeline_with_papers(
        interest_ids: List[int] | None = None,
        period_type: str = "week",
        start_date: date | None = None,
        end_date: date | None = None,
        key_papers_limit: int = 3,
        include_key_papers: bool = True
    ) -> Dict[int, Dict[str, Any]]:
        """
        Get timeline metrics for profile interests with key papers per period.

        Always reads weekly data from DB and aggregates to the requested period_type.
        Supports: week, month, quarter.

        Returns a dict keyed by profile_interest_id containing:
        - interest info (interest_text, total_papers)
        - periods: list of period data with optional key_papers
        """
        result: Dict[int, Dict[str, Any]] = {}

        with get_cursor() as cur:
            # Always query weekly data (our base granularity)
            interest_filter = ""
            params: List[Any] = ["week"]  # Always fetch weekly data

            if interest_ids:
                placeholders = ','.join(['%s'] * len(interest_ids))
                interest_filter = f"AND pri.id IN ({placeholders})"
                params.extend(interest_ids)

            date_filter = ""
            if start_date:
                date_filter += " AND pim.period_start >= %s"
                params.append(start_date)
            if end_date:
                date_filter += " AND pim.period_end <= %s"
                params.append(end_date)

            # Get profile interests and their weekly metrics
            cur.execute(
                f"""
                SELECT
                    pri.id as interest_id,
                    pri.profile_id,
                    pri.interest_text,
                    pri.short_label,
                    pim.id as metric_id,
                    pim.period_start,
                    pim.period_end,
                    pim.period_type,
                    pim.doc_count,
                    pim.avg_relevance_score,
                    pim.avg_paper_score,
                    pim.growth_rate,
                    pim.created_at,
                    (SELECT COUNT(*) FROM profile_paper_interests WHERE profile_interest_id = pri.id) as total_papers
                FROM profile_research_interests pri
                JOIN profile_interest_metrics pim ON pri.id = pim.profile_interest_id
                WHERE pim.period_type = %s {interest_filter} {date_filter}
                ORDER BY pri.id, pim.period_start ASC
                """,
                params
            )
            metrics_rows = cur.fetchall()

            # Group weekly data by interest, then aggregate to requested period_type
            interest_weekly_data: Dict[int, Dict[str, Any]] = {}

            for row in metrics_rows:
                interest_id = row["interest_id"]

                if interest_id not in interest_weekly_data:
                    interest_text = row["interest_text"]
                    short_label = row["short_label"]
                    # Use short_label if available, otherwise truncate interest_text
                    if short_label:
                        label = short_label
                    else:
                        label = interest_text[:50] + "..." if len(interest_text) > 50 else interest_text

                    interest_weekly_data[interest_id] = {
                        "topic_id": interest_id,
                        "topic_label": label,
                        "short_label": short_label,
                        "interest_text": interest_text,
                        "profile_id": row["profile_id"],
                        "keywords": [],
                        "total_papers": row["total_papers"] or 0,
                        "weekly_periods": []
                    }

                interest_weekly_data[interest_id]["weekly_periods"].append({
                    "period_start": row["period_start"],
                    "period_end": row["period_end"],
                    "doc_count": row["doc_count"] or 0,
                    "avg_relevance_score": row["avg_relevance_score"],
                    "avg_paper_score": row["avg_paper_score"],
                    "growth_rate": row["growth_rate"]
                })

            # Now aggregate weekly data to the requested period_type
            for interest_id, interest_data in interest_weekly_data.items():
                weekly_periods = interest_data.pop("weekly_periods")

                # Group weeks into the target period
                period_groups: Dict[tuple, List[Dict]] = {}
                for week in weekly_periods:
                    period_key = ProfileInterestMetricsRepository._get_period_key(
                        week["period_start"], period_type
                    )
                    if period_key not in period_groups:
                        period_groups[period_key] = []
                    period_groups[period_key].append(week)

                # Aggregate each period group
                aggregated_periods = []
                sorted_keys = sorted(period_groups.keys())
                prev_doc_count = None

                for period_key in sorted_keys:
                    weeks = period_groups[period_key]
                    period_start, period_end = ProfileInterestMetricsRepository._get_period_bounds(
                        period_key, period_type
                    )

                    # Aggregate metrics
                    total_docs = sum(w["doc_count"] for w in weeks)

                    # Weighted average for relevance/paper scores
                    relevance_scores = [(w["avg_relevance_score"], w["doc_count"])
                                       for w in weeks if w["avg_relevance_score"] is not None]
                    if relevance_scores:
                        total_weight = sum(w[1] for w in relevance_scores)
                        avg_relevance = sum(w[0] * w[1] for w in relevance_scores) / total_weight if total_weight > 0 else None
                    else:
                        avg_relevance = None

                    paper_scores = [(w["avg_paper_score"], w["doc_count"])
                                   for w in weeks if w["avg_paper_score"] is not None]
                    if paper_scores:
                        total_weight = sum(w[1] for w in paper_scores)
                        avg_paper = sum(w[0] * w[1] for w in paper_scores) / total_weight if total_weight > 0 else None
                    else:
                        avg_paper = None

                    # Calculate growth rate from previous period
                    if prev_doc_count is not None and prev_doc_count > 0:
                        growth_rate = (total_docs - prev_doc_count) / prev_doc_count
                    else:
                        growth_rate = 0.0

                    phase = TopicMetricsRepository._calculate_phase(growth_rate, total_docs)

                    aggregated_periods.append({
                        "period_start": period_start.isoformat(),
                        "period_end": period_end.isoformat(),
                        "period_type": period_type,
                        "doc_count": total_docs,
                        "growth_rate": growth_rate,
                        "phase": phase,
                        "forecast_1m": None,
                        "forecast_3m": None,
                        "forecast_6m": None,
                        "is_forecast": False,
                        "key_papers": None
                    })

                    prev_doc_count = total_docs

                interest_data["periods"] = aggregated_periods
                result[interest_id] = interest_data

            # Get key papers for each period if requested
            if include_key_papers and result:
                for interest_id, interest_data in result.items():
                    for period in interest_data["periods"]:
                        period_start = period["period_start"]
                        period_end = period["period_end"]

                        cur.execute(
                            """
                            SELECT
                                p.id, p.title, p.date, p.score, ppi.similarity_score as relevance_score
                            FROM papers p
                            JOIN profile_paper_interests ppi ON p.id = ppi.paper_id
                            WHERE ppi.profile_interest_id = %s
                                AND p.date >= %s
                                AND p.date <= %s
                            ORDER BY ppi.similarity_score DESC, p.score DESC NULLS LAST
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