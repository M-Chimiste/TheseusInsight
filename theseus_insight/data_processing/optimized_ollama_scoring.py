"""
Optimized Ollama scoring pipeline with caching and smart filtering.

This module implements optimizations for sequential LLM calls since
Ollama cannot be parallelized on local compute.
"""

import json
import time
import hashlib
from typing import List, Dict, Optional, Tuple, Any
from collections import defaultdict
import numpy as np
from tqdm import tqdm
import json_repair

from theseus_insight.prompt import research_prompt, RESEARCH_INTERESTS_SYSTEM_PROMPT
from theseus_insight.data_access import PaperRepository, ProfileScoreRepository
from theseus_insight.data_access.profiles import ProfileRepository
from theseus_insight.inference import SentenceTransformerInference


class OptimizedOllamaScorer:
    """
    Optimized Ollama scoring with smart caching and filtering.
    
    Key optimizations:
    - Smart caching for similar papers
    - Pre-filter papers using embeddings similarity
    - Batch context preparation
    - Optimized prompts for faster inference
    - Progress checkpointing
    """
    
    def __init__(
        self,
        judge_inference,
        embedding_model: Optional[SentenceTransformerInference] = None,
        similarity_threshold: float = 0.9,
        cache_size: int = 1000,
        checkpoint_interval: int = 100,
        verbose: bool = True
    ):
        """
        Initialize the optimized scorer.
        
        Args:
            judge_inference: The Ollama inference model
            embedding_model: Optional embedding model for similarity filtering
            similarity_threshold: Threshold for considering papers similar (for caching)
            cache_size: Maximum number of cached responses
            checkpoint_interval: How often to checkpoint progress
            verbose: Whether to show progress information
        """
        self.judge_inference = judge_inference
        self.embedding_model = embedding_model
        self.similarity_threshold = similarity_threshold
        self.cache_size = cache_size
        self.checkpoint_interval = checkpoint_interval
        self.verbose = verbose
        
        # Response cache: hash(abstract + interests) -> response
        self.response_cache = {}
        self.cache_hits = 0
        self.cache_misses = 0
        
        # Embedding cache for abstracts
        self.embedding_cache = {}
        
        # Checkpoint data
        self.last_checkpoint = 0
        
    def score_papers_for_profile(
        self,
        profile_id: int,
        profile_name: str,
        research_interests: str,
        papers: List[Dict],
        overwrite_existing: bool = False,
        use_prefiltering: bool = True,
        prefilter_threshold: float = 0.3
    ) -> Tuple[int, int, Dict[str, Any]]:
        """
        Score papers for a specific profile with optimizations.
        
        Args:
            profile_id: ID of the research profile
            profile_name: Name of the profile
            research_interests: Research interests description
            papers: List of papers to score
            overwrite_existing: Whether to overwrite existing scores
            use_prefiltering: Whether to use embedding-based prefiltering
            prefilter_threshold: Minimum similarity to consider scoring
            
        Returns:
            Tuple of (scored_count, failed_count, statistics)
        """
        start_time = time.time()
        stats = {
            'total_papers': len(papers),
            'prefiltered_out': 0,
            'cache_hits': 0,
            'ollama_calls': 0,
            'errors': 0
        }
        
        # Filter papers that already have scores if not overwriting
        if not overwrite_existing:
            papers_to_score = []
            for paper in papers:
                if not ProfileScoreRepository.has_score_for_profile(paper['id'], profile_id):
                    papers_to_score.append(paper)
            
            if self.verbose and len(papers_to_score) != len(papers):
                skipped = len(papers) - len(papers_to_score)
                print(f"📝 Skipping {skipped} papers that already have scores for this profile")
        else:
            papers_to_score = papers
        
        if not papers_to_score:
            if self.verbose:
                print(f"✅ All papers already scored for profile {profile_name}")
            return 0, 0, stats
        
        # Pre-filter using embeddings if requested
        if use_prefiltering and self.embedding_model:
            papers_to_score = self._prefilter_papers(
                papers_to_score,
                research_interests,
                prefilter_threshold,
                stats
            )
        
        if self.verbose:
            print(f"🎯 Scoring {len(papers_to_score)} papers for profile {profile_name}")
            if use_prefiltering and self.embedding_model:
                print(f"🔽 Pre-filtered out {stats['prefiltered_out']} low-relevance papers")
        
        # Score papers with optimizations
        scored_count = 0
        failed_count = 0
        scores_batch = []
        
        with tqdm(papers_to_score, desc=f"Scoring {profile_name}", disable=not self.verbose) as pbar:
            for idx, paper in enumerate(pbar):
                # Score the paper (with caching)
                score_data = self._score_paper_cached(
                    paper,
                    research_interests,
                    stats
                )
                
                if score_data:
                    scores_batch.append({
                        'paper_id': paper['id'],
                        'profile_id': profile_id,
                        'score': score_data['score'],
                        'related': score_data['related'],
                        'rationale': score_data['rationale']
                    })
                    scored_count += 1
                else:
                    failed_count += 1
                    stats['errors'] += 1
                
                # Batch write to database
                if len(scores_batch) >= 100:
                    self._flush_scores(scores_batch)
                    scores_batch = []
                
                # Checkpoint progress
                if idx > 0 and idx % self.checkpoint_interval == 0:
                    self._checkpoint_progress(idx, scored_count, failed_count, stats)
                
                # Update progress bar with cache statistics
                if self.cache_hits + self.cache_misses > 0:
                    cache_rate = self.cache_hits / (self.cache_hits + self.cache_misses) * 100
                    pbar.set_postfix({'cache_hit_rate': f'{cache_rate:.1f}%'})
        
        # Flush remaining scores
        if scores_batch:
            self._flush_scores(scores_batch)
        
        # Final statistics
        duration = time.time() - start_time
        stats['duration'] = duration
        stats['papers_per_second'] = scored_count / duration if duration > 0 else 0
        stats['cache_hits'] = self.cache_hits
        stats['cache_hit_rate'] = (
            self.cache_hits / (self.cache_hits + self.cache_misses) * 100
            if (self.cache_hits + self.cache_misses) > 0 else 0
        )
        
        if self.verbose:
            print(f"\n✅ Scoring complete for {profile_name}")
            print(f"📊 Scored: {scored_count}, Failed: {failed_count}")
            print(f"⚡ Rate: {stats['papers_per_second']:.1f} papers/second")
            print(f"💾 Cache hit rate: {stats['cache_hit_rate']:.1f}%")
            print(f"🔧 Ollama calls: {stats['ollama_calls']}")
        
        return scored_count, failed_count, stats
    
    def _prefilter_papers(
        self,
        papers: List[Dict],
        research_interests: str,
        threshold: float,
        stats: Dict
    ) -> List[Dict]:
        """
        Pre-filter papers using embedding similarity.
        """
        if not self.embedding_model:
            return papers
        
        if self.verbose:
            print("🔍 Pre-filtering papers using embeddings...")
        
        # Get research interests embedding
        research_embedding = self.embedding_model.invoke(research_interests)
        if hasattr(research_embedding, 'cpu'):
            research_embedding = research_embedding.cpu().numpy()
        
        filtered_papers = []
        
        for paper in tqdm(papers, desc="Pre-filtering", disable=not self.verbose):
            # Skip if no embedding
            if not paper.get('embedding'):
                filtered_papers.append(paper)
                continue
            
            # Calculate similarity
            paper_embedding = np.array(paper['embedding'])
            similarity = self._cosine_similarity(paper_embedding, research_embedding)
            
            if similarity >= threshold:
                filtered_papers.append(paper)
            else:
                stats['prefiltered_out'] += 1
        
        return filtered_papers
    
    def _score_paper_cached(
        self,
        paper: Dict,
        research_interests: str,
        stats: Dict
    ) -> Optional[Dict]:
        """
        Score a paper with caching support.
        """
        # Generate cache key
        cache_key = self._generate_cache_key(paper['abstract'], research_interests)
        
        # Check cache
        if cache_key in self.response_cache:
            self.cache_hits += 1
            stats['cache_hits'] += 1
            return self.response_cache[cache_key]
        
        self.cache_misses += 1
        
        # Check for similar papers in cache
        similar_response = self._find_similar_in_cache(paper, research_interests)
        if similar_response:
            self.cache_hits += 1
            stats['cache_hits'] += 1
            # Add to cache for exact match next time
            self.response_cache[cache_key] = similar_response
            return similar_response
        
        # Score using Ollama
        stats['ollama_calls'] += 1
        response = self._score_with_ollama(paper, research_interests)
        
        if response:
            # Add to cache
            self._add_to_cache(cache_key, response)
        
        return response
    
    def _score_with_ollama(self, paper: Dict, research_interests: str) -> Optional[Dict]:
        """
        Score a paper using Ollama.
        """
        try:
            # Use optimized prompt
            messages = [
                {"role": "user", "content": self._optimized_prompt(research_interests, paper['abstract'])}
            ]
            
            # Call Ollama
            if getattr(self.judge_inference, "provider", "") == "ollama":
                response = self.judge_inference.invoke(
                    messages=messages,
                    system_prompt=RESEARCH_INTERESTS_SYSTEM_PROMPT,
                    schema=None
                )
            else:
                response = self.judge_inference.invoke(
                    messages=messages,
                    system_prompt=RESEARCH_INTERESTS_SYSTEM_PROMPT
                )
            
            # Parse response
            try:
                response_json = json_repair.loads(response)
            except Exception as e:
                if self.verbose:
                    print(f"⚠️ JSON parsing failed: {e}")
                return None
            
            # Validate and format response
            if not all(key in response_json for key in ['score', 'related', 'rationale']):
                return None
            
            return {
                'score': max(1, min(10, int(response_json['score']))),
                'related': bool(response_json['related']),
                'rationale': str(response_json['rationale'])
            }
            
        except Exception as e:
            if self.verbose:
                print(f"❌ Error scoring paper: {e}")
            return None
    
    def _optimized_prompt(self, research_interests: str, abstract: str) -> str:
        """
        Generate an optimized prompt for faster inference.
        Shorter prompts = faster responses.
        """
        # Truncate abstract if too long (keep most relevant parts)
        if len(abstract) > 1000:
            abstract = abstract[:1000] + "..."
        
        # Use the standard research_prompt but with truncated abstract
        return research_prompt(research_interests, abstract)
    
    def _find_similar_in_cache(
        self,
        paper: Dict,
        research_interests: str
    ) -> Optional[Dict]:
        """
        Find similar papers in cache using embeddings.
        """
        if not self.embedding_model or not paper.get('embedding'):
            return None
        
        paper_embedding = np.array(paper['embedding'])
        
        # Check each cached response
        for cache_key, cached_response in list(self.response_cache.items())[:100]:  # Check recent 100
            # Skip if different research interests
            if research_interests not in cache_key:
                continue
            
            # Get cached paper's embedding if available
            if cache_key in self.embedding_cache:
                cached_embedding = self.embedding_cache[cache_key]
                similarity = self._cosine_similarity(paper_embedding, cached_embedding)
                
                if similarity >= self.similarity_threshold:
                    return cached_response
        
        return None
    
    def _add_to_cache(self, cache_key: str, response: Dict):
        """
        Add response to cache with size limit.
        """
        # Evict oldest if cache is full
        if len(self.response_cache) >= self.cache_size:
            # Remove first (oldest) item
            oldest_key = next(iter(self.response_cache))
            del self.response_cache[oldest_key]
            if oldest_key in self.embedding_cache:
                del self.embedding_cache[oldest_key]
        
        self.response_cache[cache_key] = response
    
    def _generate_cache_key(self, abstract: str, interests: str) -> str:
        """
        Generate a cache key for abstract + interests combination.
        """
        content = f"{abstract}||{interests}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _flush_scores(self, scores_batch: List[Dict]):
        """
        Flush batch of scores to database.
        """
        if not scores_batch:
            return
        
        try:
            ProfileScoreRepository.bulk_create_or_update_scores(scores_batch)
        except Exception as e:
            if self.verbose:
                print(f"❌ Error flushing scores: {e}")
            # Fall back to individual inserts
            for score in scores_batch:
                try:
                    ProfileScoreRepository.create_or_update_score(
                        paper_id=score['paper_id'],
                        profile_id=score['profile_id'],
                        score=score['score'],
                        related=score['related'],
                        rationale=score['rationale']
                    )
                except Exception as e2:
                    if self.verbose:
                        print(f"❌ Error saving score for paper {score['paper_id']}: {e2}")
    
    def _checkpoint_progress(
        self,
        papers_processed: int,
        scored_count: int,
        failed_count: int,
        stats: Dict
    ):
        """
        Checkpoint progress for resumability.
        """
        if self.verbose:
            cache_rate = stats.get('cache_hit_rate', 0)
            print(f"\n✅ Checkpoint: {papers_processed} papers processed")
            print(f"   Scored: {scored_count}, Failed: {failed_count}")
            print(f"   Cache hit rate: {cache_rate:.1f}%")
            print(f"   Ollama calls: {stats['ollama_calls']}")
    
    @staticmethod
    def _cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        return float(dot_product / (norm1 * norm2)) if norm1 > 0 and norm2 > 0 else 0.0


