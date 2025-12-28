"""
Profile-Aware Research Interest Clustering for Theseus Insight.

This module provides lightweight paper clustering against profile-specific research interests
using semantic similarity (cosine similarity on embeddings).

Key Features:
- Works with profile_research_interests table (profile-specific)
- Cluster papers against profile interests using embedding similarity
- Calculate weekly temporal metrics and aggregate to monthly/quarterly views
- Stores results in profile_paper_interests and profile_interest_metrics tables
"""
from __future__ import annotations

import logging
from typing import List, Dict, Any, Tuple, Optional, Callable
from datetime import datetime, date, timedelta
import json
import numpy as np
from collections import defaultdict
import uuid

# Data access
from ..data_access import (
    SettingsRepository, PaperRepository,
    ProfileInterestsRepository,
    ProfilePaperInterestsRepository, ProfileInterestMetricsRepository
)
from LLMFactory.providers import SentenceTransformerInference

logger = logging.getLogger(__name__)


def parse_embedding(embedding) -> np.ndarray:
    """
    Parse an embedding that may be a string (pgvector format), list, or numpy array.

    pgvector returns embeddings as strings like '[0.123,-0.456,...]'
    """
    if embedding is None:
        return None

    if isinstance(embedding, np.ndarray):
        return embedding

    if isinstance(embedding, str):
        # pgvector format: '[0.123,-0.456,0.789,...]'
        cleaned = embedding.strip('[]')
        if not cleaned:
            return None
        return np.array([float(x) for x in cleaned.split(',')])

    if isinstance(embedding, (list, tuple)):
        return np.array(embedding)

    # Try to convert directly
    return np.array(embedding)


class MetricsLogger:
    """Comprehensive metrics logging for trends processing."""

    def __init__(self):
        self.metrics_logger = logging.getLogger('trends_metrics')
        if not self.metrics_logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - TRENDS_METRICS - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.metrics_logger.addHandler(handler)
            self.metrics_logger.setLevel(logging.INFO)

    def log_pipeline_start(self, parameters: Dict[str, Any]) -> str:
        """Log pipeline start with parameters."""
        run_id = str(uuid.uuid4())[:8]
        self.metrics_logger.info(f"Pipeline START [{run_id}] - Parameters: {parameters}")
        return run_id

    def log_pipeline_completion(self, run_id: str, processing_time: float, results: Dict[str, Any]) -> None:
        """Log pipeline completion with results."""
        self.metrics_logger.info(f"Pipeline COMPLETE [{run_id}] - Time: {processing_time:.2f}s - Results: {results}")

    def log_error(self, run_id: str, error_type: str, error_message: str) -> None:
        """Log errors with context."""
        self.metrics_logger.error(f"ERROR [{run_id}] - {error_type}: {error_message}")

    def log_info(self, category: str, message: str) -> None:
        """Log general information messages."""
        self.metrics_logger.info(f"[{category.upper()}] - {message}")


