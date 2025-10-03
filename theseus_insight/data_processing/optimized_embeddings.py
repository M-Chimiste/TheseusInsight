"""
Optimized embedding generation pipeline that maximizes GPU utilization.

This module implements efficient batching and I/O overlap to ensure the
embedding model is never idle waiting for data.
"""

import time
import queue
import threading
from typing import List, Dict, Optional, Tuple
import numpy as np
from tqdm import tqdm

from theseus_insight.inference import SentenceTransformerInference
from theseus_insight.data_access import PaperRepository
from theseus_insight.data_access.bulk_operations import BulkImporter


class OptimizedEmbeddingPipeline:
    """
    Optimized embedding pipeline that overlaps I/O with computation.
    
    Key optimizations:
    - Large batch sizes for maximum GPU utilization
    - Producer thread pre-fetches data while GPU is processing
    - Consumer thread writes results while GPU processes next batch
    - Memory-efficient streaming to handle large datasets
    """
    
    def __init__(
        self,
        embedding_model: SentenceTransformerInference,
        batch_size: int = 1024,  # Larger batches for better GPU utilization
        prefetch_size: int = 2,   # Number of batches to prefetch
        checkpoint_interval: int = 5000
    ):
        """
        Initialize the optimized embedding pipeline.
        
        Args:
            embedding_model: Pre-initialized SentenceTransformer model
            batch_size: Number of papers to process in each GPU batch
            prefetch_size: Number of batches to prefetch from database
            checkpoint_interval: How often to checkpoint progress
        """
        self.embedding_model = embedding_model
        self.batch_size = batch_size
        self.prefetch_size = prefetch_size
        self.checkpoint_interval = checkpoint_interval
        
        # Queues for producer-consumer pattern
        self.input_queue = queue.Queue(maxsize=prefetch_size)
        self.output_queue = queue.Queue(maxsize=prefetch_size)
        
        # Thread control
        self._stop_event = threading.Event()
        
    def process_papers_without_embeddings(
        self,
        research_interests: Optional[str] = None,
        cosine_threshold: Optional[float] = None,
        use_bulk_operations: bool = True,
        verbose: bool = True
    ) -> Dict[str, any]:
        """
        Process all papers without embeddings using optimized pipeline.
        
        Args:
            research_interests: Optional research interests for similarity calculation
            cosine_threshold: Optional threshold for filtering papers by similarity
            use_bulk_operations: Whether to use bulk database operations
            verbose: Whether to show progress information
            
        Returns:
            Dictionary with processing statistics
        """
        start_time = time.time()
        stats = {
            'papers_processed': 0,
            'batches_processed': 0,
            'errors': 0,
            'skipped_low_similarity': 0
        }
        
        # Get research interests embedding if provided
        research_embedding = None
        if research_interests:
            if verbose:
                print("🎯 Embedding research interests...")
            research_embedding = self.embedding_model.invoke(research_interests)
            if hasattr(research_embedding, 'cpu'):
                research_embedding = research_embedding.cpu().numpy()
        
        # Get total count for progress bar
        papers_without_embeddings = PaperRepository.get_papers_without_embeddings()
        total_papers = len(papers_without_embeddings)
        
        if total_papers == 0:
            if verbose:
                print("✅ All papers already have embeddings!")
            return stats
        
        if verbose:
            print(f"📄 Found {total_papers} papers without embeddings")
            print(f"⚡ Using batch size: {self.batch_size}")
            print(f"🔄 Prefetching {self.prefetch_size} batches")
        
        # Start producer thread (fetches papers from DB)
        producer = threading.Thread(
            target=self._data_producer,
            args=(papers_without_embeddings,)
        )
        producer.start()
        
        # Start consumer thread (writes embeddings to DB)
        consumer = threading.Thread(
            target=self._result_consumer,
            args=(use_bulk_operations, verbose, stats)
        )
        consumer.start()
        
        # Main thread: Process embeddings
        pbar = tqdm(total=total_papers, desc="Generating embeddings") if verbose else None
        
        try:
            while True:
                # Get batch from input queue
                batch_data = self.input_queue.get()
                if batch_data is None:  # End signal
                    self.output_queue.put(None)
                    break
                
                batch_papers, batch_ids = batch_data
                
                # Extract abstracts
                abstracts = [p['abstract'] for p in batch_papers]
                
                try:
                    # Generate embeddings (this is the GPU-bound operation)
                    embeddings = self.embedding_model.invoke(
                        abstracts,
                        batch_size=min(len(abstracts), 256),  # Sub-batch if needed
                        show_progress_bar=False,
                        convert_to_numpy=True
                    )
                    
                    # Process results
                    results = []
                    for idx, (paper_id, embedding) in enumerate(zip(batch_ids, embeddings)):
                        result = {
                            'paper_id': paper_id,
                            'embedding': embedding
                        }
                        
                        # Calculate similarity if research interests provided
                        if research_embedding is not None:
                            similarity = self._cosine_similarity(embedding, research_embedding)
                            result['similarity'] = similarity
                            
                            # Skip if below threshold
                            if cosine_threshold and similarity < cosine_threshold:
                                stats['skipped_low_similarity'] += 1
                                continue
                        
                        results.append(result)
                    
                    # Put results in output queue
                    self.output_queue.put(results)
                    stats['batches_processed'] += 1
                    
                    if pbar:
                        pbar.update(len(batch_papers))
                    
                except Exception as e:
                    print(f"\n❌ Error generating embeddings: {e}")
                    stats['errors'] += 1
                    # Put empty results to maintain count
                    self.output_queue.put([])
                    
        except KeyboardInterrupt:
            print("\n⚠️ Interrupted! Finishing current batch...")
            self._stop_event.set()
        finally:
            if pbar:
                pbar.close()
        
        # Wait for threads to complete
        producer.join()
        consumer.join()
        
        # Calculate final statistics
        duration = time.time() - start_time
        stats['duration'] = duration
        stats['papers_per_second'] = stats['papers_processed'] / duration if duration > 0 else 0
        
        if verbose:
            print(f"\n✅ Embedding generation complete!")
            print(f"📊 Processed {stats['papers_processed']} papers in {duration:.1f}s")
            print(f"⚡ Rate: {stats['papers_per_second']:.1f} papers/second")
            if stats['skipped_low_similarity'] > 0:
                print(f"🔽 Skipped {stats['skipped_low_similarity']} papers below similarity threshold")
            if stats['errors'] > 0:
                print(f"❌ Errors encountered: {stats['errors']}")
        
        return stats
    
    def _data_producer(self, papers: List[Dict]):
        """
        Producer thread that fetches papers in batches.
        Runs in parallel with embedding generation.
        """
        try:
            for i in range(0, len(papers), self.batch_size):
                if self._stop_event.is_set():
                    break
                
                batch = papers[i:i + self.batch_size]
                batch_ids = [p['id'] for p in batch]
                
                # Put batch in queue (blocks if queue is full)
                self.input_queue.put((batch, batch_ids))
            
            # Signal end of data
            self.input_queue.put(None)
            
        except Exception as e:
            print(f"❌ Error in data producer: {e}")
            self.input_queue.put(None)
    
    def _result_consumer(
        self,
        use_bulk_operations: bool,
        verbose: bool,
        stats: Dict
    ):
        """
        Consumer thread that writes embeddings to database.
        Runs in parallel with embedding generation.
        """
        if use_bulk_operations:
            bulk_buffer = []
            bulk_buffer_size = 1000  # Flush every N embeddings
        
        checkpoint_counter = 0
        
        try:
            while True:
                # Get results from queue
                results = self.output_queue.get()
                if results is None:  # End signal
                    break
                
                if use_bulk_operations:
                    # Add to buffer
                    bulk_buffer.extend(results)
                    
                    # Flush buffer if it's large enough
                    if len(bulk_buffer) >= bulk_buffer_size:
                        self._bulk_update_embeddings(bulk_buffer)
                        stats['papers_processed'] += len(bulk_buffer)
                        bulk_buffer = []
                else:
                    # Update individually
                    for result in results:
                        try:
                            # Convert numpy array to list for storage
                            embedding_list = result['embedding'].tolist() if hasattr(result['embedding'], 'tolist') else list(result['embedding'])
                            
                            PaperRepository.update_embedding(
                                result['paper_id'],
                                embedding_list
                            )
                            stats['papers_processed'] += 1
                        except Exception as e:
                            print(f"\n❌ Error updating paper {result['paper_id']}: {e}")
                            stats['errors'] += 1
                
                # Checkpoint progress
                checkpoint_counter += len(results)
                if checkpoint_counter >= self.checkpoint_interval and verbose:
                    print(f"\n✅ Checkpoint: {stats['papers_processed']} papers saved to database")
                    checkpoint_counter = 0
                    
        except Exception as e:
            print(f"\n❌ Error in result consumer: {e}")
            stats['errors'] += 1
        finally:
            # Flush any remaining data
            if use_bulk_operations and bulk_buffer:
                self._bulk_update_embeddings(bulk_buffer)
                stats['papers_processed'] += len(bulk_buffer)
    
    def _bulk_update_embeddings(self, results: List[Dict]):
        """
        Perform bulk update of embeddings in database.
        """
        if not results:
            return
        
        try:
            # Prepare bulk update data
            updates = []
            for result in results:
                embedding_list = result['embedding'].tolist() if hasattr(result['embedding'], 'tolist') else list(result['embedding'])
                updates.append((result['paper_id'], embedding_list))
            
            # Get model name from the embedding model
            model_name = getattr(self.embedding_model, 'model_name', 'Alibaba-NLP/gte-large-en-v1.5')
            
            # Use a more efficient bulk update
            PaperRepository.bulk_update_embeddings(updates, embedding_model=model_name)
            
        except AttributeError:
            # If bulk_update_embeddings doesn't exist, fall back to individual updates
            for result in results:
                try:
                    embedding_list = result['embedding'].tolist() if hasattr(result['embedding'], 'tolist') else list(result['embedding'])
                    PaperRepository.update_embedding(result['paper_id'], embedding_list)
                except Exception as e:
                    print(f"\n❌ Error updating paper {result['paper_id']}: {e}")
    
    @staticmethod
    def _cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        return float(dot_product / (norm1 * norm2)) if norm1 > 0 and norm2 > 0 else 0.0


