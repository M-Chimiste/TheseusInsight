"""
Cross-Encoder Re-ranking Tool for Research Agent

Implements cross-encoder models to re-rank and score papers based on
their relevance to the research query for improved result quality.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import numpy as np

try:
    from sentence_transformers import CrossEncoder
    CROSSENCODER_AVAILABLE = True
except ImportError:
    CROSSENCODER_AVAILABLE = False
    logging.warning("sentence-transformers not available. Using fallback ranking.")

from .deduplication import PaperInfo


@dataclass
class RankedResult:
    """Result with re-ranking score."""
    paper_info: PaperInfo
    relevance_score: float
    ranking_method: str
    original_rank: int
    new_rank: int


class CrossEncoderReranker:
    """
    Tool for re-ranking search results using cross-encoder models
    to improve relevance scoring.
    """
    
    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        batch_size: int = 32,
        use_gpu: bool = False,
        fallback_scoring: bool = True
    ):
        """
        Initialize the cross-encoder re-ranker.
        
        Args:
            model_name: Name of the cross-encoder model to use
            batch_size: Batch size for processing
            use_gpu: Whether to use GPU if available
            fallback_scoring: Whether to use fallback scoring if model unavailable
        """
        self.model_name = model_name
        self.batch_size = batch_size
        self.use_gpu = use_gpu
        self.fallback_scoring = fallback_scoring
        self.logger = logging.getLogger(__name__)
        
        # Initialize cross-encoder model
        self.model = None
        self.model_available = False
        
        if CROSSENCODER_AVAILABLE:
            try:
                self.model = CrossEncoder(model_name)
                if not use_gpu:
                    self.model.to('cpu')
                self.model_available = True
                self.logger.info(f"Loaded cross-encoder model: {model_name}")
            except Exception as e:
                self.logger.error(f"Failed to load cross-encoder model: {e}")
                if not fallback_scoring:
                    raise
        else:
            self.logger.warning("sentence-transformers not available")
            if not fallback_scoring:
                raise ImportError("sentence-transformers required for cross-encoder re-ranking")
    
    def rerank_results(
        self,
        query: str,
        search_results: List[PaperInfo],
        top_k: Optional[int] = None,
        score_threshold: Optional[float] = None
    ) -> List[RankedResult]:
        """
        Re-rank search results based on relevance to the query.
        
        Args:
            query: Original research query
            search_results: List of PaperInfo objects to re-rank
            top_k: Number of top results to return (None for all)
            score_threshold: Minimum relevance score threshold
            
        Returns:
            List of RankedResult objects sorted by relevance
        """
        if not search_results:
            return []
        
        self.logger.info(f"Re-ranking {len(search_results)} results for query: {query[:100]}")
        
        # Calculate relevance scores
        if self.model_available:
            ranked_results = self._rerank_with_crossencoder(query, search_results)
        else:
            ranked_results = self._rerank_with_fallback(query, search_results)
        
        # Sort by relevance score
        ranked_results.sort(key=lambda x: x.relevance_score, reverse=True)
        
        # Update new rankings
        for i, result in enumerate(ranked_results):
            result.new_rank = i + 1
        
        # Apply filtering
        if score_threshold is not None:
            ranked_results = [r for r in ranked_results if r.relevance_score >= score_threshold]
        
        if top_k is not None:
            ranked_results = ranked_results[:top_k]
        
        self.logger.info(f"Re-ranking complete: {len(ranked_results)} results after filtering")
        return ranked_results
    
    def _rerank_with_crossencoder(
        self, 
        query: str, 
        search_results: List[PaperInfo]
    ) -> List[RankedResult]:
        """Re-rank using cross-encoder model."""
        ranked_results = []
        
        # Prepare input pairs for cross-encoder
        query_doc_pairs = []
        for result in search_results:
            # Combine title and abstract for better context
            doc_text = f"{result.title}. {result.abstract}"
            query_doc_pairs.append([query, doc_text])
        
        # Get relevance scores in batches
        try:
            all_scores = []
            for i in range(0, len(query_doc_pairs), self.batch_size):
                batch = query_doc_pairs[i:i + self.batch_size]
                batch_scores = self.model.predict(batch)
                all_scores.extend(batch_scores)
            
            # Create ranked results
            for i, (result, score) in enumerate(zip(search_results, all_scores)):
                ranked_results.append(RankedResult(
                    paper_info=result,
                    relevance_score=float(score),
                    ranking_method='cross_encoder',
                    original_rank=i + 1,
                    new_rank=0  # Will be set after sorting
                ))
        
        except Exception as e:
            self.logger.error(f"Error in cross-encoder ranking: {e}")
            # Fall back to original scoring
            return self._rerank_with_fallback(query, search_results)
        
        return ranked_results
    
    def _rerank_with_fallback(
        self, 
        query: str, 
        search_results: List[PaperInfo]
    ) -> List[RankedResult]:
        """Fallback re-ranking using simple text similarity."""
        ranked_results = []
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        for i, result in enumerate(search_results):
            # Calculate simple relevance score
            score = self._calculate_fallback_score(query_lower, query_words, result)
            
            ranked_results.append(RankedResult(
                paper_info=result,
                relevance_score=score,
                ranking_method='fallback_similarity',
                original_rank=i + 1,
                new_rank=0  # Will be set after sorting
            ))
        
        return ranked_results
    
    def _calculate_fallback_score(
        self, 
        query_lower: str, 
        query_words: set, 
        result: PaperInfo
    ) -> float:
        """Calculate fallback relevance score using simple text matching."""
        title_lower = result.title.lower()
        abstract_lower = result.abstract.lower()
        
        # Word overlap scoring
        title_words = set(title_lower.split())
        abstract_words = set(abstract_lower.split())
        
        title_overlap = len(query_words.intersection(title_words)) / len(query_words)
        abstract_overlap = len(query_words.intersection(abstract_words)) / len(query_words)
        
        # Phrase matching scoring
        title_phrase_score = self._calculate_phrase_score(query_lower, title_lower)
        abstract_phrase_score = self._calculate_phrase_score(query_lower, abstract_lower)
        
        # Weighted combination
        word_score = (title_overlap * 0.7 + abstract_overlap * 0.3)
        phrase_score = (title_phrase_score * 0.7 + abstract_phrase_score * 0.3)
        
        # Use existing paper score as a base
        base_score = (result.raw_data.get('score', 0.5)) / 10.0  # Normalize to 0-1 range
        
        # Combine scores
        final_score = (word_score * 0.4 + phrase_score * 0.4 + base_score * 0.2)
        
        return min(final_score, 1.0)  # Cap at 1.0
    
    def _calculate_phrase_score(self, query: str, text: str) -> float:
        """Calculate score based on phrase matching."""
        if not query or not text:
            return 0.0
        
        # Look for exact query phrases in text
        score = 0.0
        query_words = query.split()
        
        # Check for exact query match
        if query in text:
            score += 1.0
        
        # Check for partial phrase matches
        for i in range(len(query_words)):
            for j in range(i + 2, len(query_words) + 1):
                phrase = " ".join(query_words[i:j])
                if phrase in text:
                    phrase_length = j - i
                    score += (phrase_length / len(query_words)) * 0.5
        
        return min(score, 1.0)
    
    def batch_rerank_multiple_queries(
        self,
        query_results_pairs: List[Tuple[str, List[PaperInfo]]],
        top_k_per_query: Optional[int] = None
    ) -> List[Tuple[str, List[RankedResult]]]:
        """
        Re-rank results for multiple queries efficiently.
        
        Args:
            query_results_pairs: List of (query, search_results) pairs
            top_k_per_query: Number of top results per query
            
        Returns:
            List of (query, ranked_results) pairs
        """
        reranked_pairs = []
        
        for query, search_results in query_results_pairs:
            try:
                ranked_results = self.rerank_results(
                    query=query,
                    search_results=search_results,
                    top_k=top_k_per_query
                )
                reranked_pairs.append((query, ranked_results))
            except Exception as e:
                self.logger.error(f"Error re-ranking query '{query[:50]}': {e}")
                # Return original results with fallback scores
                fallback_results = []
                for i, result in enumerate(search_results):
                    fallback_results.append(RankedResult(
                        paper_info=result,
                        relevance_score=result.raw_data.get('score', 0.5),
                        ranking_method='error_fallback',
                        original_rank=i + 1,
                        new_rank=i + 1
                    ))
                reranked_pairs.append((query, fallback_results))
        
        return reranked_pairs
    
    def get_ranking_statistics(
        self, 
        ranked_results: List[RankedResult]
    ) -> Dict[str, Any]:
        """
        Get statistics about the re-ranking process.
        
        Args:
            ranked_results: List of RankedResult objects
            
        Returns:
            Dictionary with ranking statistics
        """
        if not ranked_results:
            return {
                'total_results': 0,
                'ranking_method': 'none',
                'score_statistics': {}
            }
        
        scores = [r.relevance_score for r in ranked_results]
        ranking_methods = [r.ranking_method for r in ranked_results]
        
        # Calculate rank changes
        rank_changes = []
        for result in ranked_results:
            change = result.original_rank - result.new_rank
            rank_changes.append(change)
        
        return {
            'total_results': len(ranked_results),
            'ranking_method': ranking_methods[0] if ranking_methods else 'unknown',
            'model_available': self.model_available,
            'score_statistics': {
                'mean': np.mean(scores),
                'median': np.median(scores),
                'std': np.std(scores),
                'min': np.min(scores),
                'max': np.max(scores)
            },
            'rank_change_statistics': {
                'mean_change': np.mean(rank_changes),
                'median_change': np.median(rank_changes),
                'max_improvement': max(rank_changes),
                'max_decline': min(rank_changes)
            }
        }
    
    def convert_to_paper_info_list(
        self, 
        ranked_results: List[RankedResult]
    ) -> List[PaperInfo]:
        """
        Convert RankedResult objects back to PaperInfo objects with updated scores.
        
        Args:
            ranked_results: List of RankedResult objects
            
        Returns:
            List of PaperInfo objects with relevance scores
        """
        paper_info_list = []
        
        for ranked_result in ranked_results:
            paper_info = ranked_result.paper_info
            # Update the score in raw_data with the relevance score
            paper_info.raw_data['relevance_score'] = ranked_result.relevance_score
            paper_info.raw_data['ranking_method'] = ranked_result.ranking_method
            paper_info.raw_data['original_rank'] = ranked_result.original_rank
            paper_info.raw_data['new_rank'] = ranked_result.new_rank
            
            paper_info_list.append(paper_info)
        
        return paper_info_list 