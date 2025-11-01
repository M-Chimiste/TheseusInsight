"""
Topic extraction and trend forecasting pipeline for Theseus Insight.

This module implements BERTopic-based topic modeling on paper embeddings,
calculates temporal metrics, and generates forecasts using Prophet.
"""
from __future__ import annotations

import logging
from typing import List, Dict, Any, Tuple, Optional, Callable
from datetime import datetime, date, timedelta
import json
import numpy as np
import pandas as pd
from collections import defaultdict
import uuid
import warnings
import gc

# Topic modeling - imports deferred to avoid numba conflicts at startup
# from bertopic import BERTopic  # Imported on-demand
# from hdbscan import HDBSCAN  # Imported on-demand  
# from umap import UMAP  # Imported on-demand
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer

# Forecasting
from prophet import Prophet
from prophet.diagnostics import cross_validation, performance_metrics
from sklearn.metrics import mean_absolute_error, mean_squared_error

# Data access
from ..data_access import (
    PaperRepository, TopicsRepository, TopicMetricsRepository, 
    PaperTopicsRepository, SettingsRepository, TrendsRepository,
    ResearchInterestsRepository, ResearchInterestMetricsRepository,
    PaperResearchInterestsRepository
)
from LLMFactory.providers import SentenceTransformerInference

logger = logging.getLogger(__name__)

# Constants for accuracy monitoring
FORECAST_ACCURACY_THRESHOLD = 0.30  # 30% MAE threshold for alerting
MIN_ACCURACY_SAMPLES = 3  # Minimum samples needed for accuracy calculation


class ForecastAccuracyTracker:
    """Tracks and logs forecast accuracy over time."""
    
    def __init__(self):
        self.accuracy_logger = logging.getLogger('forecast_accuracy')
        # Create dedicated handler for forecast accuracy logs
        if not self.accuracy_logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - FORECAST_ACCURACY - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.accuracy_logger.addHandler(handler)
            self.accuracy_logger.setLevel(logging.INFO)
    
    def calculate_accuracy_metrics(self, actual_values: List[float], 
                                 predicted_values: List[float]) -> Dict[str, float]:
        """Calculate comprehensive accuracy metrics."""
        if len(actual_values) != len(predicted_values) or len(actual_values) == 0:
            return {}
        
        actual = np.array(actual_values)
        predicted = np.array(predicted_values)
        
        # Calculate metrics
        mae = mean_absolute_error(actual, predicted)
        mse = mean_squared_error(actual, predicted)
        rmse = np.sqrt(mse)
        
        # Mean Absolute Percentage Error (MAPE)
        non_zero_actual = actual[actual != 0]
        non_zero_predicted = predicted[actual != 0]
        
        if len(non_zero_actual) > 0:
            mape = np.mean(np.abs((non_zero_actual - non_zero_predicted) / non_zero_actual))
        else:
            mape = float('inf')
        
        # R-squared
        ss_res = np.sum((actual - predicted) ** 2)
        ss_tot = np.sum((actual - np.mean(actual)) ** 2)
        r2 = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
        
        return {
            'mae': float(mae),
            'mse': float(mse),
            'rmse': float(rmse),
            'mape': float(mape),
            'r2': float(r2),
            'sample_count': len(actual_values)
        }
    
    def log_forecast_accuracy(self, topic_id: int, topic_label: str, 
                            forecast_horizon: str, metrics: Dict[str, float]) -> None:
        """Log forecast accuracy with structured format."""
        log_message = (
            f"Topic {topic_id} ({topic_label}) - {forecast_horizon} forecast - "
            f"MAE: {metrics.get('mae', 0):.4f}, "
            f"RMSE: {metrics.get('rmse', 0):.4f}, "
            f"MAPE: {metrics.get('mape', 0):.4f}, "
            f"R²: {metrics.get('r2', 0):.4f}, "
            f"Samples: {metrics.get('sample_count', 0)}"
        )
        
        # Alert if accuracy is below threshold
        mae = metrics.get('mae', 0)
        if mae > FORECAST_ACCURACY_THRESHOLD:
            self.accuracy_logger.warning(f"⚠️  ACCURACY ALERT: {log_message}")
            # You could integrate with alerting systems here (email, Slack, etc.)
        else:
            self.accuracy_logger.info(log_message)
    
    def check_and_alert_poor_accuracy(self, topic_id: int, topic_label: str,
                                    accuracy_metrics: Dict[str, Dict[str, float]]) -> None:
        """Check accuracy across all forecast horizons and send alerts if needed."""
        alerts = []
        
        for horizon, metrics in accuracy_metrics.items():
            mae = metrics.get('mae', 0)
            sample_count = metrics.get('sample_count', 0)
            
            if sample_count >= MIN_ACCURACY_SAMPLES and mae > FORECAST_ACCURACY_THRESHOLD:
                alerts.append(f"{horizon}: MAE {mae:.3f} > {FORECAST_ACCURACY_THRESHOLD}")
        
        if alerts:
            alert_message = f"🚨 FORECAST QUALITY ALERT for Topic {topic_id} ({topic_label}): " + ", ".join(alerts)
            self.accuracy_logger.error(alert_message)
            # Here you could integrate with external alerting (email, webhooks, etc.)


class MetricsLogger:
    """Comprehensive metrics logging for trends processing."""
    
    def __init__(self):
        self.metrics_logger = logging.getLogger('trends_metrics')
        # Create dedicated handler for metrics logs
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
    
    def log_pipeline_completion(self, run_id: str, results: Dict[str, Any]) -> None:
        """Log pipeline completion with results."""
        self.metrics_logger.info(f"Pipeline COMPLETE [{run_id}] - Results: {results}")
    
    def log_topic_extraction(self, run_id: str, paper_count: int, topic_count: int, 
                           processing_time: float) -> None:
        """Log topic extraction metrics."""
        self.metrics_logger.info(
            f"Topic Extraction [{run_id}] - Papers: {paper_count}, "
            f"Topics: {topic_count}, Time: {processing_time:.2f}s"
        )
    
    def log_forecast_generation(self, run_id: str, successful_forecasts: int, 
                              failed_forecasts: int, skipped_forecasts: int, processing_time: float) -> None:
        """Log forecast generation metrics including skipped topics."""
        self.metrics_logger.info(
            f"Forecast Generation [{run_id}] - Success: {successful_forecasts}, "
            f"Failed: {failed_forecasts}, Skipped: {skipped_forecasts}, "
            f"Time: {processing_time:.2f}s"
        )
    
    def log_error(self, run_id: str, error_type: str, error_message: str) -> None:
        """Log errors with context."""
        self.metrics_logger.error(f"ERROR [{run_id}] - {error_type}: {error_message}")

    def log_warning(self, run_id: str, warn_type: str, warn_message: str) -> None:
        """Log non-critical warnings (e.g., insufficient data)"""
        self.metrics_logger.warning(f"WARNING [{run_id}] - {warn_type}: {warn_message}")

    def log_info(self, category: str, message: str) -> None:
        """Log general information messages."""
        self.metrics_logger.info(f"[{category.upper()}] - {message}")