def optimize_embedding_batch_size(
    embedding_model: SentenceTransformerInference,
    sample_size: int = 100,
    verbose: bool = True
) -> int:
    """
    Find optimal batch size for the embedding model on current hardware.
    
    Args:
        embedding_model: The embedding model to test
        sample_size: Number of sample texts to test with
        verbose: Whether to print results
        
    Returns:
        Optimal batch size
    """
    import torch
    
    if verbose:
        print("🔍 Finding optimal batch size for embedding model...")
    
    # Test different batch sizes
    batch_sizes = [32, 64, 128, 256, 512, 1024, 2048]
    sample_texts = ["This is a sample abstract for testing embedding performance."] * sample_size
    
    best_batch_size = 256  # Default
    best_throughput = 0
    
    for batch_size in batch_sizes:
        try:
            start_time = time.time()
            
            # Test embedding generation
            _ = embedding_model.invoke(
                sample_texts,
                batch_size=batch_size,
                show_progress_bar=False
            )
            
            duration = time.time() - start_time
            throughput = sample_size / duration
            
            if verbose:
                print(f"  Batch size {batch_size}: {throughput:.1f} texts/sec")
            
            if throughput > best_throughput:
                best_throughput = throughput
                best_batch_size = batch_size
                
        except (torch.cuda.OutOfMemoryError, RuntimeError) as e:
            if verbose:
                print(f"  Batch size {batch_size}: Out of memory")
            break
    
    if verbose:
        print(f"✅ Optimal batch size: {best_batch_size}")
    
    return best_batch_size