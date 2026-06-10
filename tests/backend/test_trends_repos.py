"""Execute every profile_filter_clause-composed query in all 3 filter modes.

These are SQL-validity characterization tests for the B5 CTE collapse:
empty result sets are fine, syntax errors are not.
"""
import pytest


def test_profile_filter_clause():
    from theseus_insight.data_access.trends._profile_filters import profile_filter_clause

    sql, params = profile_filter_clause(None, [1, 2])
    assert sql == " AND t.profile_id IN (%s,%s)"
    assert params == [1, 2]

    sql, params = profile_filter_clause(7, None)
    assert sql == " AND t.profile_id = %s"
    assert params == [7]

    # profile_ids wins over profile_id (original branch order)
    sql, params = profile_filter_clause(7, [1])
    assert sql == " AND t.profile_id IN (%s)"
    assert params == [1]

    sql, params = profile_filter_clause(None, None)
    assert (sql, params) == ("", [])

    sql, params = profile_filter_clause(7, None, column="profile_id", prefix=" WHERE ")
    assert sql == " WHERE profile_id = %s"


FILTER_MODES = [
    {"profile_id": None, "profile_ids": None},
    {"profile_id": 1, "profile_ids": None},
    {"profile_id": None, "profile_ids": [1, 2]},
]


@pytest.mark.parametrize("mode", FILTER_MODES)
def test_topics_queries_execute(empty_db, mode):
    from theseus_insight.data_access.trends import TopicsRepository, TopicMetricsRepository

    assert TopicsRepository.get_all(**mode) == []
    # TopicsRepository.search_by_keywords was deleted in B5: zero callers and
    # its SQL (array_length(keywords && %s, 1)) raised UndefinedFunction on
    # every invocation — dead since inception.
    assert TopicMetricsRepository.get_trending_topics(**mode) == []
    assert TopicMetricsRepository.get_emerging_topics(**mode) == []


@pytest.mark.parametrize("mode", FILTER_MODES)
def test_dashboard_query_executes(empty_db, mode):
    from theseus_insight.data_access.trends import TrendsRepository

    data = TrendsRepository.get_dashboard_data(**mode)
    assert data["trending_topics"] == []
    assert data["total_topics"] == 0
    assert data["total_papers_with_topics"] == 0
