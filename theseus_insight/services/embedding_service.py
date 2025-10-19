"""Streaming embedding service for memory-efficient bulk processing.

This module provides a unified service for generating embeddings on large datasets
with constant memory usage, checkpointing, and GPU optimization.
"""

import gc
import json
import logging
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Callable
from pathlib import Path
from uuid import UUID, uuid4

import torch

from ..data_access.papers import PaperRepository
from ..inference import SentenceTransformerInference
from ..db import get_cursor


logger = logging.getLogger(__name__)


@dataclass
class EmbeddingServiceConfig:
    """Configuration for streaming embedding service."""
    
    # Processing
    chunk_size: int = 10000  # Papers per chunk
    gpu_batch_size: int = 512  # Papers per GPU batch (will be auto-tuned if enabled)
    auto_tune_batch_size: bool = True  # Auto-optimize for hardware
    
    # Memory & Performance
    db_flush_interval: int = 1000  # Write to DB every N papers
    checkpoint_interval: int = 10000  # Save checkpoint every N papers
    max_retry_attempts: int = 3  # Retry failed papers
    
    # Progress & Monitoring
    progress_report_interval: int = 100  # Callback frequency
    verbose: bool = True
    
    # Model
    model_name: str = "Alibaba-NLP/gte-large-en-v1.5"
    device: str = "auto"  # "cuda", "mps", "cpu", or "auto"
    trust_remote_code: bool = True
    
    # Checkpoint settings
    checkpoint_dir: str = "data/checkpoints/embeddings"
    job_timeout_hours: int = 24  # Jobs inactive for this long are considered hung


