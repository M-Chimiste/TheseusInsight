"""
Research Agent Module for Theseus Insight

A LangGraph-powered research agent that ingests user research questions,
iteratively retrieves evidence, and produces well-cited summaries.
"""

from .state import OverallState
from .tools import (
    LocalSearchTool,
    ExternalSearchTool,
    UnifiedSearchTool,
    SourceDeduplicator,
    CrossEncoderReranker,
    PaperInfo
)
from .nodes import (
    QueryPlannerNode,
    RetrieverUnifiedNode,
    EvidenceSelectorNode,
    ScratchpadCompressNode,
    AnswerGeneratorNode
)
from .workflow import ResearchAgentWorkflow, create_research_workflow

__all__ = [
    "OverallState",
    "LocalSearchTool",
    "ExternalSearchTool", 
    "UnifiedSearchTool",
    "SourceDeduplicator",
    "CrossEncoderReranker",
    "PaperInfo",
    "QueryPlannerNode",
    "RetrieverUnifiedNode",
    "EvidenceSelectorNode",
    "ScratchpadCompressNode",
    "AnswerGeneratorNode",
    "ResearchAgentWorkflow",
    "create_research_workflow"
] 