"""
Memory-efficient batch processing pipeline for large datasets.

This module implements memory-efficient techniques for processing millions of papers
without running out of memory.
"""

import os
import gc
import psutil
import warnings
from typing import Iterator, List, Dict, Any, Optional, Tuple
import pandas as pd
import numpy as np
from pathlib import Path
import tempfile
import shutil
from tqdm import tqdm

from theseus_insight.data_access import PaperRepository
from theseus_insight.data_access.bulk_operations import BulkImporter


class MemoryMonitor:
    """Monitor memory usage and trigger cleanup when needed."""
    
    def __init__(self, threshold_percent: float = 80.0, verbose: bool = True):
        """
        Initialize memory monitor.
        
        Args:
            threshold_percent: Memory usage percentage to trigger cleanup
            verbose: Whether to print memory statistics
        """
        self.threshold_percent = threshold_percent
        self.verbose = verbose
        self.initial_memory = self.get_memory_usage()
        
    def get_memory_usage(self) -> Dict[str, float]:
        """Get current memory usage statistics."""
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        
        return {
            'rss_gb': memory_info.rss / (1024 ** 3),  # Resident Set Size in GB
            'vms_gb': memory_info.vms / (1024 ** 3),  # Virtual Memory Size in GB
            'percent': process.memory_percent(),
            'available_gb': psutil.virtual_memory().available / (1024 ** 3)
        }
    
    def check_memory(self, force_gc: bool = False) -> bool:
        """
        Check memory usage and trigger garbage collection if needed.
        
        Returns:
            True if memory was cleaned, False otherwise
        """
        current = self.get_memory_usage()
        
        if force_gc or current['percent'] > self.threshold_percent:
            if self.verbose:
                print(f"⚠️ Memory usage at {current['percent']:.1f}%, triggering cleanup...")
            
            # Force garbage collection
            gc.collect()
            
            # Get usage after cleanup
            after = self.get_memory_usage()
            
            if self.verbose:
                freed = current['rss_gb'] - after['rss_gb']
                print(f"✅ Freed {freed:.2f} GB (now at {after['percent']:.1f}%)")
            
            return True
        
        return False
    
    def report(self):
        """Print memory usage report."""
        if not self.verbose:
            return
        
        current = self.get_memory_usage()
        used = current['rss_gb'] - self.initial_memory['rss_gb']
        
        print(f"\n📊 Memory Report:")
        print(f"  Initial: {self.initial_memory['rss_gb']:.2f} GB")
        print(f"  Current: {current['rss_gb']:.2f} GB")
        print(f"  Used: {used:.2f} GB")
        print(f"  Available: {current['available_gb']:.2f} GB")


