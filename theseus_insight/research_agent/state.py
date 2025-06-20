"""
State Management for Research Agent

Defines the OverallState dataclass that maintains the complete state
throughout the research agent workflow execution.
"""

from typing import List, Dict, Any, Optional, TypedDict, Annotated
import operator


class Message(TypedDict):
    """Simple message structure to replace LangChain messages."""
    role: str  # "user", "assistant", "system"
    content: str


class OverallState(TypedDict):
    """
    Complete state management for the research agent workflow.
    
    This state object is passed between all LangGraph nodes and maintains
    the entire context of the research process from initial query to final report.
    """
    
    # Core messaging for workflow (use operator.add to combine messages)
    messages: Annotated[List[Message], operator.add]
    
    # Query decomposition and planning
    original_question: str
    sub_queries: List[str]
    
    # Source retrieval and management
    sources_gathered: Annotated[List[Dict[str, Any]], operator.add]
    judged_sources: List[Dict[str, Any]]
    
    # Evidence compilation and processing
    evidence: Annotated[List[str], operator.add]
    compressed_notes: str
    
    # Full text processing
    full_text_data: Dict[str, str]  # source_id -> full text markdown
    
    # Loop control and progress tracking
    research_loop_count: int
    is_sufficient: bool
    max_loops: int
    
    # Token budget management
    current_token_count: int
    max_research_context_tokens: int
    
    # Configuration and metadata
    task_id: str
    start_time: Optional[str]
    current_node: str
    
    # Error handling and recovery
    errors: Annotated[List[str], operator.add]
    warnings: Annotated[List[str], operator.add]
    
    # Final results
    final_report: str
    citations: List[Dict[str, Any]]


# Helper functions for working with state
def create_initial_state(research_question: str, task_id: str = "", max_loops: int = 3, max_tokens: int = 15000) -> OverallState:
    """Create an initial state for the research workflow."""
    return OverallState(
        messages=[Message(role="user", content=research_question)],
        original_question=research_question,
        sub_queries=[],
        sources_gathered=[],
        judged_sources=[],
        evidence=[],
        compressed_notes="",
        full_text_data={},
        research_loop_count=0,
        is_sufficient=False,
        max_loops=max_loops,
        current_token_count=0,
        max_research_context_tokens=max_tokens,
        task_id=task_id,
        start_time=None,
        current_node="",
        errors=[],
        warnings=[],
        final_report="",
        citations=[]
    )


def get_total_evidence_tokens(state: OverallState) -> int:
    """
    Estimate the total number of tokens in all evidence.
    
    Args:
        state: Current workflow state
        
    Returns:
        int: Estimated token count (rough approximation: 1 token ≈ 4 characters)
    """
    total_chars = sum(len(evidence) for evidence in state.get("evidence", []))
    return total_chars // 4  # Rough token estimation


def needs_compression(state: OverallState) -> bool:
    """
    Check if evidence needs compression due to token budget.
    
    Args:
        state: Current workflow state
        
    Returns:
        bool: True if compression is needed, False otherwise
    """
    return get_total_evidence_tokens(state) > state.get("max_research_context_tokens", 15000)


def should_continue_research(state: OverallState) -> bool:
    """
    Determine if research should continue based on sufficiency and loop limits.
    
    Args:
        state: Current workflow state
        
    Returns:
        bool: True if research should continue, False otherwise
    """
    return (
        not state.get("is_sufficient", False) and 
        state.get("research_loop_count", 0) < state.get("max_loops", 3)
    )


def get_progress_summary(state: OverallState) -> Dict[str, Any]:
    """
    Get a summary of current progress for status reporting.
    
    Args:
        state: Current workflow state
        
    Returns:
        Dict containing progress information
    """
    return {
        "task_id": state.get("task_id", ""),
        "current_node": state.get("current_node", ""),
        "research_loop": state.get("research_loop_count", 0),
        "max_loops": state.get("max_loops", 3),
        "sources_gathered": len(state.get("sources_gathered", [])),
        "judged_sources": len(state.get("judged_sources", [])),
        "evidence_pieces": len(state.get("evidence", [])),
        "is_sufficient": state.get("is_sufficient", False),
        "token_count": get_total_evidence_tokens(state),
        "token_budget": state.get("max_research_context_tokens", 15000),
        "errors": len(state.get("errors", [])),
        "warnings": len(state.get("warnings", []))
    } 