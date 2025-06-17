"""
Unified Retriever Node for Research Agent

Uses the UnifiedSearchTool to search both local and external sources,
with automatic deduplication and re-ranking for optimal results.
"""

import logging
from typing import Dict, Any, List

from ..state import OverallState, Message
from ..tools import UnifiedSearchTool, SearchConfig


class RetrieverUnifiedNode:
    """
    LangGraph node that performs comprehensive search across all available sources.
    
    This node uses the UnifiedSearchTool to search local database and external
    sources (ArXiv), with automatic deduplication and re-ranking to provide
    the best possible results for each sub-query.
    """
    
    def __init__(
        self, 
        unified_search_tool: UnifiedSearchTool,
        default_config: SearchConfig = None
    ):
        """
        Initialize the unified retriever node.
        
        Args:
            unified_search_tool: Configured UnifiedSearchTool instance
            default_config: Default search configuration
        """
        self.search_tool = unified_search_tool
        self.default_config = default_config or SearchConfig(
            use_local=True,
            use_external=True,
            local_limit=15,
            external_limit=10,
            deduplicate=True,
            rerank=True,
            similarity_threshold=0.3,
            enable_pdf_download=True
        )
        self.logger = logging.getLogger(__name__)
    
    def __call__(self, state: OverallState) -> Dict[str, Any]:
        """
        Execute unified search on all sub-queries.
        
        Args:
            state: Current research agent state
            
        Returns:
            Updated state with gathered sources
        """
        self.logger.info("Starting unified retrieval")
        
        try:
            # Get sub-queries from state
            sub_queries = state.get("sub_queries", [])
            if not sub_queries:
                self.logger.warning("No sub-queries found, cannot perform search")
                return {
                    "sources_gathered": [],
                    "messages": [Message(role="assistant", content="⚠️ No sub-queries available for search. Please run query planning first.")]
                }
            
            # Perform search for each sub-query
            all_sources = []
            search_summaries = []
            
            for i, query in enumerate(sub_queries, 1):
                self.logger.info(f"Searching for sub-query {i}/{len(sub_queries)}: {query[:100]}")
                
                try:
                    # Perform comprehensive search
                    search_results = self.search_tool.comprehensive_search(
                        query=query,
                        config=self.default_config,
                        return_raw_results=True
                    )
                    
                    if isinstance(search_results, dict) and 'ranked_results' in search_results:
                        # Extract sources from ranked results
                        query_sources = []
                        for ranked_result in search_results['ranked_results']:
                            source_data = {
                                'query': query,
                                'query_index': i,
                                'paper_info': ranked_result.paper_info,
                                'relevance_score': ranked_result.relevance_score,
                                'ranking_method': ranked_result.ranking_method,
                                'source_type': ranked_result.paper_info.source
                            }
                            query_sources.append(source_data)
                        
                        all_sources.extend(query_sources)
                        
                        # Create summary for this query
                        summary = f"Query {i}: Found {len(query_sources)} sources ({search_results.get('search_summary', [])})"
                        search_summaries.append(summary)
                        
                        self.logger.info(f"Sub-query {i} completed: {len(query_sources)} sources found")
                    
                    else:
                        # Handle string response (fallback)
                        self.logger.warning(f"Received string response for sub-query {i}, parsing manually")
                        search_summaries.append(f"Query {i}: Search completed (string response)")
                
                except Exception as e:
                    self.logger.error(f"Error searching sub-query {i}: {e}")
                    search_summaries.append(f"Query {i}: Search failed - {str(e)}")
            
            # Create retrieval summary
            retrieval_summary = self._create_retrieval_summary(
                sub_queries, all_sources, search_summaries
            )
            
            self.logger.info(f"Unified retrieval complete: {len(all_sources)} total sources gathered")
            
            return {
                "sources_gathered": all_sources,
                "messages": [Message(role="assistant", content=retrieval_summary)]
            }
            
        except Exception as e:
            self.logger.error(f"Error in unified retrieval: {e}")
            return {
                "sources_gathered": [],
                "messages": [Message(role="assistant", content=f"🚨 Retrieval error: {str(e)}. Please try again or adjust search parameters.")]
            }
    
    def _create_retrieval_summary(
        self, 
        sub_queries: List[str], 
        all_sources: List[Dict[str, Any]], 
        search_summaries: List[str]
    ) -> str:
        """
        Create a summary of the retrieval process.
        
        Args:
            sub_queries: List of sub-queries that were searched
            all_sources: All sources gathered from searches
            search_summaries: Summary of each individual search
            
        Returns:
            Formatted retrieval summary
        """
        # Count sources by type
        local_sources = sum(1 for s in all_sources if s.get('source_type') == 'local')
        external_sources = sum(1 for s in all_sources if s.get('source_type') == 'external')
        
        # Calculate average relevance score
        relevance_scores = [s.get('relevance_score', 0) for s in all_sources]
        avg_relevance = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0
        
        summary_lines = [
            "📚 UNIFIED RETRIEVAL COMPLETE",
            "",
            f"Searched {len(sub_queries)} sub-queries across multiple sources:",
            ""
        ]
        
        # Add search summaries
        for summary in search_summaries:
            summary_lines.append(f"  • {summary}")
        
        summary_lines.extend([
            "",
            "📊 RETRIEVAL STATISTICS:",
            f"  • Total Sources Found: {len(all_sources)}",
            f"  • Local Database: {local_sources} papers",
            f"  • External (ArXiv): {external_sources} papers",
            f"  • Average Relevance Score: {avg_relevance:.3f}",
            ""
        ])
        
        if all_sources:
            # Show top sources
            summary_lines.append("🔝 TOP SOURCES PREVIEW:")
            
            # Sort by relevance score and show top 3
            sorted_sources = sorted(all_sources, key=lambda x: x.get('relevance_score', 0), reverse=True)
            for i, source in enumerate(sorted_sources[:3], 1):
                paper_info = source.get('paper_info')
                if paper_info:
                    title = paper_info.title[:80] + "..." if len(paper_info.title) > 80 else paper_info.title
                    score = source.get('relevance_score', 0)
                    source_type = source.get('source_type', 'unknown').upper()
                    summary_lines.append(f"  {i}. [{source_type}] {title} (Score: {score:.3f})")
            
            summary_lines.extend([
                "",
                "Next: Evidence selection will evaluate these sources for quality and relevance.",
                ""
            ])
        else:
            summary_lines.extend([
                "⚠️ No sources found. Consider:",
                "  • Broadening search terms",
                "  • Checking spelling and terminology", 
                "  • Trying different query formulations",
                ""
            ])
        
        return "\n".join(summary_lines)
    
    def update_search_config(self, **config_updates) -> None:
        """
        Update the default search configuration.
        
        Args:
            **config_updates: Configuration parameters to update
        """
        # Create new config with updates
        current_config = self.default_config
        new_config_dict = {
            'use_local': config_updates.get('use_local', current_config.use_local),
            'use_external': config_updates.get('use_external', current_config.use_external),
            'local_limit': config_updates.get('local_limit', current_config.local_limit),
            'external_limit': config_updates.get('external_limit', current_config.external_limit),
            'deduplicate': config_updates.get('deduplicate', current_config.deduplicate),
            'rerank': config_updates.get('rerank', current_config.rerank),
            'similarity_threshold': config_updates.get('similarity_threshold', current_config.similarity_threshold),
            'enable_pdf_download': config_updates.get('enable_pdf_download', current_config.enable_pdf_download)
        }
        
        self.default_config = SearchConfig(**new_config_dict)
        self.logger.info(f"Updated search configuration: {config_updates}")
    
    def get_node_info(self) -> Dict[str, Any]:
        """Get information about this node for monitoring and debugging."""
        search_stats = self.search_tool.get_search_statistics()
        
        return {
            "node_type": "retriever_unified",
            "search_config": {
                "use_local": self.default_config.use_local,
                "use_external": self.default_config.use_external,
                "local_limit": self.default_config.local_limit,
                "external_limit": self.default_config.external_limit,
                "deduplicate": self.default_config.deduplicate,
                "rerank": self.default_config.rerank
            },
            "search_capabilities": search_stats,
            "description": "Unified search across local and external sources with deduplication and ranking"
        } 