class ChunkedDataProcessor:
    """Process large datasets in memory-efficient chunks."""
    
    def __init__(
        self,
        chunk_size: int = 10000,
        temp_dir: Optional[str] = None,
        memory_threshold: float = 80.0,
        verbose: bool = True
    ):
        """
        Initialize chunked processor.
        
        Args:
            chunk_size: Number of records to process at once
            temp_dir: Directory for temporary files (auto-created if None)
            memory_threshold: Memory usage percentage to trigger cleanup
            verbose: Whether to show progress
        """
        self.chunk_size = chunk_size
        self.verbose = verbose
        self.memory_monitor = MemoryMonitor(memory_threshold, verbose)
        
        # Setup temporary directory
        if temp_dir:
            self.temp_dir = Path(temp_dir)
            self.temp_dir.mkdir(parents=True, exist_ok=True)
            self._cleanup_temp = False
        else:
            self.temp_dir = Path(tempfile.mkdtemp(prefix="theseus_chunk_"))
            self._cleanup_temp = True
    
    def __del__(self):
        """Cleanup temporary directory if we created it."""
        if hasattr(self, '_cleanup_temp') and self._cleanup_temp and hasattr(self, 'temp_dir'):
            try:
                shutil.rmtree(self.temp_dir)
            except:
                pass
    
    def process_dataframe_chunks(
        self,
        df: pd.DataFrame,
        process_func: callable,
        output_columns: List[str],
        **kwargs
    ) -> pd.DataFrame:
        """
        Process a large DataFrame in chunks.
        
        Args:
            df: Input DataFrame
            process_func: Function to process each chunk
            output_columns: Expected output columns
            **kwargs: Additional arguments for process_func
            
        Returns:
            Processed DataFrame
        """
        total_rows = len(df)
        
        if total_rows <= self.chunk_size:
            # Small enough to process in one go
            return process_func(df, **kwargs)
        
        if self.verbose:
            print(f"📦 Processing {total_rows} rows in chunks of {self.chunk_size}")
        
        # Process in chunks and save to temporary files
        chunk_files = []
        
        for chunk_idx, start_idx in enumerate(
            tqdm(range(0, total_rows, self.chunk_size), 
                 desc="Processing chunks", 
                 disable=not self.verbose)
        ):
            end_idx = min(start_idx + self.chunk_size, total_rows)
            chunk_df = df.iloc[start_idx:end_idx]
            
            # Process chunk
            processed_chunk = process_func(chunk_df.copy(), **kwargs)
            
            # Save to temporary file
            chunk_file = self.temp_dir / f"chunk_{chunk_idx:06d}.parquet"
            processed_chunk.to_parquet(chunk_file, compression='snappy')
            chunk_files.append(chunk_file)
            
            # Free memory
            del chunk_df
            del processed_chunk
            
            # Check memory
            self.memory_monitor.check_memory()
        
        # Combine chunks
        if self.verbose:
            print("🔄 Combining processed chunks...")
        
        result_df = self._combine_chunk_files(chunk_files, output_columns)
        
        # Cleanup chunk files
        for chunk_file in chunk_files:
            chunk_file.unlink()
        
        return result_df
    
    def _combine_chunk_files(
        self,
        chunk_files: List[Path],
        expected_columns: List[str]
    ) -> pd.DataFrame:
        """Combine chunk files into a single DataFrame."""
        chunks = []
        
        for chunk_file in tqdm(chunk_files, desc="Loading chunks", disable=not self.verbose):
            chunk = pd.read_parquet(chunk_file)
            chunks.append(chunk)
            
            # Combine in batches to avoid memory issues
            if len(chunks) >= 10:
                chunks = [pd.concat(chunks, ignore_index=True)]
                self.memory_monitor.check_memory()
        
        # Final combination
        result = pd.concat(chunks, ignore_index=True)
        
        # Ensure all expected columns exist
        for col in expected_columns:
            if col not in result.columns:
                result[col] = None
        
        return result
    
    def stream_large_csv(
        self,
        csv_path: str,
        process_func: callable,
        date_column: Optional[str] = None,
        date_range: Optional[Tuple[str, str]] = None,
        **kwargs
    ) -> Iterator[pd.DataFrame]:
        """
        Stream process a large CSV file.
        
        Args:
            csv_path: Path to CSV file
            process_func: Function to process each chunk
            date_column: Column name for date filtering
            date_range: Optional (start_date, end_date) tuple
            **kwargs: Additional arguments for process_func
            
        Yields:
            Processed DataFrame chunks
        """
        # Determine if we need date filtering
        filter_dates = date_column and date_range
        
        if self.verbose:
            print(f"📖 Streaming CSV file: {csv_path}")
            if filter_dates:
                print(f"📅 Filtering dates: {date_range[0]} to {date_range[1]}")
        
        # Read CSV in chunks
        chunk_iter = pd.read_csv(
            csv_path,
            chunksize=self.chunk_size,
            dtype='str',  # Read as strings to avoid type inference overhead
            low_memory=False
        )
        
        processed_count = 0
        
        for chunk_idx, chunk in enumerate(chunk_iter):
            # Apply date filtering if needed
            if filter_dates:
                chunk[date_column] = pd.to_datetime(chunk[date_column], errors='coerce')
                mask = (chunk[date_column] >= date_range[0]) & (chunk[date_column] <= date_range[1])
                chunk = chunk[mask]
                
                if chunk.empty:
                    continue
            
            # Process chunk
            processed_chunk = process_func(chunk, **kwargs)
            processed_count += len(processed_chunk)
            
            yield processed_chunk
            
            # Memory management
            if chunk_idx % 10 == 0:
                self.memory_monitor.check_memory()
        
        if self.verbose:
            print(f"✅ Processed {processed_count} records from CSV")


