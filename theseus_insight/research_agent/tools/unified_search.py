"""
Unified Search Tool for Research Agent

Bridges the string-based search tools with deduplication and ranking
to provide a comprehensive search interface for the research agent.
"""

import logging
import re
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass

from .local_search import BaseSearchTool, LocalSearchTool
from .external_search import ExternalSearchTool
from .deduplication import SourceDeduplicator, PaperInfo, DuplicateGroup
from .reranking import CrossEncoderReranker, RankedResult


@dataclass
class SearchConfig:
    """Configuration for unified search operations."""
    use_local: bool = True
    use_external: bool = True
    local_limit: int = 15
    external_limit: int = 15
    deduplicate: bool = True
    rerank: bool = True
    similarity_threshold: float = 0.2
    enable_pdf_download: bool = True


class UnifiedSearchTool:
    """
    Unified search tool that combines local and external search capabilities
    with deduplication and re-ranking for optimal research agent performance.
    """
    
    def __init__(
        self,
        local_search_tool: LocalSearchTool,
        external_search_tool: Optional[ExternalSearchTool] = None,
        deduplicator: Optional[SourceDeduplicator] = None,
        reranker: Optional[CrossEncoderReranker] = None
    ):
        """
        Initialize unified search tool.
        
        Args:
            local_search_tool: Local search tool instance
            external_search_tool: External search tool instance (optional)
            deduplicator: Source deduplicator instance (optional)
            reranker: Cross-encoder reranker instance (optional)
        """
        self.local_search = local_search_tool
        self.external_search = external_search_tool or ExternalSearchTool()
        self.deduplicator = deduplicator or SourceDeduplicator()
        self.reranker = reranker or CrossEncoderReranker(fallback_scoring=True)
        self.logger = logging.getLogger(__name__)
    
    def comprehensive_search(
        self,
        query: str,
        config: SearchConfig = None,
        return_raw_results: bool = False
    ) -> Union[str, Dict[str, Any]]:
        """
        Perform comprehensive search across local and external sources.
        
        Args:
            query: Search query string
            config: Search configuration options
            return_raw_results: Whether to return structured data instead of formatted string
            
        Returns:
            Formatted search results string or structured data dictionary
        """
        if config is None:
            config = SearchConfig()
        
        self.logger.info(f"Starting comprehensive search for: {query}")
        
        # Step 1: Gather sources from different search tools
        all_papers = []
        search_summary = []
        
        if config.use_local:
            local_papers = self._search_local_and_extract(query, config.local_limit)
            all_papers.extend(local_papers)
            search_summary.append(f"Local: {len(local_papers)} papers")
        
        if config.use_external:
            external_papers = self._search_external_and_extract(query, config.external_limit)
            all_papers.extend(external_papers)
            search_summary.append(f"External: {len(external_papers)} papers")
        
        if not all_papers:
            return "No papers found for the given query in any source."
        
        self.logger.info(f"Total papers before processing: {len(all_papers)}")
        
        # Step 2: Deduplication
        duplicate_groups = []
        if config.deduplicate and len(all_papers) > 1:
            all_papers, duplicate_groups = self.deduplicator.deduplicate_sources(all_papers)
            duplicates_removed = sum(len(group.duplicates) for group in duplicate_groups)
            search_summary.append(f"Deduplication: {duplicates_removed} duplicates removed")
            self.logger.info(f"After deduplication: {len(all_papers)} papers")
        
        # Step 3: Re-ranking
        ranked_results = []
        if config.rerank and all_papers:
            ranked_results = self.reranker.rerank_results(query, all_papers)
            search_summary.append(f"Re-ranking: {len(ranked_results)} papers ranked")
            self.logger.info(f"After re-ranking: {len(ranked_results)} papers")
        else:
            # Convert to RankedResult format without re-ranking
            for i, paper in enumerate(all_papers):
                score = paper.raw_data.get('score', 0.5)
                ranked_results.append(RankedResult(
                    paper_info=paper,
                    relevance_score=score,
                    ranking_method='original_score',
                    original_rank=i + 1,
                    new_rank=i + 1
                ))
        
        # Step 4: Format results
        if return_raw_results:
            return {
                'query': query,
                'ranked_results': ranked_results,
                'duplicate_groups': duplicate_groups,
                'search_summary': search_summary,
                'config': config
            }
        else:
            return self._format_comprehensive_results(
                query, ranked_results, duplicate_groups, search_summary, config
            )
    
    def _search_local_and_extract(self, query: str, limit: int) -> List[PaperInfo]:
        """Search local database and extract structured paper info."""
        try:
            # Use the raw search method to get structured data
            raw_results = self.local_search.search_local_only(query, limit)
            papers = []
            
            for result in raw_results:
                paper = PaperInfo(
                    paper_id=str(result.get('id', '')),
                    title=result.get('title', ''),
                    abstract=result.get('abstract', ''),
                    url=result.get('url', ''),
                    source='local',
                    raw_data=result
                )
                papers.append(paper)
            
            return papers
            
        except Exception as e:
            self.logger.error(f"Error in local search: {e}")
            return []
    
    def _search_external_and_extract(self, query: str, limit: int) -> List[PaperInfo]:
        """Search external sources and extract structured paper info."""
        try:
            # Use the search_and_rank method to get structured data
            raw_results = self.external_search.search_and_rank(query, limit)
            papers = []
            
            for result in raw_results:
                paper = PaperInfo(
                    paper_id=result.get('url', ''),  # Use URL as ID for external papers
                    title=result.get('title', ''),
                    abstract=result.get('abstract', ''),
                    url=result.get('url', ''),
                    source='external',
                    raw_data=result
                )
                papers.append(paper)
            
            return papers
            
        except Exception as e:
            self.logger.error(f"Error in external search: {e}")
            return []
    
    def _format_comprehensive_results(
        self,
        query: str,
        ranked_results: List[RankedResult],
        duplicate_groups: List[DuplicateGroup],
        search_summary: List[str],
        config: SearchConfig
    ) -> str:
        """Format comprehensive search results for agent consumption."""
        result_lines = [
            f"COMPREHENSIVE SEARCH RESULTS for '{query}':",
            f"Search Summary: {' | '.join(search_summary)}",
            ""
        ]
        
        if not ranked_results:
            result_lines.append("No papers found matching the query.")
            return "\n".join(result_lines)
        
        # Format top results
        result_lines.append(f"TOP RANKED PAPERS ({len(ranked_results)} total):")
        result_lines.append("")
        
        for i, ranked_result in enumerate(ranked_results[:10], 1):  # Show top 10
            paper = ranked_result.paper_info
            result_lines.extend([
                f"RANKED PAPER {i}:",
                f"  Source: {paper.source.upper()}",
                f"  ID: {paper.paper_id}",
                f"  Title: {paper.title}",
                f"  Relevance Score: {ranked_result.relevance_score:.3f} ({ranked_result.ranking_method})",
                f"  URL: {paper.url}" if paper.url else "  URL: Not available"
            ])
            
            # Add abstract preview
            if paper.abstract:
                if len(paper.abstract) > 200:
                    abstract_preview = paper.abstract[:200] + "..."
                else:
                    abstract_preview = paper.abstract
                result_lines.append(f"  Abstract: {abstract_preview}")
            
            # Add availability info
            if paper.source == 'local':
                has_full_text = bool(paper.raw_data.get('text'))
                if has_full_text:
                    result_lines.append(f"  Content: Full text available")
                elif paper.url and config.enable_pdf_download:
                    result_lines.append(f"  Content: PDF can be downloaded and processed")
                else:
                    result_lines.append(f"  Content: Abstract only")
            else:  # external
                result_lines.append(f"  Content: PDF available for download")
            
            result_lines.append("")
        
        # Add deduplication summary if applicable
        if duplicate_groups:
            total_duplicates = sum(len(group.duplicates) for group in duplicate_groups)
            result_lines.extend([
                f"DEDUPLICATION SUMMARY:",
                f"Found {len(duplicate_groups)} groups of duplicates, removed {total_duplicates} duplicate papers",
                ""
            ])
        
        # Add usage instructions
        result_lines.extend([
            "USAGE INSTRUCTIONS:",
            "- Use retrieve_full_text(paper_id) to get full paper content",
            "- Local papers: Use the ID number for retrieval",
            "- External papers: Use the full URL for retrieval",
            ""
        ])
        
        return "\n".join(result_lines)
    
    def get_paper_full_text(self, paper_identifier: str, source_hint: str = None) -> str:
        """
        Get full text for a paper using the appropriate search tool.
        
        Args:
            paper_identifier: Paper ID or URL
            source_hint: Hint about the source ('local' or 'external')
            
        Returns:
            Full text content or error message
        """
        try:
            # Determine source if not provided
            if source_hint is None:
                if paper_identifier.startswith(('http://', 'https://')):
                    source_hint = 'external'
                else:
                    source_hint = 'local'
            
            if source_hint == 'local':
                return self.local_search.retrieve_full_text(paper_identifier)
            else:
                return self.external_search.retrieve_full_text(paper_identifier)
                
        except Exception as e:
            return f"Error retrieving full text for {paper_identifier}: {str(e)}"
    
    def get_search_statistics(self) -> Dict[str, Any]:
        """Get comprehensive statistics about search capabilities."""
        stats = {
            'deduplication_available': self.deduplicator is not None,
            'reranking_available': self.reranker is not None
        }
        
        # Safely get local search stats
        try:
            if hasattr(self.local_search, 'get_search_stats'):
                stats['local_search_stats'] = self.local_search.get_search_stats()
            else:
                stats['local_search_stats'] = {'available': True}
        except Exception as e:
            stats['local_search_stats'] = {'error': str(e)}
        
        # Safely get external search capabilities
        try:
            if self.external_search and hasattr(self.external_search, 'get_search_capabilities'):
                stats['external_search_capabilities'] = self.external_search.get_search_capabilities()
            else:
                stats['external_search_capabilities'] = {'available': self.external_search is not None}
        except Exception as e:
            stats['external_search_capabilities'] = {'error': str(e)}
        
        # Safely get reranking model availability
        try:
            if hasattr(self.reranker, 'model_available'):
                stats['reranking_model_available'] = self.reranker.model_available
        except Exception as e:
            stats['reranking_model_error'] = str(e)
        
        return stats 