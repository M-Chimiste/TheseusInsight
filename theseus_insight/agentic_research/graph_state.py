from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from langchain_core.messages import BaseMessage


@dataclass
class OverallState:
    """State container for the simplified research agent."""

    messages: List[BaseMessage]
    sub_queries: List[str] = field(default_factory=list)
    sources_gathered: List[Dict[str, Any]] = field(default_factory=list)
    judged_sources: List[Dict[str, Any]] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)
    compressed_notes: str = ""
    research_loop_count: int = 0
    is_sufficient: bool = False
    # Optional fields for compatibility with callbacks
    needs_clarification: Optional[bool] = None
    clarifying_questions: Optional[List[str]] = None
    follow_up_queries: Optional[List[str]] = None


# Backwards compatibility with earlier versions ---------------------------------

class QueryGenerationState(Dict[str, Any]):
    pass

class ReflectionState(Dict[str, Any]):
    pass

class WebSearchState(Dict[str, Any]):
    pass

class QueryRefinementState(Dict[str, Any]):
    pass

class JudgeState(Dict[str, Any]):
    pass

class OutlineState(Dict[str, Any]):
    pass


@dataclass(kw_only=True)
class SearchStateOutput:
    running_summary: Optional[str] = None