class EfficientBulkProcessor:
    """
    Efficient bulk processing with minimal memory footprint.
    """
    
    def __init__(
        self,
        batch_size: int = 1000,
        use_staging: bool = True,
        memory_threshold: float = 80.0,
        verbose: bool = True
    ):
        """
        Initialize bulk processor.
        
        Args:
            batch_size: Number of records to accumulate before flushing
            use_staging: Whether to use staging tables
            memory_threshold: Memory usage percentage to trigger cleanup
            verbose: Whether to show progress
        """
        self.batch_size = batch_size
        self.use_staging = use_staging
        self.verbose = verbose
        self.memory_monitor = MemoryMonitor(memory_threshold, verbose)
        
        # Initialize bulk importer if using staging
        self.bulk_importer = BulkImporter() if use_staging else None
        
        # Buffers for different data types
        self.paper_buffer = []
        self.embedding_buffer = []
        self.score_buffer = []
        self.keyword_buffer = []
        
        # Statistics
        self.stats = {
            'papers_processed': 0,
            'embeddings_processed': 0,
            'scores_processed': 0,
            'flushes': 0
        }
    
    def add_paper(self, paper_data: Dict[str, Any]):
        """Add a paper to the buffer."""
        self.paper_buffer.append(paper_data)
        
        if len(self.paper_buffer) >= self.batch_size:
            self.flush_papers()
    
    def add_embedding(self, paper_id: int, embedding: List[float]):
        """Add an embedding to the buffer."""
        self.embedding_buffer.append((paper_id, embedding))
        
        if len(self.embedding_buffer) >= self.batch_size:
            self.flush_embeddings()
    
    def add_score(self, score_data: Dict[str, Any]):
        """Add a score to the buffer."""
        self.score_buffer.append(score_data)
        
        if len(self.score_buffer) >= self.batch_size:
            self.flush_scores()
    
    def flush_papers(self):
        """Flush paper buffer to database."""
        if not self.paper_buffer:
            return
        
        try:
            if self.use_staging and self.bulk_importer:
                # Use staging tables
                for paper in self.paper_buffer:
                    self.bulk_importer.add_paper(
                        paper_id=paper.get('id'),
                        title=paper['title'],
                        abstract=paper['abstract'],
                        authors=paper.get('authors', []),
                        date=paper['date'],
                        url=paper['url'],
                        score=paper.get('score'),
                        related=paper.get('related'),
                        rationale=paper.get('rationale'),
                        cosine_similarity=paper.get('cosine_similarity'),
                        embedding_model=paper.get('embedding_model'),
                        embedding=paper.get('embedding'),
                        keywords=paper.get('keywords', [])
                    )
                
                # Commit staging data
                self.bulk_importer.commit()
            else:
                # Use regular inserts
                for paper in self.paper_buffer:
                    PaperRepository.insert(paper, skip_duplicates=True)
            
            self.stats['papers_processed'] += len(self.paper_buffer)
            self.paper_buffer = []
            self.stats['flushes'] += 1
            
        except Exception as e:
            if self.verbose:
                print(f"❌ Error flushing papers: {e}")
            raise
    
    def flush_embeddings(self):
        """Flush embedding buffer to database."""
        if not self.embedding_buffer:
            return
        
        try:
            # Use bulk update with default model name (this pipeline doesn't track which model was used)
            PaperRepository.bulk_update_embeddings(self.embedding_buffer)
            
            self.stats['embeddings_processed'] += len(self.embedding_buffer)
            self.embedding_buffer = []
            
        except Exception as e:
            if self.verbose:
                print(f"❌ Error flushing embeddings: {e}")
            raise
    
    def flush_scores(self):
        """Flush score buffer to database."""
        if not self.score_buffer:
            return
        
        try:
            from theseus_insight.data_access.profiles import ProfileScoreRepository
            ProfileScoreRepository.bulk_create_or_update_scores(self.score_buffer)
            
            self.stats['scores_processed'] += len(self.score_buffer)
            self.score_buffer = []
            
        except Exception as e:
            if self.verbose:
                print(f"❌ Error flushing scores: {e}")
            raise
    
    def flush_all(self):
        """Flush all buffers."""
        self.flush_papers()
        self.flush_embeddings()
        self.flush_scores()
        
        # Check memory after flush
        self.memory_monitor.check_memory()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get processing statistics."""
        stats = self.stats.copy()
        stats['memory'] = self.memory_monitor.get_memory_usage()
        return stats


def optimize_dataframe_memory(df: pd.DataFrame, verbose: bool = True) -> pd.DataFrame:
    """
    Optimize DataFrame memory usage by downcasting types.
    
    Args:
        df: Input DataFrame
        verbose: Whether to print optimization results
        
    Returns:
        Optimized DataFrame
    """
    if verbose:
        start_mem = df.memory_usage(deep=True).sum() / 1024**2
        print(f"🔧 Optimizing DataFrame memory usage ({start_mem:.1f} MB)...")
    
    # Optimize numeric columns
    for col in df.select_dtypes(include=['int']).columns:
        df[col] = pd.to_numeric(df[col], downcast='integer')
    
    for col in df.select_dtypes(include=['float']).columns:
        df[col] = pd.to_numeric(df[col], downcast='float')
    
    # Optimize object columns
    for col in df.select_dtypes(include=['object']).columns:
        num_unique = df[col].nunique()
        num_total = len(df[col])
        
        # Convert to category if less than 50% unique values
        if num_unique / num_total < 0.5:
            df[col] = df[col].astype('category')
    
    if verbose:
        end_mem = df.memory_usage(deep=True).sum() / 1024**2
        reduction = (start_mem - end_mem) / start_mem * 100
        print(f"✅ Memory reduced by {reduction:.1f}% ({end_mem:.1f} MB)")
    
    return df