class EmbeddingJobCheckpoint:
    """Manages checkpoints for embedding jobs."""
    
    def __init__(self, checkpoint_dir: str = "data/checkpoints/embeddings"):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
    
    def save(
        self,
        job_id: UUID,
        operation: str,
        parameters: Dict[str, Any],
        progress: Dict[str, Any],
        statistics: Dict[str, Any]
    ):
        """Save checkpoint for a job."""
        checkpoint_data = {
            "job_id": str(job_id),
            "operation": operation,
            "parameters": parameters,
            "progress": progress,
            "statistics": statistics,
            "last_updated": datetime.now().isoformat()
        }
        
        checkpoint_file = self.checkpoint_dir / f"{job_id}.json"
        
        # Atomic write: write to temp file, then rename
        temp_file = checkpoint_file.with_suffix('.tmp')
        try:
            with open(temp_file, 'w') as f:
                json.dump(checkpoint_data, f, indent=2)
            temp_file.rename(checkpoint_file)
        except Exception as e:
            logger.error(f"Failed to save checkpoint for job {job_id}: {e}")
            if temp_file.exists():
                temp_file.unlink()
            raise
    
    def load(self, job_id: UUID) -> Optional[Dict[str, Any]]:
        """Load checkpoint for a job."""
        checkpoint_file = self.checkpoint_dir / f"{job_id}.json"
        
        if not checkpoint_file.exists():
            return None
        
        try:
            with open(checkpoint_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load checkpoint for job {job_id}: {e}")
            return None
    
    def delete(self, job_id: UUID):
        """Delete checkpoint for a job."""
        checkpoint_file = self.checkpoint_dir / f"{job_id}.json"
        if checkpoint_file.exists():
            checkpoint_file.unlink()
    
    def list_jobs(self) -> List[Dict[str, Any]]:
        """List all checkpoint jobs."""
        jobs = []
        for checkpoint_file in self.checkpoint_dir.glob("*.json"):
            try:
                with open(checkpoint_file, 'r') as f:
                    data = json.load(f)
                    jobs.append(data)
            except Exception as e:
                logger.warning(f"Failed to load checkpoint {checkpoint_file}: {e}")
        return jobs
    
    def cleanup_hung_jobs(self, timeout_hours: int = 24) -> List[UUID]:
        """Clean up jobs that have been inactive for too long.
        
        Returns list of job IDs that were cleaned up.
        """
        cleaned_jobs = []
        cutoff_time = datetime.now() - timedelta(hours=timeout_hours)
        
        for job_data in self.list_jobs():
            try:
                last_updated = datetime.fromisoformat(job_data['last_updated'])
                if last_updated < cutoff_time:
                    job_id = UUID(job_data['job_id'])
                    self.delete(job_id)
                    cleaned_jobs.append(job_id)
                    logger.info(f"Cleaned up hung job {job_id} (inactive since {last_updated})")
            except Exception as e:
                logger.warning(f"Error cleaning up job: {e}")
        
        return cleaned_jobs


class StreamingEmbeddingService:
    """Memory-efficient streaming service for bulk embedding generation.
    
    This service processes papers in chunks to maintain constant memory usage
    regardless of dataset size. It supports checkpointing for resumability,
    GPU batch size optimization, and progress tracking.
    
    Example:
        ```python
        service = StreamingEmbeddingService()
        
        # Process papers in date range
        stats = await service.embed_papers_in_date_range(
            start_date="2024-01-01",
            end_date="2024-12-31",
            progress_callback=lambda current, total: print(f"{current}/{total}")
        )
        ```
    """
    
    def __init__(self, config: Optional[EmbeddingServiceConfig] = None):
        """Initialize the streaming embedding service.
        
        Args:
            config: Service configuration. If None, uses defaults.
        """
        self.config = config or EmbeddingServiceConfig()
        self.checkpoint_manager = EmbeddingJobCheckpoint(self.config.checkpoint_dir)
        self.embedding_model = None
        self._optimal_batch_size = None
    
    def _get_device(self) -> str:
        """Determine optimal device for embedding model."""
        if self.config.device != "auto":
            return self.config.device
        
        # Auto-detect best available device
        if torch.cuda.is_available():
            return "cuda"
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            return "mps"
        else:
            return "cpu"
    
    def _load_embedding_model(self):
        """Load embedding model (lazy initialization)."""
        if self.embedding_model is None:
            device = self._get_device()
            
            if self.config.verbose:
                logger.info(f"Loading embedding model: {self.config.model_name} on {device}")
            
            self.embedding_model = SentenceTransformerInference(
                self.config.model_name,
                remote_code=self.config.trust_remote_code,
                device=device
            )
            
            # Auto-tune batch size if enabled
            if self.config.auto_tune_batch_size:
                if self._optimal_batch_size is None:
                    logger.info("🎯 Running GPU batch size auto-tuning (first run)...")
                    self._optimal_batch_size = self._auto_tune_batch_size()
                    logger.info(f"✅ Auto-tuned optimal batch size: {self._optimal_batch_size}")
                else:
                    logger.info(f"📌 Using cached optimal batch size: {self._optimal_batch_size}")
        
        return self.embedding_model
    
    def _auto_tune_batch_size(self) -> int:
        """Automatically find optimal batch size for current hardware.
        
        Returns:
            Optimal batch size (256-2048)
        """
        logger.info("⚡ Testing batch sizes: [256, 512, 1024, 2048]")
        
        test_sizes = [256, 512, 1024, 2048]
        sample_texts = ["Sample abstract for testing embedding performance."] * 1000
        
        best_size = self.config.gpu_batch_size  # Default fallback
        best_throughput = 0
        results = []
        
        for size in test_sizes:
            try:
                start = time.time()
                
                # Test embedding generation
                _ = self.embedding_model.invoke(
                    sample_texts[:size*4],
                    batch_size=size,
                    show_progress_bar=False
                )
                
                duration = time.time() - start
                throughput = (size * 4) / duration
                results.append((size, throughput))
                
                logger.info(f"  📊 Batch size {size}: {throughput:.1f} texts/sec")
                
                if throughput > best_throughput:
                    best_throughput = throughput
                    best_size = size
                elif throughput < best_throughput * 0.95:
                    # Performance plateau - stop testing
                    logger.info(f"  ⏸️  Performance plateau detected, stopping tests")
                    break
                    
            except (torch.cuda.OutOfMemoryError, RuntimeError) as e:
                logger.info(f"  ⚠️  Batch size {size}: Out of memory, stopping tests")
                break
        
        logger.info(f"🏆 Selected batch size: {best_size} ({best_throughput:.1f} texts/sec)")
        
        return best_size
    
    async def embed_papers_in_date_range(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        job_id: Optional[UUID] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Dict[str, Any]:
        """Embed all papers missing embeddings in the specified date range.
        
        This method uses streaming/chunked processing to maintain constant memory
        usage regardless of dataset size.
        
        Args:
            start_date: Start date (YYYY-MM-DD, inclusive). None for no start limit.
            end_date: End date (YYYY-MM-DD, inclusive). None for no end limit.
            job_id: Optional job ID for checkpoint resumption. If None, creates new job.
            progress_callback: Optional callback(current_count, total_count) for progress updates.
            
        Returns:
            Statistics dictionary with:
                - total_papers: Total papers processed
                - papers_embedded: Successfully embedded papers
                - papers_failed: Failed papers
                - elapsed_seconds: Total time taken
                - papers_per_second: Throughput
        """
        job_id = job_id or uuid4()
        start_time = time.time()
        
        # Load embedding model
        self._load_embedding_model()
        batch_size = self._optimal_batch_size or self.config.gpu_batch_size
        
        # Check for existing checkpoint
        checkpoint = self.checkpoint_manager.load(job_id)
        offset = 0
        
        if checkpoint:
            offset = checkpoint['progress'].get('offset', 0)
            if self.config.verbose:
                logger.info(f"🔄 Resuming from checkpoint at offset {offset}")
        
        # Get total count for progress tracking
        total_papers = PaperRepository.count_papers_missing_embeddings_in_date_range(
            start_date=start_date,
            end_date=end_date
        )
        
        if total_papers == 0:
            if self.config.verbose:
                logger.info("✅ No papers need embeddings")
            return {
                "total_papers": 0,
                "papers_embedded": 0,
                "papers_failed": 0,
                "elapsed_seconds": 0,
                "papers_per_second": 0
            }
        
        if self.config.verbose:
            logger.info(f"🧠 Embedding {total_papers} papers in date range {start_date} to {end_date}")
            logger.info(f"⚙️  Chunk size: {self.config.chunk_size}, GPU batch size: {batch_size}")
        
        # Statistics
        stats = {
            "total_papers": total_papers,
            "papers_embedded": 0,
            "papers_failed": 0,
            "papers_processed": offset
        }
        
        # Process in chunks
        db_buffer = []  # Buffer for bulk DB writes
        
        while offset < total_papers:
            # Fetch chunk from database (paginated)
            chunk = PaperRepository.get_papers_missing_embeddings_in_date_range_paginated(
                start_date=start_date,
                end_date=end_date,
                limit=self.config.chunk_size,
                offset=offset
            )
            
            if not chunk:
                break  # No more papers
            
            if self.config.verbose:
                logger.info(f"📦 Processing chunk: {offset}-{offset+len(chunk)}/{total_papers}")
            
            # Generate embeddings for chunk
            abstracts = [p['abstract'] for p in chunk]
            paper_ids = [p['id'] for p in chunk]
            
            try:
                embeddings = self.embedding_model.invoke(
                    abstracts,
                    batch_size=batch_size,
                    show_progress_bar=False,
                    convert_to_numpy=True,
                    to_list=False
                )
                
                # Prepare updates
                for paper_id, embedding in zip(paper_ids, embeddings):
                    try:
                        vector = embedding.tolist() if hasattr(embedding, 'tolist') else list(embedding)
                        db_buffer.append((paper_id, vector))
                        stats['papers_embedded'] += 1
                    except Exception as e:
                        logger.error(f"Error preparing embedding for paper {paper_id}: {e}")
                        stats['papers_failed'] += 1
                
                # Flush to database periodically
                if len(db_buffer) >= self.config.db_flush_interval:
                    PaperRepository.bulk_update_embeddings(
                        db_buffer,
                        embedding_model=self.config.model_name
                    )
                    if self.config.verbose:
                        logger.info(f"💾 Flushed {len(db_buffer)} embeddings to DB")
                    db_buffer = []
                
            except Exception as e:
                logger.error(f"Error processing chunk at offset {offset}: {e}")
                stats['papers_failed'] += len(chunk)
            
            # Update progress
            offset += len(chunk)
            stats['papers_processed'] = offset
            
            # Progress callback
            if progress_callback and offset % self.config.progress_report_interval == 0:
                progress_callback(offset, total_papers)
            
            # Save checkpoint
            if offset % self.config.checkpoint_interval == 0:
                self.checkpoint_manager.save(
                    job_id=job_id,
                    operation="embed_date_range",
                    parameters={
                        "start_date": start_date,
                        "end_date": end_date,
                        "model_name": self.config.model_name
                    },
                    progress={
                        "total_papers": total_papers,
                        "processed_papers": offset,
                        "offset": offset
                    },
                    statistics=stats
                )
            
            # Clear memory for next chunk
            del chunk, abstracts, embeddings
            gc.collect()
        
        # Final flush of any remaining embeddings
        if db_buffer:
            PaperRepository.bulk_update_embeddings(
                db_buffer,
                embedding_model=self.config.model_name
            )
            if self.config.verbose:
                logger.info(f"💾 Final flush: {len(db_buffer)} embeddings to DB")
        
        # Calculate final statistics
        elapsed = time.time() - start_time
        stats['elapsed_seconds'] = elapsed
        stats['papers_per_second'] = stats['papers_embedded'] / elapsed if elapsed > 0 else 0
        
        # Final progress callback
        if progress_callback:
            progress_callback(total_papers, total_papers)
        
        # Clean up checkpoint
        self.checkpoint_manager.delete(job_id)
        
        if self.config.verbose:
            logger.info(f"✅ Embedding complete!")
            logger.info(f"📊 Processed {stats['papers_embedded']} papers in {elapsed:.1f}s")
            logger.info(f"⚡ Rate: {stats['papers_per_second']:.1f} papers/second")
            if stats['papers_failed'] > 0:
                logger.warning(f"❌ {stats['papers_failed']} papers failed")
        
        return stats
    
    async def embed_all_missing_papers(
        self,
        job_id: Optional[UUID] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Dict[str, Any]:
        """Embed all papers that are missing embeddings (no date range filter).
        
        Args:
            job_id: Optional job ID for checkpoint resumption.
            progress_callback: Optional callback(current_count, total_count) for progress updates.
            
        Returns:
            Statistics dictionary
        """
        return await self.embed_papers_in_date_range(
            start_date=None,
            end_date=None,
            job_id=job_id,
            progress_callback=progress_callback
        )
    
    async def resume_from_checkpoint(
        self,
        job_id: UUID,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Dict[str, Any]:
        """Resume an embedding job from checkpoint.
        
        Args:
            job_id: Job ID to resume
            progress_callback: Optional progress callback
            
        Returns:
            Statistics dictionary
            
        Raises:
            ValueError: If checkpoint not found
        """
        checkpoint = self.checkpoint_manager.load(job_id)
        if not checkpoint:
            raise ValueError(f"No checkpoint found for job {job_id}")
        
        if self.config.verbose:
            logger.info(f"🔄 Resuming job {job_id}")
            logger.info(f"Operation: {checkpoint['operation']}")
            logger.info(f"Progress: {checkpoint['progress']['processed_papers']}/{checkpoint['progress']['total_papers']}")
        
        # Resume based on operation type
        operation = checkpoint['operation']
        params = checkpoint['parameters']
        
        if operation == "embed_date_range":
            return await self.embed_papers_in_date_range(
                start_date=params.get('start_date'),
                end_date=params.get('end_date'),
                job_id=job_id,
                progress_callback=progress_callback
            )
        else:
            raise ValueError(f"Unknown operation type: {operation}")
    
    def cleanup_hung_jobs(self) -> List[UUID]:
        """Clean up jobs that have been inactive for too long.
        
        Returns:
            List of job IDs that were cleaned up
        """
        return self.checkpoint_manager.cleanup_hung_jobs(
            timeout_hours=self.config.job_timeout_hours
        )
    
    def list_active_jobs(self) -> List[Dict[str, Any]]:
        """List all active embedding jobs with checkpoints.
        
        Returns:
            List of job information dictionaries
        """
        return self.checkpoint_manager.list_jobs()
    
    def get_job_status(self, job_id: UUID) -> Optional[Dict[str, Any]]:
        """Get status of a specific job.
        
        Args:
            job_id: Job ID to check
            
        Returns:
            Job information dictionary or None if not found
        """
        return self.checkpoint_manager.load(job_id)


