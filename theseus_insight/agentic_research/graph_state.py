from __future__ import annotations

import operator
from dataclasses import dataclass, field
from typing import TypedDict, List, Dict, Any, Optional
from typing_extensions import Annotated

from langgraph.graph import add_messages


class OverallState(TypedDict):
    """
    Main state container for the research agent graph workflow.
    This TypedDict defines the entire state of the graph. Every key that any node
    reads from or writes to must be defined here.
    """
    # Core conversation and research results (accumulated)
    messages: Annotated[list, add_messages]
    search_query: Annotated[list, operator.add]
    web_research_result: Annotated[list, operator.add]
    sources_gathered: Annotated[list, operator.add]
    
    # State from query refinement
    needs_clarification: Optional[bool]
    clarifying_questions: Optional[List[str]]
    refined_query: Optional[str]
    original_query: Optional[str]

    # State from query generation
    query_list: Optional[List[Query]]

    # State from paper judging and PDF processing
    judged_sources: Optional[List[Dict[str, Any]]]
    judged_papers: Optional[List[Dict[str, Any]]]
    rejected_papers: Optional[List[Dict[str, Any]]]
    external_judged_papers: Optional[List[Dict[str, Any]]]
    external_rejected_papers: Optional[List[Dict[str, Any]]]
    
    # State from outline generation
    current_outline: Optional[str]
    paper_contexts: Optional[List[str]]

    # State from reflection and research evaluation
    is_sufficient: Optional[bool]
    knowledge_gap: Optional[str]
    follow_up_queries: Annotated[list, operator.add]
    
    # Configuration and loop control
    initial_search_query_count: Optional[int]
    max_research_loops: Optional[int]
    research_loop_count: Optional[int]
    number_of_ran_queries: Optional[int]
    reasoning_model: Optional[str]


class ReflectionState(TypedDict):
    """State for the reflection node that evaluates research progress."""
    is_sufficient: bool
    knowledge_gap: str
    follow_up_queries: List[str]
    research_loop_count: int
    number_of_ran_queries: int


class Query(TypedDict):
    """Individual search query with rationale."""
    query: str
    rationale: str


class QueryRefinementState(TypedDict):
    """State for query refinement and clarification."""
    needs_clarification: bool
    clarifying_questions: List[str]
    refined_query: str
    original_query: str


class QueryGenerationState(TypedDict):
    """State after generating initial search queries."""
    query_list: List[Query]


class WebSearchState(TypedDict):
    """State for individual search operations."""
    search_query: str
    id: str


class JudgeState(TypedDict):
    """State for relevance judging of papers."""
    judged_papers: List[Dict[str, Any]]
    rejected_papers: List[Dict[str, Any]]


class OutlineState(TypedDict):
    """State for research outline generation."""
    outline: str
    paper_contexts: List[str]


@dataclass(kw_only=True)
class SearchStateOutput:
    """Output container for search results."""
    running_summary: str = field(default=None)  # Final report 