"""
Source Deduplication Tool for Research Agent

Implements SimHash and MinHash algorithms to identify and remove
duplicate papers from search results across local and external sources.
"""

import logging
import hashlib
import re
from typing import List, Dict, Any, Set, Tuple
from dataclasses import dataclass
from collections import defaultdict

try:
    from simhash import Simhash
    SIMHASH_AVAILABLE = True
except ImportError:
    SIMHASH_AVAILABLE = False
    logging.warning("simhash library not available. Using fallback deduplication.")

from typing import List, Dict, Any, Set, Tuple
from dataclasses import dataclass


@dataclass
class DuplicateGroup:
    """Group of papers identified as duplicates."""
    representative: Dict[str, Any]
    duplicates: List[Dict[str, Any]]
    similarity_score: float
    dedup_method: str


@dataclass
class PaperInfo:
    """Simplified paper information for deduplication."""
    paper_id: str
    title: str
    abstract: str
    url: str
    source: str  # 'local' or 'external'
    raw_data: Dict[str, Any]  # Original data structure
    
    def __hash__(self):
        """Make PaperInfo hashable by using paper_id and URL."""
        return hash((self.paper_id, self.url))
    
    def __eq__(self, other):
        """Define equality based on paper_id and URL."""
        if not isinstance(other, PaperInfo):
            return False
        return self.paper_id == other.paper_id and self.url == other.url


