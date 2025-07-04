"""
State Management for Mind-Map Explorer

Defines the MindMapState dataclass that maintains the complete state
throughout the mind-map generation workflow execution.
"""

from typing import List, Dict, Any, Optional, TypedDict, Annotated
import operator


class Message(TypedDict):
    """Simple message structure for workflow communication."""
    role: str  # "user", "assistant", "system"
    content: str


class PaperNode(TypedDict):
    """Represents a paper node in the mind-map."""
    id: int
    title: str
    abstract: str
    date: str
    url: str
    score: float
    rationale: str
    similarity_score: float
    summary: Optional[str]  # LLM-generated summary
    keywords: Optional[List[str]]
    x: Optional[float]  # UI positioning
    y: Optional[float]  # UI positioning


class MindMapEdge(TypedDict):
    """Represents a connection between papers in the mind-map."""
    source_id: int
    target_id: int
    similarity_score: float
    relationship_type: str  # "similar", "cites", "cited_by", etc.


class MindMapState(TypedDict):
    """
    Complete state management for the mind-map generation workflow.
    
    This state object is passed between all LangGraph nodes and maintains
    the entire context of the mind-map generation process.
    """
    
    # Core messaging for workflow
    messages: Annotated[List[Message], operator.add]
    
    # Seed paper selection
    seed_paper_id: int
    seed_paper: Optional[PaperNode]
    
    # Similarity search parameters
    k_neighbors: int  # Number of similar papers to find
    similarity_threshold: float
    
    # Multi-order expansion parameters
    expansion_order: int  # Number of expansion orders (1-5)
    max_nodes_per_order: int  # Maximum nodes to expand from each paper
    current_expansion_order: int  # Current order being processed
    
    # Profile filtering context
    profile_id: Optional[int]  # Single profile filter
    profile_ids: Optional[List[int]]  # Multiple profile filter
    profile_tag: Optional[str]  # Single tag filter
    profile_tags: Optional[List[str]]  # Multiple tag filter
    resolved_profile_ids: Optional[List[int]]  # Final resolved profile IDs from tags
    
    # Retrieved papers and relationships
    similar_papers: List[PaperNode]
    edges: List[MindMapEdge]
    all_papers: Dict[int, PaperNode]  # All papers found across all orders
    papers_by_order: Dict[int, List[int]]  # Order -> list of paper IDs
    
    # LLM-generated summaries
    summaries: Dict[int, str]  # paper_id -> summary
    
    # Mind-map structure and layout
    nodes: List[PaperNode]  # Final nodes with positions
    layout_algorithm: str  # "force", "hierarchical", "circular"
    
    # Configuration and metadata
    task_id: str
    start_time: Optional[str]
    current_node: str
    
    # Embedding model configuration
    embedding_model_config: Dict[str, Any]
    llm_model_config: Dict[str, Any]
    
    # Error handling and recovery
    errors: Annotated[List[str], operator.add]
    warnings: Annotated[List[str], operator.add]
    
    # Final results
    mindmap_data: Dict[str, Any]  # Complete mind-map JSON for frontend
    generation_summary: str


# Helper functions for working with mind-map state
def create_initial_mindmap_state(
    seed_paper_id: int,
    k_neighbors: int = 15,
    similarity_threshold: float = 0.3,
    expansion_order: int = 1,
    max_nodes_per_order: int = 20,
    task_id: str = "",
    embedding_model_config: Dict[str, Any] = None,
    llm_model_config: Dict[str, Any] = None,
    profile_id: Optional[int] = None,
    profile_ids: Optional[List[int]] = None,
    profile_tag: Optional[str] = None,
    profile_tags: Optional[List[str]] = None
) -> MindMapState:
    """Create an initial state for the mind-map workflow."""
    return MindMapState(
        messages=[Message(role="system", content=f"Generating mind-map for paper ID {seed_paper_id}")],
        seed_paper_id=seed_paper_id,
        seed_paper=None,
        k_neighbors=k_neighbors,
        similarity_threshold=similarity_threshold,
        expansion_order=expansion_order,
        max_nodes_per_order=max_nodes_per_order,
        current_expansion_order=1,
        profile_id=profile_id,
        profile_ids=profile_ids,
        profile_tag=profile_tag,
        profile_tags=profile_tags,
        resolved_profile_ids=None,
        similar_papers=[],
        edges=[],
        all_papers={},
        papers_by_order={},
        summaries={},
        nodes=[],
        layout_algorithm="force",
        task_id=task_id,
        start_time=None,
        current_node="",
        embedding_model_config=embedding_model_config or {},
        llm_model_config=llm_model_config or {},
        errors=[],
        warnings=[],
        mindmap_data={},
        generation_summary=""
    )


def create_paper_node(paper_data: Dict[str, Any], similarity_score: float = 0.0) -> PaperNode:
    """
    Create a PaperNode from database paper data.
    
    Args:
        paper_data: Paper data from database
        similarity_score: Similarity score to seed paper
        
    Returns:
        PaperNode instance
    """
    # Handle different possible date formats from database
    date_val = paper_data.get('date') or paper_data.get('publication_date')
    if hasattr(date_val, 'isoformat'):  # Check if it's a date/datetime object
        date_str = date_val.isoformat()
    else:
        date_str = str(date_val or '')

    return PaperNode(
        id=paper_data.get('id'),
        title=paper_data.get('title', ''),
        abstract=paper_data.get('abstract', ''),
        date=date_str,
        url=paper_data.get('url', ''),
        score=paper_data.get('score', 0.0),
        rationale=paper_data.get('rationale', ''),
        similarity_score=similarity_score,
        summary=None,
        keywords=None,
        x=None,
        y=None
    )


def create_mindmap_edge(source_id: int, target_id: int, similarity_score: float) -> MindMapEdge:
    """
    Create a MindMapEdge between two papers.
    
    Args:
        source_id: Source paper ID
        target_id: Target paper ID
        similarity_score: Similarity score between papers
        
    Returns:
        MindMapEdge instance
    """
    return MindMapEdge(
        source_id=source_id,
        target_id=target_id,
        similarity_score=similarity_score,
        relationship_type="similar"
    )


def get_progress_summary(state: MindMapState) -> Dict[str, Any]:
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
        "seed_paper_id": state.get("seed_paper_id"),
        "k_neighbors": state.get("k_neighbors", 15),
        "similar_papers_found": len(state.get("similar_papers", [])),
        "summaries_generated": len(state.get("summaries", {})),
        "nodes_created": len(state.get("nodes", [])),
        "edges_created": len(state.get("edges", [])),
        "errors": len(state.get("errors", [])),
        "warnings": len(state.get("warnings", []))
    }


def has_required_data(state: MindMapState) -> bool:
    """
    Check if state has minimum required data to generate mind-map.
    
    Args:
        state: Current workflow state
        
    Returns:
        bool: True if sufficient data exists
    """
    return (
        state.get("seed_paper") is not None and
        len(state.get("similar_papers", [])) > 0
    ) 