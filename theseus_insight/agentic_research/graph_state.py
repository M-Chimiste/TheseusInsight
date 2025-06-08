from __future__ import annotations

import operator
from dataclasses import dataclass, field
from typing import TypedDict, List, Dict, Any, Optional
from typing_extensions import Annotated

from langgraph.graph import add_messages


class OverallState(TypedDict):
    """Main state container for the research agent graph workflow."""
    messages: Annotated[list, add_messages]
    search_query: Annotated[list, operator.add]
    web_research_result: Annotated[list, operator.add]
    sources_gathered: Annotated[list, operator.add]
    initial_search_query_count: int
    max_research_loops: int
    research_loop_count: int
    reasoning_model: str


class ReflectionState(TypedDict):
    """State for the reflection node that evaluates research progress."""
    is_sufficient: bool
    knowledge_gap: str
    follow_up_queries: Annotated[list, operator.add]
    research_loop_count: int
    number_of_ran_queries: int


class Query(TypedDict):
    """Individual search query with rationale."""
    query: str
    rationale: str


class QueryGenerationState(TypedDict):
    """State after generating initial search queries."""
    query_list: List[Query]


class WebSearchState(TypedDict):
    """State for individual search operations."""
    search_query: str
    id: str


@dataclass(kw_only=True)
class SearchStateOutput:
    """Output container for search results."""
    running_summary: str = field(default=None)  # Final report 