def optimize_ollama_parameters(
    judge_inference,
    sample_papers: List[Dict],
    research_interests: str,
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Find optimal parameters for Ollama scoring.
    
    Args:
        judge_inference: The Ollama inference model
        sample_papers: Sample papers to test with
        research_interests: Research interests for testing
        verbose: Whether to show results
        
    Returns:
        Dictionary with optimal parameters
    """
    if verbose:
        print("🔍 Finding optimal Ollama parameters...")
    
    # Test different prompt lengths
    abstract_lengths = [500, 750, 1000, 1500, 2000]
    best_length = 1000
    best_time = float('inf')
    
    for length in abstract_lengths:
        if verbose:
            print(f"  Testing abstract length: {length} chars")
        
        start_time = time.time()
        
        # Test scoring with truncated abstracts
        for paper in sample_papers[:5]:
            truncated_abstract = paper['abstract'][:length]
            if len(paper['abstract']) > length:
                truncated_abstract += "..."
            
            messages = [
                {"role": "user", "content": research_prompt(research_interests, truncated_abstract)}
            ]
            
            try:
                if getattr(judge_inference, "provider", "") == "ollama":
                    response = judge_inference.invoke(
                        messages=messages,
                        system_prompt=RESEARCH_INTERESTS_SYSTEM_PROMPT,
                        schema=None
                    )
                else:
                    response = judge_inference.invoke(
                        messages=messages,
                        system_prompt=RESEARCH_INTERESTS_SYSTEM_PROMPT
                    )
            except Exception as e:
                if verbose:
                    print(f"    Error: {e}")
                continue
        
        duration = time.time() - start_time
        avg_time = duration / min(5, len(sample_papers))
        
        if verbose:
            print(f"    Average time: {avg_time:.2f}s per paper")
        
        if avg_time < best_time:
            best_time = avg_time
            best_length = length
    
    if verbose:
        print(f"✅ Optimal abstract length: {best_length} chars")
        print(f"   Average scoring time: {best_time:.2f}s per paper")
    
    return {
        'optimal_abstract_length': best_length,
        'average_scoring_time': best_time
    }