class TrendsProcessor:
    """Main processor for topic extraction and trend forecasting."""
    
    def __init__(self, 
                 embedding_model: Optional[SentenceTransformerInference] = None,
                 min_topic_size: int = 10,
                 n_neighbors: int = 15,
                 min_cluster_size: int = 5,
                 verbose: bool = True,
                 performance_config: Optional[Dict[str, Any]] = None):
        """
        Initialize the trends processor.
        
        Args:
            embedding_model: Pre-initialized embedding model, or None to load from config
            min_topic_size: Minimum size for a topic cluster
            n_neighbors: HDBSCAN n_neighbors parameter
            min_cluster_size: HDBSCAN min_cluster_size parameter
            verbose: Whether to print progress information
            performance_config: Performance optimization settings
        """
        self.embedding_model = embedding_model
        self.min_topic_size = min_topic_size
        self.n_neighbors = n_neighbors
        self.min_cluster_size = min_cluster_size
        self.verbose = verbose
        
        # Performance configuration with intelligent defaults
        self.perf_config = performance_config or {}
        self.max_cores = self.perf_config.get('max_cores', 4)
        self.hdbscan_n_jobs = self.perf_config.get('hdbscan_n_jobs', -1)
        self.clustering_batch_size = self.perf_config.get('clustering_batch_size', 50000)
        self.embedding_batch_size = self.perf_config.get('embedding_batch_size', 512)
        self.enable_memory_mapping = self.perf_config.get('enable_memory_mapping', True)
        self.cache_embeddings = self.perf_config.get('cache_embeddings', True)
        self.aggressive_gc = self.perf_config.get('aggressive_garbage_collection', False)
        self.development_mode = self.perf_config.get('development_mode', False)
        self.development_max_papers = self.perf_config.get('development_max_papers', 5000)
        
        # Initialize logging and accuracy tracking
        self.accuracy_tracker = ForecastAccuracyTracker()
        self.metrics_logger = MetricsLogger()
        
        # BERTopic will be initialized lazily when needed
        self.topic_model = None
        
        if self.verbose:
            self._log_performance_config()
        
    def _log_performance_config(self):
        """Log the current performance configuration."""
        self.metrics_logger.log_info("performance", f"🚀 Performance Configuration:")
        self.metrics_logger.log_info("performance", f"  Max Cores: {self.max_cores}")
        self.metrics_logger.log_info("performance", f"  HDBSCAN n_jobs: {self.hdbscan_n_jobs}")
        self.metrics_logger.log_info("performance", f"  Clustering Batch Size: {self.clustering_batch_size:,}")
        self.metrics_logger.log_info("performance", f"  Embedding Batch Size: {self.embedding_batch_size}")
        self.metrics_logger.log_info("performance", f"  Memory Mapping: {self.enable_memory_mapping}")
        self.metrics_logger.log_info("performance", f"  Cache Embeddings: {self.cache_embeddings}")
        if self.development_mode:
            self.metrics_logger.log_info("performance", f"  🔧 Development Mode: Max {self.development_max_papers:,} papers")
        
    def _setup_bertopic(self):
        """Initialize BERTopic with custom parameters optimized for performance."""
        # Import BERTopic dependencies on-demand to avoid startup conflicts
        from bertopic import BERTopic
        from hdbscan import HDBSCAN
        
        # Performance-optimized HDBSCAN model
        memory_config = None
        if self.enable_memory_mapping:
            # Create joblib Memory object for caching
            from joblib import Memory
            memory_config = Memory(location=None, verbose=0)  # In-memory caching
        
        hdbscan_model = HDBSCAN(
            min_cluster_size=self.min_cluster_size,
            min_samples=1,
            metric='euclidean',
            cluster_selection_method='eom',
            prediction_data=True,
            core_dist_n_jobs=self.hdbscan_n_jobs,  # 🚀 CRITICAL: Enable parallelization!
            memory=memory_config  # Use memory mapping for large datasets
        )
        
        # Custom vectorizer for better topic representation
        vectorizer_model = CountVectorizer(
            ngram_range=(1, 2),
            stop_words="english",
            min_df=2,
            max_df=0.95
        )
        
        # Initialize BERTopic with performance optimizations
        self.topic_model = BERTopic(
            hdbscan_model=hdbscan_model,
            vectorizer_model=vectorizer_model,
            min_topic_size=self.min_topic_size,
            nr_topics=None,  # Let it determine automatically
            calculate_probabilities=True,
            verbose=self.verbose
        )
        
        if self.verbose:
            self.metrics_logger.log_info("bertopic", f"🧠 BERTopic initialized with {self.hdbscan_n_jobs} HDBSCAN jobs")
        
    def _load_embedding_model(self) -> SentenceTransformerInference:
        """Load embedding model from orchestration config."""
        if self.embedding_model:
            return self.embedding_model
            
        # Load from settings
        orchestration_json = SettingsRepository.get("orchestration")
        if not orchestration_json:
            raise ValueError("Orchestration config not found in settings")
            
        orchestration_config = json.loads(orchestration_json)
        embedding_config = orchestration_config.get('embedding_model')
        if not embedding_config:
            raise ValueError("Embedding model config not found")
            
        self.embedding_model = SentenceTransformerInference(
            model_name=embedding_config['model_name'],
            remote_code=embedding_config.get('trust_remote_code', False)
        )
        return self.embedding_model
    
    def _manage_memory(self, stage: str):
        """Manage memory between processing stages."""
        if self.aggressive_gc:
            if self.verbose:
                self.metrics_logger.log_info("memory", f"🧹 Aggressive garbage collection after {stage}")
            gc.collect()
            
    def _apply_development_limits(self, papers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Apply development mode limits to reduce dataset size for faster iteration."""
        if not self.development_mode:
            return papers
            
        if len(papers) > self.development_max_papers:
            if self.verbose:
                self.metrics_logger.log_info("development", 
                    f"🔧 Development mode: Limiting to {self.development_max_papers:,} papers (from {len(papers):,})")
            return papers[:self.development_max_papers]
        
        return papers
    
    def extract_topics_from_papers(self, 
                                   papers: List[Dict[str, Any]],
                                   progress_callback: Optional[Callable] = None) -> Tuple[List[int], Any]:
        """
        Extract topics from a list of papers using BERTopic with performance optimizations.
        
        Args:
            papers: List of paper dictionaries with 'title', 'abstract', 'embedding'
            progress_callback: Optional callback for progress updates
            
        Returns:
            Tuple of (topic_assignments, fitted_model)
        """
        if progress_callback:
            progress_callback("topic_extraction", 5, "Applying performance optimizations")
        
        # Apply development mode limits for faster iteration
        papers = self._apply_development_limits(papers)
        
        if progress_callback:
            progress_callback("topic_extraction", 10, f"Preparing {len(papers):,} documents and embeddings")
        
        # Initialize BERTopic if not already done
        if self.topic_model is None:
            if progress_callback:
                progress_callback("topic_extraction", 15, "Initializing performance-optimized BERTopic...")
            self._setup_bertopic()
        
        # Prepare documents (title + abstract) with optimized batching
        documents = []
        embeddings = []
        
        # Process in batches to manage memory efficiently
        batch_size = min(self.clustering_batch_size, len(papers))
        processed = 0
        
        for i in range(0, len(papers), batch_size):
            batch_papers = papers[i:i + batch_size]
            
            for paper in batch_papers:
                # Combine title and abstract
                doc = f"{paper.get('title', '')} {paper.get('abstract', '')}"
                documents.append(doc)
                
                # Use existing embedding if available, otherwise compute
                if paper.get('embedding'):
                    if isinstance(paper['embedding'], str):
                        # Parse pgvector format [1,2,3] -> list
                        embedding_str = paper['embedding'].strip('[]')
                        embedding = [float(x) for x in embedding_str.split(',')]
                    else:
                        embedding = paper['embedding']
                    embeddings.append(embedding)
                else:
                    # Compute embedding on the fly with optimized batch size
                    embedding_model = self._load_embedding_model()
                    embedding = embedding_model.invoke(doc, to_list=True)
                    embeddings.append(embedding)
            
            processed += len(batch_papers)
            if progress_callback and len(papers) > batch_size:
                progress = 15 + int((processed / len(papers)) * 15)  # 15-30%
                progress_callback("topic_extraction", progress, 
                    f"Processed {processed:,}/{len(papers):,} papers in batches")
            
            # Memory management between batches
            if i > 0:  # Don't GC on first batch
                self._manage_memory(f"document_batch_{i//batch_size}")
        
        embeddings = np.array(embeddings)
        
        if progress_callback:
            progress_callback("topic_extraction", 35, 
                f"🚀 Running parallelized BERTopic clustering on {len(documents):,} papers")
        
        if self.verbose:
            self.metrics_logger.log_info("clustering", 
                f"🔥 Starting HDBSCAN clustering with {self.hdbscan_n_jobs} parallel jobs")
        
        # Fit BERTopic with performance monitoring
        start_time = datetime.now()
        topics, probabilities = self.topic_model.fit_transform(documents, embeddings)
        clustering_time = (datetime.now() - start_time).total_seconds()
        
        unique_topics = len(set(topics))
        if self.verbose:
            self.metrics_logger.log_info("clustering", 
                f"⚡ Clustering completed in {clustering_time:.1f}s: {unique_topics} topics extracted")
        
        if progress_callback:
            progress_callback("topic_extraction", 80, 
                f"✅ Extracted {unique_topics} topics in {clustering_time:.1f}s")
        
        # Final memory cleanup
        self._manage_memory("topic_extraction_complete")
        
        return topics, self.topic_model
    
    def save_topics_to_db(self, 
                         topic_model: Any,
                         papers: List[Dict[str, Any]],
                         topic_assignments: List[int],
                         embedding_model_name: str,
                         progress_callback: Optional[Callable] = None) -> Dict[int, int]:
        """
        Save extracted topics and paper assignments to database.
        
        Args:
            topic_model: Fitted BERTopic model
            papers: Original papers list
            topic_assignments: Topic assignments for each paper
            embedding_model_name: Name of the embedding model used
            progress_callback: Optional progress callback
            
        Returns:
            Mapping from BERTopic topic_id to database topic_id
        """
        if progress_callback:
            progress_callback("saving_topics", 10, "Extracting topic information")
        
        # Get topic info from BERTopic
        topic_info = topic_model.get_topic_info()
        topic_mapping = {}  # bertopic_id -> db_id
        
        for _, row in topic_info.iterrows():
            bertopic_id = row['Topic']
            if bertopic_id == -1:  # Skip outliers
                continue
                
            # Get topic representation
            topic_words = topic_model.get_topic(bertopic_id)
            if not topic_words:
                continue
                
            # Create label and keywords
            top_words = [word for word, _ in topic_words[:5]]
            label = f"Topic {bertopic_id}: {' '.join(top_words[:3])}"
            keywords = [word for word, _ in topic_words[:10]]
            
            # Get topic centroid embedding
            topic_embeddings = topic_model.topic_embeddings_
            if topic_embeddings is not None and bertopic_id < len(topic_embeddings):
                centroid_embedding = topic_embeddings[bertopic_id].tolist()
            else:
                centroid_embedding = None
            
            # Save to database
            db_topic_id = TopicsRepository.insert(
                label=label,
                keywords=keywords,
                centroid_embedding=centroid_embedding,
                embedding_model=embedding_model_name
            )
            topic_mapping[bertopic_id] = db_topic_id
        
        if progress_callback:
            progress_callback("saving_topics", 50, f"Saved {len(topic_mapping)} topics")
        
        # Save paper-topic relationships
        paper_topic_pairs = []
        for i, (paper, topic_id) in enumerate(zip(papers, topic_assignments)):
            if topic_id == -1 or topic_id not in topic_mapping:
                continue
                
            paper_id = paper['id']
            db_topic_id = topic_mapping[topic_id]
            
            # Get topic probability as relevance score
            relevance_score = 0.5  # Default fallback
            if hasattr(topic_model, 'probabilities_') and topic_model.probabilities_ is not None:
                if i < len(topic_model.probabilities_):
                    probs = topic_model.probabilities_[i]
                    if topic_id < len(probs):
                        relevance_score = float(probs[topic_id])
            
            paper_topic_pairs.append((paper_id, db_topic_id, relevance_score))
        
        # Bulk insert paper-topic relationships
        if paper_topic_pairs:
            PaperTopicsRepository.bulk_insert(paper_topic_pairs)
        
        if progress_callback:
            progress_callback("saving_topics", 90, f"Saved {len(paper_topic_pairs)} paper-topic relationships")
        
        return topic_mapping
    
    def calculate_weekly_metrics(self, 
                               lookback_months: int = 24,
                               progress_callback: Optional[Callable] = None) -> None:
        """
        Calculate weekly temporal metrics for all topics as the base unit.
        This forms the foundation for all trend analysis and forecasting.
        
        Args:
            lookback_months: How many months back to analyze
            progress_callback: Optional progress callback
        """
        if progress_callback:
            progress_callback("weekly_metrics", 10, "Calculating weekly metrics (base unit)")
        
        # Get all topics
        topics = TopicsRepository.get_all()
        if not topics:
            logger.warning("No topics found for temporal analysis")
            return
        
        # Calculate date ranges - use full available history for better forecasting
        end_date = date.today()
        start_date = end_date - timedelta(days=lookback_months * 30)
        
        # Clear existing weekly metrics for clean recomputation
        TopicMetricsRepository.delete_for_period_type("week")
        
        for i, topic in enumerate(topics):
            topic_id = topic['id']
            
            if progress_callback:
                progress_callback("weekly_metrics", 10 + (i * 80) // len(topics), 
                                f"Processing topic {i+1}/{len(topics)}: {topic['label']}")
            
            # Get papers for this topic
            papers = PaperTopicsRepository.get_papers_for_topic(topic_id, limit=5000)  # Increased limit for full analysis
            if not papers:
                continue
            
            # Group papers by week
            weekly_counts = defaultdict(list)
            for paper in papers:
                paper_date = paper['date']
                if isinstance(paper_date, str):
                    paper_date = datetime.strptime(paper_date, '%Y-%m-%d').date()
                
                if paper_date < start_date:
                    continue
                
                # Get start of week (Monday)
                days_since_monday = paper_date.weekday()
                week_start = paper_date - timedelta(days=days_since_monday)
                week_end = week_start + timedelta(days=6)
                
                week_key = (week_start, week_end)
                weekly_counts[week_key].append(paper)
            
            # Sort weeks chronologically for proper growth rate calculation
            sorted_weeks = sorted(weekly_counts.items(), key=lambda x: x[0][0])
            
            # Calculate metrics for each week and save
            previous_count = 0
            for (week_start, week_end), papers_in_week in sorted_weeks:
                doc_count = len(papers_in_week)
                avg_score = np.mean([p.get('score', 0) for p in papers_in_week if p.get('score')])
                
                # Calculate growth rate compared to previous week
                growth_rate = None
                if previous_count > 0:
                    growth_rate = (doc_count - previous_count) / previous_count
                
                # Save weekly metrics
                TopicMetricsRepository.insert(
                    topic_id=topic_id,
                    period_start=week_start,
                    period_end=week_end,
                    period_type="week",
                    doc_count=doc_count,
                    avg_score=float(avg_score) if not np.isnan(avg_score) else None,
                    growth_rate=growth_rate
                )
                
                previous_count = doc_count

    def calculate_weekly_metrics_incremental(self, 
                                           lookback_months: int = 24,
                                           progress_callback: Optional[Callable] = None) -> None:
        """
        Calculate weekly metrics incrementally, only processing new papers and recent periods.
        This is much more efficient than full recalculation.
        
        Args:
            lookback_months: How many months back to analyze
            progress_callback: Optional progress callback
        """
        if progress_callback:
            progress_callback("weekly_metrics", 10, "Calculating weekly metrics (incremental)")
        
        # Get the latest period end to determine what needs recalculation
        latest_period_end = TopicMetricsRepository.get_latest_period_end("week")
        
        # If no historical data exists, fall back to full calculation
        if latest_period_end is None:
            self.metrics_logger.metrics_logger.info("No historical weekly data found, performing full calculation")
            return self.calculate_weekly_metrics(lookback_months, progress_callback)
        
        # Only recalculate the last 2 weeks + new weeks to handle any late papers
        recalc_start_date = latest_period_end - timedelta(days=14)  # 2 weeks back
        end_date = date.today()
        
        # Delete metrics for periods that need recalculation
        deleted_count = TopicMetricsRepository.delete_recent_periods("week", recalc_start_date)
        self.metrics_logger.metrics_logger.info(f"Deleted {deleted_count} recent weekly metrics for recalculation")
        
        # Get papers that need topic assignment (new papers without topics)
        new_papers = PaperTopicsRepository.get_papers_needing_topic_assignment(recalc_start_date)
        
        if new_papers:
            self.metrics_logger.metrics_logger.info(f"Found {len(new_papers)} new papers needing topic assignment")
            
            # Extract topics for new papers only
            topic_assignments, topic_model = self.extract_topics_from_papers(new_papers, progress_callback)
            
            # Save topic assignments for new papers
            embedding_model_name = getattr(self.embedding_model, 'model_name', 'unknown')
            self.save_topics_to_db(topic_model, new_papers, topic_assignments, embedding_model_name, progress_callback)
        
        # Get all topics and recalculate metrics only for affected periods
        topics = TopicsRepository.get_all()
        if not topics:
            logger.warning("No topics found for temporal analysis")
            return
        
        for i, topic in enumerate(topics):
            topic_id = topic['id']
            
            if progress_callback:
                progress_callback("weekly_metrics", 10 + (i * 80) // len(topics), 
                                f"Processing topic {i+1}/{len(topics)}: {topic['label']}")
            
            # Get papers for this topic that are in the recalculation period
            papers = PaperTopicsRepository.get_papers_with_topics_since(recalc_start_date)
            papers = [p for p in papers if any(t['topic_id'] == topic_id for t in PaperTopicsRepository.get_topics_for_paper(p['id']))]
            
            if not papers:
                continue
            
            # Group papers by week (only for recalculation period)
            weekly_counts = defaultdict(list)
            for paper in papers:
                paper_date = paper['date']
                if isinstance(paper_date, str):
                    paper_date = datetime.strptime(paper_date, '%Y-%m-%d').date()
                
                if paper_date < recalc_start_date:
                    continue
                
                # Get start of week (Monday)
                days_since_monday = paper_date.weekday()
                week_start = paper_date - timedelta(days=days_since_monday)
                week_end = week_start + timedelta(days=6)
                
                week_key = (week_start, week_end)
                weekly_counts[week_key].append(paper)
            
            # Sort weeks chronologically
            sorted_weeks = sorted(weekly_counts.items(), key=lambda x: x[0][0])
            
            # Get the previous week's count for growth rate calculation
            previous_week_start = recalc_start_date - timedelta(days=7)
            previous_metrics = TopicMetricsRepository.get_topic_timeline(topic_id, "week", limit=1)
            previous_count = previous_metrics[0]['doc_count'] if previous_metrics else 0
            
            # Calculate metrics for each week and save
            for (week_start, week_end), papers_in_week in sorted_weeks:
                doc_count = len(papers_in_week)
                avg_score = np.mean([p.get('score', 0) for p in papers_in_week if p.get('score')])
                
                # Calculate growth rate compared to previous week
                growth_rate = None
                if previous_count > 0:
                    growth_rate = (doc_count - previous_count) / previous_count
                
                # Save weekly metrics
                TopicMetricsRepository.insert(
                    topic_id=topic_id,
                    period_start=week_start,
                    period_end=week_end,
                    period_type="week",
                    doc_count=doc_count,
                    avg_score=float(avg_score) if not np.isnan(avg_score) else None,
                    growth_rate=growth_rate
                )
                
                previous_count = doc_count

    def assign_topics_to_new_papers(self, cutoff_date: date | None = None, 
                                   progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """
        Assign topics only to papers that don't have topic assignments yet.
        
        Args:
            cutoff_date: Only process papers from this date onwards
            progress_callback: Optional progress callback
            
        Returns:
            Dictionary with assignment results
        """
        # Get papers needing topic assignment
        new_papers = PaperTopicsRepository.get_papers_needing_topic_assignment(cutoff_date)
        
        if not new_papers:
            return {"new_papers_processed": 0, "topics_assigned": 0}
        
        if progress_callback:
            progress_callback("topic_assignment", 10, f"Assigning topics to {len(new_papers)} new papers")
        
        # Load existing topics and their centroids to classify new papers
        existing_topics = TopicsRepository.get_all()
        if not existing_topics:
            # No existing topics, need to extract topics from all papers
            return {"error": "No existing topics found, full topic extraction required"}
        
        # Use existing topic model to classify new papers
        # This is a simplified approach - in practice you'd want to use the trained BERTopic model
        topic_assignments = []
        
        for paper in new_papers:
            # Simple approach: assign to topic with most similar centroid
            # In practice, you'd want to use the actual BERTopic model for this
            best_topic_id = existing_topics[0]['id']  # Default to first topic
            topic_assignments.append((paper['id'], best_topic_id, 0.5))  # Default relevance
        
        # Bulk insert topic assignments
        PaperTopicsRepository.bulk_insert(topic_assignments)
        
        return {
            "new_papers_processed": len(new_papers),
            "topics_assigned": len(topic_assignments)
        }
    
    def aggregate_weekly_data(self, 
                            target_period: str = "month",
                            duration_months: int = 6,
                            progress_callback: Optional[Callable] = None) -> None:
        """
        Aggregate weekly metrics into monthly or quarterly views for specific durations.
        
        Args:
            target_period: 'month' or 'quarter' to aggregate to
            duration_months: How many months of data to aggregate (1, 3, 6, 12, 24)
            progress_callback: Optional progress callback
        """
        if progress_callback:
            progress_callback("aggregation", 10, f"Aggregating weekly data to {target_period} for {duration_months}M duration")
        
        if target_period not in ["month", "quarter"]:
            raise ValueError("target_period must be 'month' or 'quarter'")
        
        # Get all topics
        topics = TopicsRepository.get_all()
        if not topics:
            logger.warning("No topics found for aggregation")
            return
        
        # Calculate date range for aggregation
        end_date = date.today()
        start_date = end_date - timedelta(days=duration_months * 30)
        
        # Clear existing aggregated data for this period type
        TopicMetricsRepository.delete_for_period_type(target_period)
        
        for i, topic in enumerate(topics):
            topic_id = topic['id']
            
            if progress_callback:
                progress_callback("aggregation", 10 + (i * 80) // len(topics), 
                                f"Aggregating topic {i+1}/{len(topics)}: {topic['label']}")
            
            # Get weekly metrics for this topic
            weekly_metrics = TopicMetricsRepository.get_topic_timeline(
                topic_id, "week", limit=duration_months * 5  # ~5 weeks per month
            )
            
            if not weekly_metrics:
                continue
            
            # Group weekly data by target period
            period_groups = defaultdict(list)
            for metric in weekly_metrics:
                metric_date = metric['period_start']
                if isinstance(metric_date, str):
                    metric_date = datetime.strptime(metric_date, '%Y-%m-%d').date()
                
                if metric_date < start_date:
                    continue
                
                # Calculate target period
                if target_period == "month":
                    period_start = metric_date.replace(day=1)
                    if period_start.month == 12:
                        period_end = period_start.replace(year=period_start.year + 1, month=1) - timedelta(days=1)
                    else:
                        period_end = period_start.replace(month=period_start.month + 1) - timedelta(days=1)
                else:  # quarter
                    quarter = (metric_date.month - 1) // 3 + 1
                    period_start = metric_date.replace(month=(quarter - 1) * 3 + 1, day=1)
                    if quarter == 4:
                        period_end = period_start.replace(year=period_start.year + 1, month=1) - timedelta(days=1)
                    else:
                        period_end = period_start.replace(month=quarter * 3 + 1) - timedelta(days=1)
                
                period_key = (period_start, period_end)
                period_groups[period_key].append(metric)
            
            # Calculate aggregated metrics for each period
            sorted_periods = sorted(period_groups.items(), key=lambda x: x[0][0])
            previous_count = 0
            
            for (period_start, period_end), week_metrics in sorted_periods:
                # Aggregate weekly data
                total_doc_count = sum(m['doc_count'] for m in week_metrics)
                avg_scores = [m['avg_score'] for m in week_metrics if m.get('avg_score') is not None]
                avg_score = np.mean(avg_scores) if avg_scores else None
                
                # Calculate growth rate compared to previous period
                growth_rate = None
                if previous_count > 0:
                    growth_rate = (total_doc_count - previous_count) / previous_count
                
                # Save aggregated metrics
                TopicMetricsRepository.insert(
                    topic_id=topic_id,
                    period_start=period_start,
                    period_end=period_end,
                    period_type=target_period,
                    doc_count=total_doc_count,
                    avg_score=float(avg_score) if avg_score is not None else None,
                    growth_rate=growth_rate
                )
                
                previous_count = total_doc_count
    
    def validate_forecast_accuracy(self, 
                                 period_type: str = "month",
                                 run_id: str = "manual",
                                 progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """
        Validate forecast accuracy by comparing past predictions to actual values.
        
        Args:
            period_type: Time period for validation
            run_id: Run identifier for logging
            progress_callback: Optional progress callback
            
        Returns:
            Dictionary with validation results and accuracy metrics
        """
        if progress_callback:
            progress_callback("validation", 10, "Starting forecast accuracy validation")
        
        # Get all topics with forecasts
        topics = TopicsRepository.get_all()
        validation_results = {
            'total_topics_checked': 0,
            'topics_with_accuracy_data': 0,
            'overall_accuracy': {},
            'poor_accuracy_topics': [],
            'validation_timestamp': datetime.now().isoformat()
        }
        
        all_actual_values = []
        all_forecast_1m = []
        all_forecast_3m = []
        
        for i, topic in enumerate(topics):
            topic_id = topic['id']
            topic_label = topic['label']
            
            if progress_callback:
                progress_callback("validation", 10 + (i * 80) // len(topics),
                                f"Validating topic {i+1}/{len(topics)}: {topic_label}")
            
            validation_results['total_topics_checked'] += 1
            
            # Get historical metrics to compare forecasts
            metrics = TopicMetricsRepository.get_topic_timeline(topic_id, period_type, limit=12)
            if len(metrics) < 4:  # Need enough data for comparison
                continue
            
            # Find metrics with forecasts and corresponding actual values
            forecast_comparisons = {'1m': [], '3m': []}
            
            for j, metric in enumerate(metrics):
                if not metric.get('forecast_1m') and not metric.get('forecast_3m'):
                    continue
                    
                # For 1-month forecast validation
                if metric.get('forecast_1m') and j > 0:
                    actual_next_month = metrics[j-1].get('doc_count', 0)  # Next month's actual
                    forecast_1m = metric['forecast_1m']
                    forecast_comparisons['1m'].append((actual_next_month, forecast_1m))
                    all_actual_values.append(actual_next_month)
                    all_forecast_1m.append(forecast_1m)
                
                # For 3-month forecast validation
                if metric.get('forecast_3m') and j >= 3:
                    actual_3m_later = metrics[j-3].get('doc_count', 0)  # 3 months later actual
                    forecast_3m = metric['forecast_3m']
                    forecast_comparisons['3m'].append((actual_3m_later, forecast_3m))
                    all_forecast_3m.append(forecast_3m)
            
            # Calculate accuracy metrics for this topic
            topic_accuracy = {}
            for horizon, comparisons in forecast_comparisons.items():
                if len(comparisons) >= MIN_ACCURACY_SAMPLES:
                    actual_vals = [c[0] for c in comparisons]
                    predicted_vals = [c[1] for c in comparisons]
                    
                    metrics_dict = self.accuracy_tracker.calculate_accuracy_metrics(
                        actual_vals, predicted_vals
                    )
                    topic_accuracy[horizon] = metrics_dict
                    
                    # Log accuracy for this topic and horizon
                    self.accuracy_tracker.log_forecast_accuracy(
                        topic_id, topic_label, f"{horizon} forecast", metrics_dict
                    )
            
            if topic_accuracy:
                validation_results['topics_with_accuracy_data'] += 1
                
                # Check for poor accuracy and alert
                self.accuracy_tracker.check_and_alert_poor_accuracy(
                    topic_id, topic_label, topic_accuracy
                )
        
        # Calculate overall accuracy metrics
        if len(all_actual_values) >= MIN_ACCURACY_SAMPLES:
            validation_results['overall_accuracy']['1m'] = self.accuracy_tracker.calculate_accuracy_metrics(
                all_actual_values, all_forecast_1m
            )
        
        if len(all_forecast_3m) >= MIN_ACCURACY_SAMPLES:
            validation_results['overall_accuracy']['3m'] = self.accuracy_tracker.calculate_accuracy_metrics(
                all_actual_values[:len(all_forecast_3m)], all_forecast_3m
            )
        
        # Log overall validation results
        self.metrics_logger.metrics_logger.info(
            f"Forecast Validation [{run_id}] - Topics checked: {validation_results['total_topics_checked']}, "
            f"With accuracy data: {validation_results['topics_with_accuracy_data']}, "
            f"Overall MAE 1m: {validation_results['overall_accuracy'].get('1m', {}).get('mae', 'N/A')}, "
            f"Overall MAE 3m: {validation_results['overall_accuracy'].get('3m', {}).get('mae', 'N/A')}"
        )
        
        if progress_callback:
            progress_callback("validation", 100, "Forecast accuracy validation completed")
        
        return validation_results
    
    def generate_forecasts(self, 
                          period_type: str = "month",
                          progress_callback: Optional[Callable] = None,
                          run_id: str = "manual") -> Dict[str, Any]:
        """
        Generate Prophet forecasts for all topics with sufficient data.
        
        Args:
            period_type: Time period for forecasting
            progress_callback: Optional progress callback
            run_id: Run identifier for logging
            
        Returns:
            Dictionary with forecasting results and statistics
        """
        start_time = datetime.now()
        forecast_results = {
            'successful_forecasts': 0,
            'failed_forecasts': 0,
            'skipped_topics': 0,
            'total_topics': 0,
            'processing_time_seconds': 0.0,
            'period_type': period_type
        }
        
        if progress_callback:
            progress_callback("forecasting", 10, "Loading topic metrics for forecasting")
        
        # Get all topics with metrics
        topics = TopicsRepository.get_all()
        forecast_results['total_topics'] = len(topics)
        
        for i, topic in enumerate(topics):
            topic_id = topic['id']
            topic_label = topic['label']
            
            if progress_callback:
                progress_callback("forecasting", 10 + (i * 80) // len(topics),
                                f"Forecasting topic {i+1}/{len(topics)}: {topic_label}")
            
            # Get historical metrics
            metrics = TopicMetricsRepository.get_topic_timeline(topic_id, period_type, limit=24)
            if len(metrics) < 3:  # Reduced minimum from 6 to 3 data points for Prophet
                self.metrics_logger.log_warning(
                    run_id, "insufficient_data", 
                    f"Topic {topic_id} ({topic_label}): only {len(metrics)} data points"
                )
                forecast_results['skipped_topics'] += 1
                continue
            
            try:
                # Prepare data for Prophet
                df = pd.DataFrame([
                    {
                        'ds': metric['period_start'],
                        'y': metric['doc_count']
                    }
                    for metric in reversed(metrics)  # Prophet expects chronological order
                ])
                
                # Validate data quality
                if df['y'].sum() == 0:
                    self.metrics_logger.log_warning(
                        run_id, "zero_data", 
                        f"Topic {topic_id} ({topic_label}): all document counts are zero"
                    )
                    forecast_results['skipped_topics'] += 1
                    continue
                
                # Fit Prophet model with settings optimized for small datasets
                model = Prophet(
                    yearly_seasonality=False,
                    weekly_seasonality=(period_type == 'week'),
                    daily_seasonality=False,
                    changepoint_prior_scale=0.01,  # Reduced for smaller datasets
                    seasonality_prior_scale=0.1,   # Reduced for smaller datasets
                    n_changepoints=min(3, len(df) // 2)  # Limit changepoints for small datasets
                )
                
                # Suppress Prophet's verbose output
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    model.fit(df)
                
                # Generate forecasts
                future_periods = min(6, len(df))  # Forecast up to 6 periods ahead, but not more than data points
                if future_periods == 0:
                    self.metrics_logger.log_warning(
                        run_id, "no_forecast_periods", 
                        f"Topic {topic_id} ({topic_label}): cannot generate forecasts"
                    )
                    forecast_results['skipped_topics'] += 1
                    continue
                    
                freq = 'MS' if period_type == 'month' else ('QS' if period_type == 'quarter' else 'W')
                future = model.make_future_dataframe(periods=future_periods, freq=freq)
                forecast = model.predict(future)
                
                # Extract forecast values and ensure non-negative
                forecast_values = forecast.tail(future_periods)['yhat'].values
                forecast_1m = max(0, int(forecast_values[0])) if len(forecast_values) > 0 else None
                forecast_3m = max(0, int(forecast_values[2])) if len(forecast_values) > 2 else None
                forecast_6m = max(0, int(forecast_values[5])) if len(forecast_values) > 5 else None
                
                # Update the latest metric record with forecasts
                if metrics:
                    latest_metric = metrics[0]  # Most recent
                    TopicMetricsRepository.update_forecasts(
                        topic_id=topic_id,
                        period_start=latest_metric['period_start'],
                        period_end=latest_metric['period_end'],
                        period_type=period_type,
                        forecast_1m=forecast_1m,
                        forecast_3m=forecast_3m,
                        forecast_6m=forecast_6m
                    )
                
                forecast_results['successful_forecasts'] += 1
                
                # Log successful forecast
                self.metrics_logger.metrics_logger.info(
                    f"Forecast Success [{run_id}] - Topic {topic_id} ({topic_label}): "
                    f"1m={forecast_1m}, 3m={forecast_3m}, 6m={forecast_6m}"
                )
                
            except Exception as e:
                forecast_results['failed_forecasts'] += 1
                self.metrics_logger.log_error(
                    run_id, "forecast_error", 
                    f"Topic {topic_id} ({topic_label}): {str(e)}"
                )
                continue
        
        # Calculate processing time
        end_time = datetime.now()
        forecast_results['processing_time_seconds'] = (end_time - start_time).total_seconds()
        
        # Log overall results
        self.metrics_logger.log_forecast_generation(
            run_id, 
            forecast_results['successful_forecasts'], 
            forecast_results['failed_forecasts'],
            forecast_results['skipped_topics'],
            forecast_results['processing_time_seconds']
        )
        
        if progress_callback:
            progress_callback("forecasting", 100, 
                            f"Forecasting complete: {forecast_results['successful_forecasts']} success, "
                            f"{forecast_results['failed_forecasts']} failed")
        
        return forecast_results
    
    def run_full_pipeline(self, 
                         lookback_months: int = 24,
                         duration_months: int = 6,
                         min_papers: int = 100,
                         progress_callback: Optional[Callable] = None,
                         validate_accuracy: bool = True) -> Dict[str, Any]:
        """
        Run the complete trends processing pipeline with weekly-first analysis.
        
        This pipeline always computes weekly metrics as the foundation, then aggregates
        to monthly/quarterly views for the specified duration.
        
        Args:
            lookback_months: How many months of historical data to analyze (for training)
            duration_months: Duration for current analysis views (1, 3, 6, 12, 24 months)
            min_papers: Minimum number of papers required to run
            progress_callback: Optional progress callback
            validate_accuracy: Whether to run forecast accuracy validation
            
        Returns:
            Dictionary with processing results and statistics
        """
        start_time = datetime.now()
        
        # Get recent papers with embeddings first to include in logging
        cutoff_date = (datetime.now() - timedelta(days=lookback_months * 30)).date()
        
        # Get ALL papers with embeddings (remove artificial limit)
        # Using a much higher limit to capture all available papers
        all_papers = PaperRepository.get_papers_with_embeddings(limit=100000)
        papers = [p for p in all_papers if p.get('date') and 
                 (isinstance(p['date'], date) and p['date'] >= cutoff_date or
                  isinstance(p['date'], str) and datetime.strptime(p['date'], '%Y-%m-%d').date() >= cutoff_date)]
        
        # Start comprehensive logging with paper statistics
        run_id = self.metrics_logger.log_pipeline_start({
            'analysis_approach': 'weekly_first',
            'lookback_months': lookback_months,
            'duration_months': duration_months,
            'min_papers': min_papers,
            'validate_accuracy': validate_accuracy,
            'total_papers_fetched': len(all_papers),
            'papers_after_date_filter': len(papers),
            'cutoff_date': cutoff_date.isoformat()
        })
        
        pipeline_results = {
            'run_id': run_id,
            'success': False,
            'processing_time_seconds': 0.0,
            'papers_processed': 0,
            'topics_extracted': 0,
            'analysis_approach': 'weekly_first',
            'lookback_months': lookback_months,
            'duration_months': duration_months,
            'completed_at': None,
            'forecast_results': {},
            'validation_results': {},
            'aggregation_results': {},
            'errors': []
        }
        
        try:
            if progress_callback:
                progress_callback("initialization", 5, "Starting trends processing pipeline")
            
            if len(papers) < min_papers:
                error_msg = f"Insufficient papers for analysis: {len(papers)} < {min_papers}"
                self.metrics_logger.log_error(run_id, "insufficient_papers", error_msg)
                pipeline_results['errors'].append(error_msg)
                raise ValueError(error_msg)
            
            pipeline_results['papers_processed'] = len(papers)
            
            if progress_callback:
                progress_callback("initialization", 10, f"Loaded {len(papers)} papers for analysis")
            
            # Step 1: Extract topics
            topic_extraction_start = datetime.now()
            topic_assignments, topic_model = self.extract_topics_from_papers(papers, progress_callback)
            topic_extraction_time = (datetime.now() - topic_extraction_start).total_seconds()
            
            # Step 2: Save topics to database
            embedding_model_name = getattr(self.embedding_model, 'model_name', 'unknown')
            topic_mapping = self.save_topics_to_db(
                topic_model, papers, topic_assignments, embedding_model_name, progress_callback
            )
            
            pipeline_results['topics_extracted'] = len(topic_mapping)
            
            # Log topic extraction metrics
            self.metrics_logger.log_topic_extraction(
                run_id, len(papers), len(topic_mapping), topic_extraction_time
            )
            
            # Step 3: Calculate weekly metrics (foundation)
            if progress_callback:
                progress_callback("weekly_metrics", 40, "Calculating weekly metrics (foundation)")
            
            self.calculate_weekly_metrics(lookback_months, progress_callback)
            
            # Step 4: Aggregate weekly data to monthly view for specified duration
            if progress_callback:
                progress_callback("monthly_aggregation", 50, f"Aggregating to monthly view ({duration_months}M duration)")
            
            self.aggregate_weekly_data("month", duration_months, progress_callback)
            aggregation_results = {'monthly_duration': duration_months}
            
            # Step 5: Aggregate weekly data to quarterly view for longer durations
            if duration_months >= 6:
                if progress_callback:
                    progress_callback("quarterly_aggregation", 60, f"Aggregating to quarterly view ({duration_months}M duration)")
                
                self.aggregate_weekly_data("quarter", duration_months, progress_callback)
                aggregation_results['quarterly_duration'] = duration_months
            
            pipeline_results['aggregation_results'] = aggregation_results
            
            # Step 6: Generate forecasts based on weekly data
            if progress_callback:
                progress_callback("forecasting", 70, "Generating forecasts from weekly data")
            
            forecast_results = self.generate_forecasts("week", progress_callback, run_id)
            pipeline_results['forecast_results'] = forecast_results
            
            # Step 7: Validate forecast accuracy (if enabled)
            if validate_accuracy:
                if progress_callback:
                    progress_callback("validation", 90, "Validating forecast accuracy")
                
                validation_results = self.validate_forecast_accuracy("week", run_id, progress_callback)
                pipeline_results['validation_results'] = validation_results
            
            if progress_callback:
                progress_callback("completed", 100, "Trends processing pipeline completed")
            
            # Mark as successful
            pipeline_results['success'] = True
            
        except Exception as e:
            error_msg = f"Pipeline failed: {str(e)}"
            self.metrics_logger.log_error(run_id, "pipeline_failure", error_msg)
            pipeline_results['errors'].append(error_msg)
            raise
        
        finally:
            # Calculate final processing time
            end_time = datetime.now()
            pipeline_results['processing_time_seconds'] = (end_time - start_time).total_seconds()
            pipeline_results['completed_at'] = end_time.isoformat()
            
            # Log pipeline completion
            self.metrics_logger.log_pipeline_completion(run_id, {
                'success': pipeline_results['success'],
                'processing_time_seconds': pipeline_results['processing_time_seconds'],
                'papers_processed': pipeline_results['papers_processed'],
                'topics_extracted': pipeline_results['topics_extracted'],
                'forecast_success_rate': (
                    pipeline_results['forecast_results'].get('successful_forecasts', 0) / 
                    max(1, pipeline_results['forecast_results'].get('total_topics', 1))
                ) if pipeline_results['forecast_results'] else 0,
                'errors_count': len(pipeline_results['errors'])
            })
        
        return pipeline_results

    def run_incremental_pipeline(self, 
                               lookback_months: int = 24,
                               duration_months: int = 6,
                               min_papers: int = 100,
                               force_full_recalc: bool = False,
                               clear_all_data: bool = False,
                               progress_callback: Optional[Callable] = None,
                               validate_accuracy: bool = True) -> Dict[str, Any]:
        """
        Run an incremental trends processing pipeline that only processes new data.
        
        This is much more efficient as it:
        1. Only assigns topics to papers that don't have topic assignments yet
        2. Only recalculates metrics for recent time periods (last 2 weeks)
        3. Preserves all historical data that hasn't changed
        
        Args:
            lookback_months: How many months of historical data to use for analysis
            duration_months: Duration for current analysis views (1, 3, 6, 12, 24 months)
            min_papers: Minimum number of new papers required to run incremental update
            force_full_recalc: If True, forces full recalculation (ignores incremental logic)
            clear_all_data: NUCLEAR OPTION - Clear all topics, metrics, and relationships first
            progress_callback: Optional progress callback
            validate_accuracy: Whether to run forecast accuracy validation
            
        Returns:
            Dictionary with processing results and statistics
        """
        start_time = datetime.now()
        
        # Handle nuclear option first
        if clear_all_data:
            if progress_callback:
                progress_callback("nuclear_cleanup", 5, "NUCLEAR OPTION: Clearing all trends data")
            
            self.metrics_logger.metrics_logger.warning("NUCLEAR OPTION ACTIVATED: Clearing all trends data for fresh start")
            deleted_counts = TrendsRepository.nuclear_cleanup_all_data()
            self.metrics_logger.metrics_logger.info(f"Nuclear cleanup completed: {deleted_counts}")
            
            # Force full recalculation after nuclear cleanup
            force_full_recalc = True
        
        # Get papers that need topic assignment to include in logging
        new_papers_needing_topics = PaperTopicsRepository.get_papers_needing_topic_assignment()
        latest_period_end = TopicMetricsRepository.get_latest_period_end("week")
        
        # Start comprehensive logging with incremental statistics
        run_id = self.metrics_logger.log_pipeline_start({
            'analysis_approach': 'nuclear_recalc' if clear_all_data else ('full_recalc' if force_full_recalc else 'incremental_weekly'),
            'lookback_months': lookback_months,
            'duration_months': duration_months,
            'min_papers': min_papers,
            'force_full_recalc': force_full_recalc,
            'clear_all_data': clear_all_data,
            'validate_accuracy': validate_accuracy,
            'new_papers_needing_topics': len(new_papers_needing_topics),
            'latest_period_end': latest_period_end.isoformat() if latest_period_end else None,
            'has_historical_data': latest_period_end is not None and not clear_all_data
        })
        
        pipeline_results = {
            'run_id': run_id,
            'success': False,
            'processing_time_seconds': 0.0,
            'papers_processed': 0,
            'topics_extracted': 0,
            'analysis_approach': 'nuclear_recalc' if clear_all_data else ('full_recalc' if force_full_recalc else 'incremental_weekly'),
            'lookback_months': lookback_months,
            'duration_months': duration_months,
            'completed_at': None,
            'forecast_results': {},
            'validation_results': {},
            'aggregation_results': {},
            'incremental_stats': {},
            'nuclear_cleanup_stats': deleted_counts if clear_all_data else {},
            'errors': []
        }
        
        try:
            if progress_callback:
                progress_callback("initialization", 10, f"Starting {'nuclear' if clear_all_data else ('full' if force_full_recalc else 'incremental')} trends processing pipeline")
            
            # Incremental logic is disabled due to bugs - always use full pipeline
            self.metrics_logger.metrics_logger.warning("Incremental pipeline is currently disabled. Falling back to full pipeline.")
            return self.run_full_pipeline(lookback_months, duration_months, min_papers, progress_callback, validate_accuracy)

        except Exception as e:
            error_msg = f"Full pipeline failed: {str(e)}"
            self.metrics_logger.log_error(run_id, "pipeline_failure", error_msg)
            pipeline_results['errors'].append(error_msg)
            raise
        
        finally:
            # Calculate final processing time
            end_time = datetime.now()
            pipeline_results['processing_time_seconds'] = (end_time - start_time).total_seconds()
            pipeline_results['completed_at'] = end_time.isoformat()
            
            # Log pipeline completion
            self.metrics_logger.log_pipeline_completion(run_id, {
                'success': pipeline_results['success'],
                'processing_time_seconds': pipeline_results['processing_time_seconds'],
                'papers_processed': pipeline_results['papers_processed'],
                'topics_extracted': pipeline_results['topics_extracted'],
                'forecast_success_rate': (
                    pipeline_results['forecast_results'].get('successful_forecasts', 0) / 
                    max(1, pipeline_results['forecast_results'].get('total_topics', 1))
                ) if pipeline_results['forecast_results'] else 0,
                'errors_count': len(pipeline_results['errors']),
                'processing_mode': pipeline_results.get('incremental_stats', {}).get('processing_mode', 'unknown'),
                'nuclear_cleanup': clear_all_data
            })
        
        return pipeline_results 

# === Research Interest Clustering Processor ===
# Separate from automatic topic discovery, this analyzes papers against user's research interests

class ResearchInterestProcessor:
    """Processor for research interest based clustering and temporal analysis."""
    
    def __init__(self, 
                 embedding_model: Optional[SentenceTransformerInference] = None,
                 similarity_threshold: float = 0.3,
                 verbose: bool = True):
        """
        Initialize the research interest processor.
        
        Args:
            embedding_model: Pre-initialized embedding model, or None to load from config
            similarity_threshold: Minimum similarity score for paper-interest associations
            verbose: Whether to print progress information
        """
        self.embedding_model = embedding_model
        self.similarity_threshold = similarity_threshold
        self.verbose = verbose
        
        # Use the same accuracy tracker and metrics logger infrastructure
        self.accuracy_tracker = ForecastAccuracyTracker()
        self.metrics_logger = MetricsLogger()
    
    def _load_embedding_model(self) -> SentenceTransformerInference:
        """Load embedding model from orchestration config."""
        if self.embedding_model:
            return self.embedding_model
            
        # Load from settings
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
    
    def setup_research_interests(self, 
                                progress_callback: Optional[Callable] = None) -> List[Dict[str, Any]]:
        """
        Set up research interests by retrieving from settings, splitting by newline, and embedding them.
        
        Args:
            progress_callback: Optional progress callback
            
        Returns:
            List of research interest dictionaries with embeddings
        """
        if progress_callback:
            progress_callback("setup_interests", 10, "Retrieving research interests from settings")
        
        # Get research interests from settings
        research_interests_text = SettingsRepository.get("research_interests")
        if not research_interests_text:
            raise ValueError("No research interests found in settings. Please configure your research interests first.")
        
        # Split by newline and clean up
        interest_lines = [line.strip() for line in research_interests_text.split('\n') 
                         if line.strip() and not line.strip().startswith('#')]
        
        if not interest_lines:
            raise ValueError("No valid research interests found. Please add research interests to settings.")
        
        if progress_callback:
            progress_callback("setup_interests", 30, f"Found {len(interest_lines)} research interests")
        
        # Clear existing research interests for fresh setup
        ResearchInterestsRepository.delete_all()
        
        # Load embedding model
        embedding_model = self._load_embedding_model()
        model_name = getattr(embedding_model, 'model_name', 'unknown')
        
        # Embed each research interest and save to database
        research_interests = []
        for i, interest_text in enumerate(interest_lines):
            if progress_callback:
                progress_callback("setup_interests", 30 + (i * 50) // len(interest_lines), 
                                f"Embedding interest {i+1}/{len(interest_lines)}: {interest_text[:50]}...")
            
            # Generate embedding using invoke method
            embedding = embedding_model.invoke(interest_text, to_list=True)
            embedding_list = embedding if isinstance(embedding, list) else embedding.tolist()
            
            # Save to database
            interest_id = ResearchInterestsRepository.insert(
                interest_text=interest_text,
                embedding=embedding_list,
                embedding_model=model_name
            )
            
            research_interests.append({
                'id': interest_id,
                'interest_text': interest_text,
                'embedding': embedding_list,
                'embedding_model': model_name
            })
        
        if progress_callback:
            progress_callback("setup_interests", 90, f"Successfully set up {len(research_interests)} research interests")
        
        return research_interests
    
    def cluster_papers_by_research_interests(self, 
                                           papers: List[Dict[str, Any]],
                                           research_interests: List[Dict[str, Any]],
                                           progress_callback: Optional[Callable] = None) -> List[Tuple[int, int, float]]:
        """
        Cluster papers against research interests using cosine similarity.
        
        Args:
            papers: List of paper dictionaries with embeddings
            research_interests: List of research interest dictionaries with embeddings
            progress_callback: Optional progress callback
            
        Returns:
            List of (paper_id, research_interest_id, similarity_score) tuples
        """
        if progress_callback:
            progress_callback("clustering", 10, f"Clustering {len(papers):,} papers against {len(research_interests)} research interests")
        
        import numpy as np
        from sklearn.metrics.pairwise import cosine_similarity
        
        # Prepare embeddings matrices
        if progress_callback:
            progress_callback("clustering", 20, "Preparing embedding matrices")
        
        # Extract paper embeddings
        paper_embeddings = []
        valid_papers = []
        
        for paper in papers:
            embedding = paper.get('embedding')
            if not embedding:
                continue
                
            # Parse embedding if it's a string format
            if isinstance(embedding, str):
                try:
                    # Handle pgvector format [1,2,3] -> list
                    embedding_str = embedding.strip('[]')
                    embedding = [float(x) for x in embedding_str.split(',')]
                except:
                    continue
            
            paper_embeddings.append(embedding)
            valid_papers.append(paper)
        
        if not paper_embeddings:
            raise ValueError("No valid paper embeddings found")
        
        # Extract research interest embeddings  
        interest_embeddings = [ri['embedding'] for ri in research_interests]
        
        # Convert to numpy arrays
        paper_matrix = np.array(paper_embeddings)
        interest_matrix = np.array(interest_embeddings)
        
        if progress_callback:
            progress_callback("clustering", 40, f"Computing similarity matrix ({paper_matrix.shape[0]} x {interest_matrix.shape[0]})")
        
        # Compute cosine similarity matrix
        similarity_matrix = cosine_similarity(paper_matrix, interest_matrix)
        
        # Extract relationships above threshold
        relationships = []
        for paper_idx, paper in enumerate(valid_papers):
            paper_id = paper['id']
            
            for interest_idx, research_interest in enumerate(research_interests):
                interest_id = research_interest['id']
                similarity_score = float(similarity_matrix[paper_idx, interest_idx])
                
                # Only include relationships above threshold
                if similarity_score >= self.similarity_threshold:
                    relationships.append((paper_id, interest_id, similarity_score))
        
        if progress_callback:
            progress_callback("clustering", 80, f"Found {len(relationships):,} paper-interest relationships above threshold ({self.similarity_threshold})")
        
        return relationships
    
    def save_paper_interest_relationships(self, 
                                        relationships: List[Tuple[int, int, float]],
                                        progress_callback: Optional[Callable] = None) -> int:
        """
        Save paper-research_interest relationships to database.
        
        Args:
            relationships: List of (paper_id, research_interest_id, similarity_score) tuples
            progress_callback: Optional progress callback
            
        Returns:
            Number of relationships saved
        """
        if progress_callback:
            progress_callback("saving_relationships", 10, f"Saving {len(relationships):,} paper-interest relationships")
        
        # Clear existing relationships for fresh clustering
        PaperResearchInterestsRepository.delete_all()
        
        # Bulk insert new relationships
        saved_count = PaperResearchInterestsRepository.bulk_insert(relationships)
        
        if progress_callback:
            progress_callback("saving_relationships", 90, f"Saved {saved_count:,} relationships")
        
        return saved_count
    
    def calculate_weekly_metrics(self, 
                               lookback_months: int = 24,
                               progress_callback: Optional[Callable] = None) -> None:
        """
        Calculate weekly temporal metrics for all research interests.
        
        Args:
            lookback_months: How many months back to analyze
            progress_callback: Optional progress callback
        """
        if progress_callback:
            progress_callback("weekly_metrics", 10, "Calculating weekly metrics for research interests")
        
        # Get all research interests
        research_interests = ResearchInterestsRepository.get_all()
        if not research_interests:
            logger.warning("No research interests found for temporal analysis")
            return
        
        # Calculate date ranges
        end_date = date.today()
        start_date = end_date - timedelta(days=lookback_months * 30)
        
        # Clear existing weekly metrics
        ResearchInterestMetricsRepository.delete_for_period_type("week")
        
        for i, research_interest in enumerate(research_interests):
            interest_id = research_interest['id']
            interest_text = research_interest['interest_text']
            
            if progress_callback:
                progress_callback("weekly_metrics", 10 + (i * 80) // len(research_interests), 
                                f"Processing interest {i+1}/{len(research_interests)}: {interest_text[:50]}...")
            
            # Get papers for this research interest
            papers = PaperResearchInterestsRepository.get_papers_for_interest(interest_id, limit=5000)
            if not papers:
                continue
            
            # Group papers by week
            weekly_counts = defaultdict(list)
            for paper in papers:
                paper_date = paper['date']
                if isinstance(paper_date, str):
                    paper_date = datetime.strptime(paper_date, '%Y-%m-%d').date()
                
                if paper_date < start_date:
                    continue
                
                # Get start of week (Monday)
                days_since_monday = paper_date.weekday()
                week_start = paper_date - timedelta(days=days_since_monday)
                week_end = week_start + timedelta(days=6)
                
                week_key = (week_start, week_end)
                weekly_counts[week_key].append(paper)
            
            # Sort weeks chronologically
            sorted_weeks = sorted(weekly_counts.items(), key=lambda x: x[0][0])
            
            # Calculate metrics for each week and save
            previous_count = 0
            for (week_start, week_end), week_papers in sorted_weeks:
                doc_count = len(week_papers)
                
                # Calculate average similarity and paper scores
                similarity_scores = [p['similarity_score'] for p in week_papers]
                paper_scores = [p['score'] for p in week_papers if p.get('score') is not None]
                
                avg_relevance_score = np.mean(similarity_scores) if similarity_scores else None
                avg_paper_score = np.mean(paper_scores) if paper_scores else None
                
                # Calculate growth rate
                growth_rate = None
                if previous_count > 0:
                    growth_rate = (doc_count - previous_count) / previous_count
                
                # Save metrics
                ResearchInterestMetricsRepository.insert(
                    research_interest_id=interest_id,
                    period_start=week_start,
                    period_end=week_end,
                    period_type="week",
                    doc_count=doc_count,
                    avg_relevance_score=float(avg_relevance_score) if avg_relevance_score is not None else None,
                    avg_paper_score=float(avg_paper_score) if avg_paper_score is not None else None,
                    growth_rate=growth_rate
                )
                
                previous_count = doc_count
    
    def aggregate_weekly_data(self, 
                            target_period: str = "month",
                            duration_months: int = 6,
                            progress_callback: Optional[Callable] = None) -> None:
        """
        Aggregate weekly metrics into monthly or quarterly views.
        
        Args:
            target_period: 'month' or 'quarter' to aggregate to
            duration_months: How many months of data to aggregate
            progress_callback: Optional progress callback
        """
        if progress_callback:
            progress_callback("aggregation", 10, f"Aggregating weekly data to {target_period} for research interests")
        
        # Get all research interests
        research_interests = ResearchInterestsRepository.get_all()
        if not research_interests:
            logger.warning("No research interests found for aggregation")
            return
        
        # Calculate date range
        end_date = date.today()
        start_date = end_date - timedelta(days=duration_months * 30)
        
        # Clear existing aggregated data
        ResearchInterestMetricsRepository.delete_for_period_type(target_period)
        
        for i, research_interest in enumerate(research_interests):
            interest_id = research_interest['id']
            
            if progress_callback:
                progress_callback("aggregation", 10 + (i * 80) // len(research_interests), 
                                f"Aggregating interest {i+1}/{len(research_interests)}")
            
            # Get weekly metrics
            weekly_metrics = ResearchInterestMetricsRepository.get_interest_timeline(
                interest_id, "week", limit=duration_months * 5
            )
            
            if not weekly_metrics:
                continue
            
            # Group weekly data by target period
            period_groups = defaultdict(list)
            for metric in weekly_metrics:
                metric_date = metric['period_start']
                if isinstance(metric_date, str):
                    metric_date = datetime.strptime(metric_date, '%Y-%m-%d').date()
                
                if metric_date < start_date:
                    continue
                
                # Calculate target period
                if target_period == "month":
                    period_start = metric_date.replace(day=1)
                    if period_start.month == 12:
                        period_end = period_start.replace(year=period_start.year + 1, month=1) - timedelta(days=1)
                    else:
                        period_end = period_start.replace(month=period_start.month + 1) - timedelta(days=1)
                else:  # quarter
                    quarter = (metric_date.month - 1) // 3 + 1
                    period_start = metric_date.replace(month=(quarter - 1) * 3 + 1, day=1)
                    if quarter == 4:
                        period_end = period_start.replace(year=period_start.year + 1, month=1) - timedelta(days=1)
                    else:
                        period_end = period_start.replace(month=quarter * 3 + 1) - timedelta(days=1)
                
                period_key = (period_start, period_end)
                period_groups[period_key].append(metric)
            
            # Calculate aggregated metrics
            sorted_periods = sorted(period_groups.items(), key=lambda x: x[0][0])
            previous_count = 0
            
            for (period_start, period_end), week_metrics in sorted_periods:
                total_doc_count = sum(m['doc_count'] for m in week_metrics)
                
                # Average the relevance and paper scores
                relevance_scores = [m['avg_relevance_score'] for m in week_metrics if m.get('avg_relevance_score') is not None]
                paper_scores = [m['avg_paper_score'] for m in week_metrics if m.get('avg_paper_score') is not None]
                
                avg_relevance_score = np.mean(relevance_scores) if relevance_scores else None
                avg_paper_score = np.mean(paper_scores) if paper_scores else None
                
                # Calculate growth rate
                growth_rate = None
                if previous_count > 0:
                    growth_rate = (total_doc_count - previous_count) / previous_count
                
                # Save aggregated metrics
                ResearchInterestMetricsRepository.insert(
                    research_interest_id=interest_id,
                    period_start=period_start,
                    period_end=period_end,
                    period_type=target_period,
                    doc_count=total_doc_count,
                    avg_relevance_score=float(avg_relevance_score) if avg_relevance_score is not None else None,
                    avg_paper_score=float(avg_paper_score) if avg_paper_score is not None else None,
                    growth_rate=growth_rate
                )
                
                previous_count = total_doc_count
    
    def generate_forecasts(self, 
                         period_type: str = "week",
                         progress_callback: Optional[Callable] = None,
                         run_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate forecasts for research interests using Prophet.
        
        Args:
            period_type: Period type to use for forecasting
            progress_callback: Optional progress callback
            run_id: Run ID for logging
            
        Returns:
            Dictionary with forecasting results
        """
        if progress_callback:
            progress_callback("forecasting", 10, f"Generating forecasts for research interests ({period_type})")
        
        research_interests = ResearchInterestsRepository.get_all()
        if not research_interests:
            return {"error": "No research interests found for forecasting"}
        
        forecast_results = {
            "interests_processed": 0,
            "interests_with_forecasts": 0,
            "total_forecasts_generated": 0,
            "errors": []
        }
        
        for i, research_interest in enumerate(research_interests):
            interest_id = research_interest['id']
            interest_text = research_interest['interest_text']
            
            if progress_callback:
                progress_callback("forecasting", 10 + (i * 80) // len(research_interests), 
                                f"Forecasting interest {i+1}/{len(research_interests)}: {interest_text[:30]}...")
            
            try:
                # Get historical metrics
                metrics = ResearchInterestMetricsRepository.get_interest_timeline(interest_id, period_type, limit=52)
                
                if len(metrics) < 8:  # Need at least 8 data points for Prophet
                    continue
                
                # Prepare data for Prophet
                df_data = []
                for metric in reversed(metrics):  # Prophet expects chronological order
                    df_data.append({
                        'ds': metric['period_start'],
                        'y': metric['doc_count']
                    })
                
                df = pd.DataFrame(df_data)
                
                # Initialize and fit Prophet model
                model = Prophet(
                    yearly_seasonality=True,
                    weekly_seasonality=False,
                    daily_seasonality=False,
                    changepoint_prior_scale=0.05
                )
                
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    model.fit(df)
                
                # Generate forecasts
                if period_type == "week":
                    periods = [4, 12, 24]  # 1M, 3M, 6M in weeks
                elif period_type == "month":
                    periods = [1, 3, 6]  # 1M, 3M, 6M in months
                else:  # quarter
                    periods = [1, 2, 4]  # 3M, 6M, 12M in quarters
                
                forecasts = {}
                for period in periods:
                    future = model.make_future_dataframe(periods=period, freq='W' if period_type == 'week' else 'M')
                    forecast = model.predict(future)
                    forecasts[f"{period}"] = max(0, int(forecast.iloc[-1]['yhat']))
                
                # Update the latest metric with forecasts
                latest_metrics = ResearchInterestMetricsRepository.get_interest_timeline(interest_id, period_type, limit=1)
                if latest_metrics:
                    latest_metric = latest_metrics[0]
                    ResearchInterestMetricsRepository.insert(
                        research_interest_id=interest_id,
                        period_start=latest_metric['period_start'],
                        period_end=latest_metric['period_end'],
                        period_type=period_type,
                        doc_count=latest_metric['doc_count'],
                        avg_relevance_score=latest_metric.get('avg_relevance_score'),
                        avg_paper_score=latest_metric.get('avg_paper_score'),
                        growth_rate=latest_metric.get('growth_rate'),
                        forecast_1m=forecasts.get("1" if period_type == "month" else "4"),
                        forecast_3m=forecasts.get("3" if period_type == "month" else "12"),
                        forecast_6m=forecasts.get("6" if period_type == "month" else "24")
                    )
                
                forecast_results["interests_with_forecasts"] += 1
                forecast_results["total_forecasts_generated"] += len(forecasts)
                
            except Exception as e:
                error_msg = f"Error forecasting interest {interest_id}: {str(e)}"
                forecast_results["errors"].append(error_msg)
                if run_id:
                    self.metrics_logger.log_error(run_id, f"forecast_interest_{interest_id}", error_msg)
            
            forecast_results["interests_processed"] += 1
        
        return forecast_results
    
    def run_full_pipeline(self, 
                         lookback_months: int = 24,
                         duration_months: int = 6,
                         min_papers: int = 100,
                         similarity_threshold: Optional[float] = None,
                         progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """
        Run the complete research interest clustering pipeline.
        
        Args:
            lookback_months: How many months of historical data to analyze
            duration_months: Duration for current analysis views
            min_papers: Minimum number of papers required to run
            similarity_threshold: Override the default similarity threshold
            progress_callback: Optional progress callback
            
        Returns:
            Dictionary with processing results
        """
        start_time = datetime.now()
        
        if similarity_threshold is not None:
            self.similarity_threshold = similarity_threshold
        
        # Generate run ID for logging
        run_id = str(uuid.uuid4())
        
        # Start logging
        self.metrics_logger.log_pipeline_start({
            'analysis_type': 'research_interest_clustering',
            'lookback_months': lookback_months,
            'duration_months': duration_months,
            'min_papers': min_papers,
            'similarity_threshold': self.similarity_threshold
        })
        
        pipeline_results = {
            'run_id': run_id,
            'success': False,
            'processing_time_seconds': 0.0,
            'research_interests_processed': 0,
            'papers_processed': 0,
            'relationships_created': 0,
            'lookback_months': lookback_months,
            'duration_months': duration_months,
            'similarity_threshold': self.similarity_threshold,
            'forecast_results': {},
            'errors': []
        }
        
        try:
            # Step 1: Setup research interests from settings
            if progress_callback:
                progress_callback("setup", 5, "Setting up research interests from settings")
            
            research_interests = self.setup_research_interests(progress_callback)
            pipeline_results['research_interests_processed'] = len(research_interests)
            
            # Step 2: Get papers with embeddings
            if progress_callback:
                progress_callback("data_loading", 15, "Loading papers with embeddings")
            
            cutoff_date = (datetime.now() - timedelta(days=lookback_months * 30)).date()
            from ..data_access import PaperRepository
            all_papers = PaperRepository.get_papers_with_embeddings(limit=100000)
            papers = [p for p in all_papers if p.get('date') and 
                     (isinstance(p['date'], date) and p['date'] >= cutoff_date or
                      isinstance(p['date'], str) and datetime.strptime(p['date'], '%Y-%m-%d').date() >= cutoff_date)]
            
            if len(papers) < min_papers:
                error_msg = f"Insufficient papers for analysis: {len(papers)} < {min_papers}"
                pipeline_results['errors'].append(error_msg)
                raise ValueError(error_msg)
            
            pipeline_results['papers_processed'] = len(papers)
            
            # Step 3: Cluster papers against research interests
            if progress_callback:
                progress_callback("clustering", 25, f"Clustering {len(papers):,} papers against research interests")
            
            relationships = self.cluster_papers_by_research_interests(papers, research_interests, progress_callback)
            
            # Step 4: Save relationships
            if progress_callback:
                progress_callback("saving", 40, "Saving paper-interest relationships")
            
            saved_count = self.save_paper_interest_relationships(relationships, progress_callback)
            pipeline_results['relationships_created'] = saved_count
            
            # Step 5: Calculate weekly metrics
            if progress_callback:
                progress_callback("weekly_metrics", 50, "Calculating weekly metrics")
            
            self.calculate_weekly_metrics(lookback_months, progress_callback)
            
            # Step 6: Aggregate to monthly/quarterly views
            if progress_callback:
                progress_callback("aggregation", 70, "Aggregating to monthly view")
            
            self.aggregate_weekly_data("month", duration_months, progress_callback)
            
            if duration_months >= 6:
                if progress_callback:
                    progress_callback("aggregation", 75, "Aggregating to quarterly view")
                self.aggregate_weekly_data("quarter", duration_months, progress_callback)
            
            # Step 7: Generate forecasts
            if progress_callback:
                progress_callback("forecasting", 85, "Generating forecasts")
            
            forecast_results = self.generate_forecasts("week", progress_callback, run_id)
            pipeline_results['forecast_results'] = forecast_results
            
            # Success
            pipeline_results['success'] = True
            pipeline_results['processing_time_seconds'] = (datetime.now() - start_time).total_seconds()
            
            if progress_callback:
                progress_callback("completion", 100, f"✅ Research interest clustering completed successfully!")
            
            # Log completion
            self.metrics_logger.log_pipeline_completion(run_id, pipeline_results['processing_time_seconds'], {
                'research_interests': len(research_interests),
                'papers_processed': len(papers),
                'relationships_created': saved_count,
                'forecast_results': forecast_results
            })
            
        except Exception as e:
            error_msg = f"Pipeline failed: {str(e)}"
            pipeline_results['errors'].append(error_msg)
            self.metrics_logger.log_error(run_id, "pipeline_failure", error_msg)
            logger.error(f"Research interest clustering pipeline failed: {e}")
        
        return pipeline_results 