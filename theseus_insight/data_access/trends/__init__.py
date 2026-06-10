"""Data access layer for trends and topics.

Converted from a single 2,015-line module into a package; this __init__
re-exports every class so existing import paths keep working
(`from ..data_access.trends import X` and the data_access package
re-export).
"""
from .topics import (
    PaperTopicsRepository,
    TopicMetricsRepository,
    TopicsRepository,
)
from .trend_metrics import TrendsRepository
from .research_interests import (
    PaperResearchInterestsRepository,
    ResearchInterestMetricsRepository,
    ResearchInterestTrendsRepository,
    ResearchInterestsRepository,
)
from .profile_interests import (
    ProfileInterestMetricsRepository,
    ProfilePaperInterestsRepository,
)

__all__ = [
    "PaperResearchInterestsRepository",
    "PaperTopicsRepository",
    "ProfileInterestMetricsRepository",
    "ProfilePaperInterestsRepository",
    "ResearchInterestMetricsRepository",
    "ResearchInterestTrendsRepository",
    "ResearchInterestsRepository",
    "TopicMetricsRepository",
    "TopicsRepository",
    "TrendsRepository",
]
