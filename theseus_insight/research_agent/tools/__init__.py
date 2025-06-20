"""
Research Agent Tools Module

Contains all tools used by the research agent for:
- Local database search with PDF processing
- External ArXiv search with enhanced capabilities  
- Source deduplication using SimHash/MinHash
- Cross-encoder re-ranking system
"""

from .local_search import LocalSearchTool, BaseSearchTool
from .external_search import ExternalSearchTool
from .deduplication import SourceDeduplicator, PaperInfo, DuplicateGroup
from .reranking import CrossEncoderReranker, RankedResult
from .unified_search import UnifiedSearchTool, SearchConfig

__all__ = [
    "BaseSearchTool",
    "LocalSearchTool",
    "ExternalSearchTool", 
    "SourceDeduplicator",
    "CrossEncoderReranker",
    "PaperInfo",
    "DuplicateGroup", 
    "RankedResult",
    "UnifiedSearchTool",
    "SearchConfig"
] 