class SourceDeduplicator:
    """
    Tool for deduplicating paper sources using multiple algorithms.
    
    Implements SimHash for near-duplicate detection and various fallback
    methods for title/abstract similarity.
    """
    
    def __init__(
        self, 
        title_similarity_threshold: float = 0.8,
        abstract_similarity_threshold: float = 0.7,
        simhash_threshold: int = 10,  # Hamming distance threshold
        use_simhash: bool = True
    ):
        """
        Initialize the deduplication tool.
        
        Args:
            title_similarity_threshold: Threshold for title similarity (0-1)
            abstract_similarity_threshold: Threshold for abstract similarity (0-1)
            simhash_threshold: Hamming distance threshold for SimHash
            use_simhash: Whether to use SimHash (requires simhash library)
        """
        self.title_threshold = title_similarity_threshold
        self.abstract_threshold = abstract_similarity_threshold
        self.simhash_threshold = simhash_threshold
        self.use_simhash = use_simhash and SIMHASH_AVAILABLE
        self.logger = logging.getLogger(__name__)
        
        if not SIMHASH_AVAILABLE:
            self.logger.warning("SimHash not available, using fallback methods only")
    
    def deduplicate_sources(
        self, 
        sources: List[PaperInfo],
        preserve_highest_score: bool = True
    ) -> Tuple[List[PaperInfo], List[DuplicateGroup]]:
        """
        Remove duplicate sources from a list of search results.
        
        Args:
            sources: List of PaperInfo objects to deduplicate
            preserve_highest_score: Whether to keep the highest-scoring paper from each group
            
        Returns:
            Tuple of (deduplicated_sources, duplicate_groups)
        """
        if not sources:
            return [], []
        
        self.logger.info(f"Deduplicating {len(sources)} sources")
        
        # Find duplicate groups using different methods
        duplicate_groups = []
        
        if self.use_simhash:
            simhash_groups = self._find_simhash_duplicates(sources)
            duplicate_groups.extend(simhash_groups)
        
        # Find remaining duplicates using title/abstract similarity
        remaining_sources = self._get_remaining_sources(sources, duplicate_groups)
        title_groups = self._find_title_duplicates(remaining_sources)
        duplicate_groups.extend(title_groups)
        
        # Find URL duplicates
        remaining_sources = self._get_remaining_sources(sources, duplicate_groups)
        url_groups = self._find_url_duplicates(remaining_sources)
        duplicate_groups.extend(url_groups)
        
        # Create final deduplicated list
        deduplicated_sources = self._create_deduplicated_list(
            sources, duplicate_groups, preserve_highest_score
        )
        
        self.logger.info(
            f"Deduplication complete: {len(sources)} -> {len(deduplicated_sources)} "
            f"({len(sources) - len(deduplicated_sources)} duplicates removed)"
        )
        
        return deduplicated_sources, duplicate_groups
    
    def _find_simhash_duplicates(self, sources: List[PaperInfo]) -> List[DuplicateGroup]:
        """Find duplicates using SimHash algorithm."""
        if not self.use_simhash:
            return []
        
        duplicate_groups = []
        simhashes = {}
        
        # Calculate SimHash for each source
        for source in sources:
            text = f"{source.title} {source.abstract}".lower()
            simhash_value = Simhash(self._tokenize_text(text))
            simhashes[source] = simhash_value
        
        # Find duplicates by comparing SimHash values
        processed = set()
        for source1 in sources:
            if source1 in processed:
                continue
            
            duplicates = []
            simhash1 = simhashes[source1]
            
            for source2 in sources:
                if source2 == source1 or source2 in processed:
                    continue
                
                simhash2 = simhashes[source2]
                hamming_distance = simhash1.distance(simhash2)
                
                if hamming_distance <= self.simhash_threshold:
                    duplicates.append(source2)
                    processed.add(source2)
            
            if duplicates:
                # Calculate average similarity for the group
                similarity_score = 1.0 - (self.simhash_threshold / 64.0)  # Normalize
                
                duplicate_groups.append(DuplicateGroup(
                    representative=source1.raw_data,
                    duplicates=[dup.raw_data for dup in duplicates],
                    similarity_score=similarity_score,
                    dedup_method='simhash'
                ))
                processed.add(source1)
        
        return duplicate_groups
    
    def _find_title_duplicates(self, sources: List[PaperInfo]) -> List[DuplicateGroup]:
        """Find duplicates based on title similarity."""
        duplicate_groups = []
        processed = set()
        
        for i, source1 in enumerate(sources):
            if source1 in processed:
                continue
            
            duplicates = []
            
            for j, source2 in enumerate(sources[i+1:], i+1):
                if source2 in processed:
                    continue
                
                # Calculate title similarity
                title_sim = self._calculate_string_similarity(
                    source1.title.lower(), source2.title.lower()
                )
                
                # Also check abstract similarity for borderline cases
                abstract_sim = self._calculate_string_similarity(
                    source1.abstract.lower(), source2.abstract.lower()
                )
                
                # Consider it a duplicate if title is very similar OR both title and abstract are similar
                is_duplicate = (
                    title_sim >= self.title_threshold or
                    (title_sim >= 0.6 and abstract_sim >= self.abstract_threshold)
                )
                
                if is_duplicate:
                    duplicates.append(source2)
                    processed.add(source2)
            
            if duplicates:
                # Use the highest similarity score found
                max_similarity = max(
                    self._calculate_string_similarity(source1.title.lower(), dup.title.lower())
                    for dup in duplicates
                )
                
                duplicate_groups.append(DuplicateGroup(
                    representative=source1.raw_data,
                    duplicates=[dup.raw_data for dup in duplicates],
                    similarity_score=max_similarity,
                    dedup_method='title_similarity'
                ))
                processed.add(source1)
        
        return duplicate_groups
    
    def _find_url_duplicates(self, sources: List[PaperInfo]) -> List[DuplicateGroup]:
        """Find exact URL duplicates."""
        duplicate_groups = []
        url_map = defaultdict(list)
        
        # Group by normalized URL
        for source in sources:
            normalized_url = self._normalize_url(source.url)
            url_map[normalized_url].append(source)
        
        # Create duplicate groups for URLs with multiple papers
        for url, url_sources in url_map.items():
            if len(url_sources) > 1:
                # Sort by score to pick the best representative
                url_sources.sort(key=lambda x: x.raw_data.get('score', 0), reverse=True)
                
                duplicate_groups.append(DuplicateGroup(
                    representative=url_sources[0].raw_data,
                    duplicates=[dup.raw_data for dup in url_sources[1:]],
                    similarity_score=1.0,  # Exact URL match
                    dedup_method='url_exact'
                ))
        
        return duplicate_groups
    
    def _get_remaining_sources(
        self, 
        all_sources: List[PaperInfo], 
        duplicate_groups: List[DuplicateGroup]
    ) -> List[PaperInfo]:
        """Get sources that haven't been processed for deduplication yet."""
        processed_ids = set()
        
        for group in duplicate_groups:
            # Add representative ID
            rep_id = group.representative.get('id') or group.representative.get('url', '')
            processed_ids.add(rep_id)
            
            # Add duplicate IDs
            for dup in group.duplicates:
                dup_id = dup.get('id') or dup.get('url', '')
                processed_ids.add(dup_id)
        
        return [
            source for source in all_sources 
            if (source.paper_id not in processed_ids and source.url not in processed_ids)
        ]
    
    def _create_deduplicated_list(
        self,
        sources: List[PaperInfo],
        duplicate_groups: List[DuplicateGroup],
        preserve_highest_score: bool
    ) -> List[PaperInfo]:
        """Create the final deduplicated list of sources."""
        result = []
        processed_ids = set()
        
        # Add representatives from duplicate groups
        for group in duplicate_groups:
            if preserve_highest_score:
                # Find the highest-scoring paper in the group
                all_papers_data = [group.representative] + group.duplicates
                best_paper_data = max(all_papers_data, key=lambda x: x.get('score', 0))
                
                # Find the corresponding PaperInfo object
                best_paper = None
                for source in sources:
                    source_id = source.paper_id or source.url
                    paper_id = best_paper_data.get('id') or best_paper_data.get('url', '')
                    if source_id == paper_id:
                        best_paper = source
                        break
                
                if best_paper:
                    result.append(best_paper)
            else:
                # Find the representative PaperInfo object
                rep_data = group.representative
                for source in sources:
                    source_id = source.paper_id or source.url
                    rep_id = rep_data.get('id') or rep_data.get('url', '')
                    if source_id == rep_id:
                        result.append(source)
                        break
            
            # Mark all papers in the group as processed
            rep_id = group.representative.get('id') or group.representative.get('url', '')
            processed_ids.add(rep_id)
            
            for dup in group.duplicates:
                dup_id = dup.get('id') or dup.get('url', '')
                processed_ids.add(dup_id)
        
        # Add sources that weren't duplicates
        for source in sources:
            source_id = source.paper_id or source.url
            if source_id not in processed_ids:
                result.append(source)
        
        return result
    
    def _tokenize_text(self, text: str) -> List[str]:
        """Tokenize text for SimHash calculation."""
        # Simple tokenization - could be improved with proper NLP
        text = re.sub(r'[^\w\s]', '', text.lower())
        words = text.split()
        
        # Create n-grams for better similarity detection
        tokens = words.copy()
        
        # Add bigrams
        for i in range(len(words) - 1):
            tokens.append(f"{words[i]}_{words[i+1]}")
        
        # Add trigrams for longer texts
        if len(words) > 10:
            for i in range(len(words) - 2):
                tokens.append(f"{words[i]}_{words[i+1]}_{words[i+2]}")
        
        return tokens
    
    def _calculate_string_similarity(self, str1: str, str2: str) -> float:
        """Calculate similarity between two strings using Jaccard similarity."""
        if not str1 or not str2:
            return 0.0
        
        # Tokenize strings
        tokens1 = set(self._tokenize_text(str1))
        tokens2 = set(self._tokenize_text(str2))
        
        # Calculate Jaccard similarity
        intersection = len(tokens1.intersection(tokens2))
        union = len(tokens1.union(tokens2))
        
        return intersection / union if union > 0 else 0.0
    
    def _normalize_url(self, url: str) -> str:
        """Normalize URL for comparison."""
        if not url:
            return ""
        
        # Remove protocol and www
        normalized = re.sub(r'^https?://', '', url.lower())
        normalized = re.sub(r'^www\.', '', normalized)
        
        # Remove trailing slash
        normalized = normalized.rstrip('/')
        
        # Handle ArXiv URLs specifically
        if 'arxiv.org' in normalized:
            # Extract just the paper ID
            match = re.search(r'arxiv\.org/(?:abs|pdf)/([0-9]+\.[0-9]+)', normalized)
            if match:
                return f"arxiv.org/abs/{match.group(1)}"
        
        return normalized
    
    def get_duplicate_statistics(self, duplicate_groups: List[DuplicateGroup]) -> Dict[str, Any]:
        """Get statistics about the deduplication process."""
        if not duplicate_groups:
            return {
                'total_groups': 0,
                'total_duplicates': 0,
                'methods_used': [],
                'average_similarity': 0.0
            }
        
        methods_count = defaultdict(int)
        total_duplicates = 0
        total_similarity = 0.0
        
        for group in duplicate_groups:
            methods_count[group.dedup_method] += 1
            total_duplicates += len(group.duplicates)
            total_similarity += group.similarity_score
        
        return {
            'total_groups': len(duplicate_groups),
            'total_duplicates': total_duplicates,
            'methods_used': dict(methods_count),
            'average_similarity': total_similarity / len(duplicate_groups),
            'simhash_available': SIMHASH_AVAILABLE
        } 