class ProfileInterestProcessor:
    """Processor for profile-specific research interest clustering and temporal analysis."""

    def __init__(self,
                 embedding_model: Optional[SentenceTransformerInference] = None,
                 similarity_threshold: float = 0.3,
                 verbose: bool = True):
        """
        Initialize the profile interest processor.

        Args:
            embedding_model: Pre-initialized embedding model, or None to load from config
            similarity_threshold: Minimum similarity score for paper-interest associations
            verbose: Whether to print progress information
        """
        self.embedding_model = embedding_model
        self.similarity_threshold = similarity_threshold
        self.verbose = verbose
        self.metrics_logger = MetricsLogger()

    def _load_embedding_model(self) -> SentenceTransformerInference:
        """Load embedding model from orchestration config."""
        if self.embedding_model:
            return self.embedding_model

        orchestration_json = SettingsRepository.get("orchestration")
        if not orchestration_json:
            raise ValueError("Orchestration config not found in settings")

        orchestration_config = json.loads(orchestration_json)
        embedding_config = orchestration_config.get('embedding_model')
        if not embedding_config:
            raise ValueError("Embedding model config not found")

        self.embedding_model = SentenceTransformerInference(
            embedding_config['model_name'],
            remote_code=embedding_config.get('trust_remote_code', False)
        )

        if self.verbose:
            logger.info(f"Loaded embedding model: {embedding_config['model_name']}")

        return self.embedding_model

    def ensure_profile_interests_embedded(
        self,
        profile_id: int,
        progress_callback: Optional[Callable] = None
    ) -> List[Dict[str, Any]]:
        """
        Ensure all research interests for a profile have embeddings.

        Args:
            profile_id: Profile ID to process
            progress_callback: Optional progress callback

        Returns:
            List of research interest dictionaries with embeddings
        """
        if progress_callback:
            progress_callback("embedding", 10, f"Loading interests for profile {profile_id}")

        # Get interests for this profile
        interests = ProfileInterestsRepository.get_by_profile(profile_id)
        if not interests:
            return []

        # Load embedding model
        embedding_model = self._load_embedding_model()
        model_name = getattr(embedding_model, 'model_name', 'unknown')

        # Embed any interests that don't have embeddings yet
        embedded_interests = []
        for i, interest in enumerate(interests):
            if progress_callback:
                progress_callback("embedding", 10 + (i * 40) // len(interests),
                                f"Processing interest {i+1}/{len(interests)}")

            # Check if already embedded
            if interest.get('embedding') is not None:
                embedded_interests.append(interest)
                continue

            # Generate embedding
            embedding = embedding_model.invoke(interest['interest_text'], to_list=True)
            embedding_list = embedding if isinstance(embedding, list) else embedding.tolist()

            # Update in database
            ProfileInterestsRepository.update_embedding(
                interest['id'],
                embedding_list,
                model_name
            )

            interest['embedding'] = embedding_list
            interest['embedding_model'] = model_name
            embedded_interests.append(interest)

        if progress_callback:
            progress_callback("embedding", 50, f"Embedded {len(embedded_interests)} interests")

        return embedded_interests

    def cluster_papers_for_profile(
        self,
        profile_id: int,
        papers: List[Dict[str, Any]],
        interests: List[Dict[str, Any]],
        progress_callback: Optional[Callable] = None
    ) -> List[Tuple[int, int, float]]:
        """
        Cluster papers against profile research interests using cosine similarity.

        Args:
            profile_id: Profile ID
            papers: List of paper dictionaries with embeddings
            interests: List of interest dictionaries with embeddings
            progress_callback: Optional progress callback

        Returns:
            List of (paper_id, interest_id, similarity_score) tuples
        """
        if progress_callback:
            progress_callback("clustering", 50, f"Clustering {len(papers)} papers against {len(interests)} interests")

        relationships = []
        batch_size = 500

        # Filter interests that have embeddings
        interests_with_embeddings = [i for i in interests if i.get('embedding')]
        if not interests_with_embeddings:
            return []

        # Convert interest embeddings to numpy for efficient computation
        # Parse embeddings in case they come as strings from pgvector
        interest_embeddings = np.array([parse_embedding(i['embedding']) for i in interests_with_embeddings])

        for batch_start in range(0, len(papers), batch_size):
            batch_end = min(batch_start + batch_size, len(papers))
            batch = papers[batch_start:batch_end]

            if progress_callback:
                progress = 50 + (batch_start * 30) // len(papers)
                progress_callback("clustering", progress, f"Processing papers {batch_start+1}-{batch_end}/{len(papers)}")

            for paper in batch:
                paper_embedding = paper.get('embedding')
                if paper_embedding is None:
                    continue

                # Parse embedding in case it comes as a string from pgvector
                paper_embedding = parse_embedding(paper_embedding)
                if paper_embedding is None:
                    continue

                # Compute cosine similarity with all interests
                norms = np.linalg.norm(interest_embeddings, axis=1) * np.linalg.norm(paper_embedding)
                norms[norms == 0] = 1e-8  # Avoid division by zero
                similarities = np.dot(interest_embeddings, paper_embedding) / norms

                # Find interests above threshold
                for interest_idx, similarity in enumerate(similarities):
                    if similarity >= self.similarity_threshold:
                        relationships.append((
                            paper['id'],
                            interests_with_embeddings[interest_idx]['id'],
                            float(similarity)
                        ))

        if progress_callback:
            progress_callback("clustering", 85, f"Found {len(relationships)} paper-interest relationships")

        return relationships

    def calculate_metrics_for_profile(
        self,
        profile_id: int,
        lookback_months: int = 24,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        Calculate weekly metrics for all profile interests.

        Args:
            profile_id: Profile ID
            lookback_months: How many months to look back
            progress_callback: Optional progress callback

        Returns:
            Dictionary with calculation results
        """
        if progress_callback:
            progress_callback("metrics", 85, "Calculating weekly metrics")

        # Get interests for this profile
        interests = ProfileInterestsRepository.get_by_profile(profile_id)
        if not interests:
            return {"error": "No interests found for profile"}

        end_date = date.today()
        start_date = end_date - timedelta(days=lookback_months * 30)

        metrics_created = 0
        previous_counts = {}

        for i, interest in enumerate(interests):
            interest_id = interest['id']

            if progress_callback:
                progress = 85 + (i * 10) // len(interests)
                progress_callback("metrics", progress, f"Calculating metrics for interest {i+1}/{len(interests)}")

            # Get papers for this interest within the time range
            papers = ProfilePaperInterestsRepository.get_papers_for_interest(
                interest_id,
                limit=10000,
                start_date=start_date,
                end_date=end_date
            )

            if not papers:
                continue

            # Group papers by week
            weekly_data = defaultdict(list)
            for paper in papers:
                pub_date = paper.get('published_date')
                if pub_date:
                    if isinstance(pub_date, str):
                        pub_date = datetime.fromisoformat(pub_date.replace('Z', '+00:00')).date()
                    elif isinstance(pub_date, datetime):
                        pub_date = pub_date.date()

                    # Get week start (Monday)
                    week_start = pub_date - timedelta(days=pub_date.weekday())
                    weekly_data[week_start].append(paper)

            # Create metrics for each week
            previous_count = previous_counts.get(interest_id, 0)
            for week_start in sorted(weekly_data.keys()):
                week_end = week_start + timedelta(days=6)
                papers_in_week = weekly_data[week_start]
                doc_count = len(papers_in_week)

                # Calculate average scores
                similarity_scores = [p.get('similarity_score', 0) for p in papers_in_week if p.get('similarity_score')]
                paper_scores = [p.get('score', 0) for p in papers_in_week if p.get('score')]

                avg_relevance = np.mean(similarity_scores) if similarity_scores else None
                avg_paper_score = np.mean(paper_scores) if paper_scores else None

                # Calculate growth rate
                if previous_count > 0:
                    growth_rate = (doc_count - previous_count) / previous_count
                else:
                    growth_rate = 0.0

                ProfileInterestMetricsRepository.insert(
                    profile_interest_id=interest_id,
                    period_start=week_start,
                    period_end=week_end,
                    period_type='week',
                    doc_count=doc_count,
                    avg_relevance_score=float(avg_relevance) if avg_relevance is not None else None,
                    avg_paper_score=float(avg_paper_score) if avg_paper_score is not None else None,
                    growth_rate=growth_rate
                )
                metrics_created += 1
                previous_count = doc_count

            previous_counts[interest_id] = previous_count

        if progress_callback:
            progress_callback("metrics", 95, f"Created {metrics_created} weekly metrics")

        return {
            "success": True,
            "metrics_created": metrics_created,
            "interests_processed": len(interests)
        }

    def run_for_profile(
        self,
        profile_id: int,
        lookback_months: int = 24,
        min_papers: int = 10,
        similarity_threshold: Optional[float] = None,
        clear_existing: bool = False,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        Run the interest clustering pipeline for a single profile.

        Args:
            profile_id: Profile ID to process
            lookback_months: How many months of historical data to analyze
            min_papers: Minimum number of papers required to run
            similarity_threshold: Override default similarity threshold
            clear_existing: If True, clear existing data for this profile first
            progress_callback: Optional progress callback

        Returns:
            Dictionary with pipeline results
        """
        import time
        start_time = time.time()

        if similarity_threshold is not None:
            self.similarity_threshold = similarity_threshold

        run_id = self.metrics_logger.log_pipeline_start({
            'profile_id': profile_id,
            'lookback_months': lookback_months,
            'min_papers': min_papers,
            'similarity_threshold': self.similarity_threshold,
            'clear_existing': clear_existing
        })

        results = {
            'success': False,
            'profile_id': profile_id,
            'interests_processed': 0,
            'papers_processed': 0,
            'relationships_created': 0,
            'errors': []
        }

        try:
            # Clear existing data if requested
            if clear_existing:
                if progress_callback:
                    progress_callback("cleanup", 5, "Clearing existing profile data")
                ProfilePaperInterestsRepository.delete_for_profile(profile_id)
                ProfileInterestMetricsRepository.delete_for_profile(profile_id)

            # Step 1: Ensure interests have embeddings
            if progress_callback:
                progress_callback("embedding", 10, "Embedding research interests")

            interests = self.ensure_profile_interests_embedded(profile_id, progress_callback)
            if not interests:
                results['errors'].append(f"No interests found for profile {profile_id}")
                return results

            results['interests_processed'] = len(interests)

            # Step 2: Get papers with embeddings
            if progress_callback:
                progress_callback("loading", 45, "Loading papers with embeddings")

            end_date = date.today()
            start_date = end_date - timedelta(days=lookback_months * 30)

            papers = PaperRepository.get_papers_with_embeddings(
                start_date=start_date,
                end_date=end_date,
                limit=None
            )
            results['papers_processed'] = len(papers)

            if len(papers) < min_papers:
                results['errors'].append(f"Not enough papers ({len(papers)} < {min_papers})")
                return results

            # Step 3: Cluster papers against interests
            if progress_callback:
                progress_callback("clustering", 50, "Clustering papers against interests")

            relationships = self.cluster_papers_for_profile(
                profile_id, papers, interests, progress_callback
            )

            # Step 4: Save relationships
            if progress_callback:
                progress_callback("saving", 80, f"Saving {len(relationships)} relationships")

            # Bulk insert relationships
            ProfilePaperInterestsRepository.bulk_insert(relationships)
            results['relationships_created'] = len(relationships)

            # Step 5: Calculate metrics
            if progress_callback:
                progress_callback("metrics", 85, "Calculating temporal metrics")

            self.calculate_metrics_for_profile(profile_id, lookback_months, progress_callback)

            results['success'] = True

        except Exception as e:
            error_msg = f"Pipeline error: {str(e)}"
            results['errors'].append(error_msg)
            self.metrics_logger.log_error(run_id, "pipeline", error_msg)
            logger.exception(f"Pipeline failed for profile {profile_id}: {e}")

        processing_time = time.time() - start_time
        self.metrics_logger.log_pipeline_completion(run_id, processing_time, results)

        if progress_callback:
            progress_callback("complete", 100, f"Pipeline completed in {processing_time:.1f}s")

        return results

    def run_for_profiles(
        self,
        profile_ids: List[int],
        lookback_months: int = 24,
        min_papers: int = 10,
        similarity_threshold: Optional[float] = None,
        clear_existing: bool = False,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        Run the interest clustering pipeline for multiple profiles.

        Args:
            profile_ids: List of profile IDs to process
            lookback_months: How many months of historical data to analyze
            min_papers: Minimum number of papers required
            similarity_threshold: Override default similarity threshold
            clear_existing: If True, clear existing data first
            progress_callback: Optional progress callback

        Returns:
            Dictionary with aggregated pipeline results
        """
        aggregated_results = {
            'success': True,
            'profiles_processed': 0,
            'total_interests': 0,
            'total_papers': 0,
            'total_relationships': 0,
            'profile_results': {},
            'errors': []
        }

        for i, profile_id in enumerate(profile_ids):
            if progress_callback:
                base_progress = (i * 100) // len(profile_ids)
                def profile_progress(stage, progress, message):
                    adjusted_progress = base_progress + (progress // len(profile_ids))
                    progress_callback(stage, adjusted_progress, f"[Profile {profile_id}] {message}")
            else:
                profile_progress = None

            result = self.run_for_profile(
                profile_id=profile_id,
                lookback_months=lookback_months,
                min_papers=min_papers,
                similarity_threshold=similarity_threshold,
                clear_existing=clear_existing,
                progress_callback=profile_progress
            )

            aggregated_results['profile_results'][profile_id] = result
            aggregated_results['profiles_processed'] += 1
            aggregated_results['total_interests'] += result.get('interests_processed', 0)
            aggregated_results['total_relationships'] += result.get('relationships_created', 0)

            if not result.get('success'):
                aggregated_results['success'] = False
                aggregated_results['errors'].extend(result.get('errors', []))

            # Track max papers processed (they're shared across profiles)
            aggregated_results['total_papers'] = max(
                aggregated_results['total_papers'],
                result.get('papers_processed', 0)
            )

        return aggregated_results
