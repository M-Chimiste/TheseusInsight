#!/usr/bin/env python3
"""
Utility script to backfill embeddings for papers that don't have them yet.
This is useful when upgrading from a version without embeddings to one with embeddings.
"""

import os
import sys
import json
import torch
import asyncio
from typing import Optional
from tqdm import tqdm
from uuid import UUID

# Add the project root to the path so we can import theseus_insight modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from theseus_insight.data_access import PaperRepository, SettingsRepository
from theseus_insight.inference import SentenceTransformerInference
from theseus_insight.data_processing.optimized_embeddings import OptimizedEmbeddingPipeline, optimize_embedding_batch_size
from theseus_insight.data_processing.checkpoint_manager import CheckpointManager


async def backfill_embeddings(
    embedding_model_name: Optional[str] = None,
    trust_remote_code: bool = True,
    batch_size: int = 256,
    dry_run: bool = False,
    verbose: bool = True,
    use_optimized_pipeline: bool = True,
    use_database_checkpoints: bool = True
):
    """
    Backfill embeddings for papers that don't have them.
    
    Args:
        embedding_model_name: Name of the embedding model to use. If None, tries to get from orchestration config.
        trust_remote_code: Whether to trust remote code for the embedding model
        batch_size: How many papers to process at once (1 = no batching, higher = more efficient)
        dry_run: If True, only shows what would be done without making changes
        verbose: If True, prints detailed progress information
        use_optimized_pipeline: If True, uses the optimized parallel pipeline
    """
    if verbose:
        print("Connecting to database using repository pattern...")
    
    # Get embedding model configuration
    if embedding_model_name is None:
        if verbose:
            print("No embedding model specified, trying to get from orchestration config...")
        orchestration_json = SettingsRepository.get("orchestration")
        if not orchestration_json:
            raise ValueError("No orchestration config found in database and no embedding model specified")
        
        orchestration_config = json.loads(orchestration_json)
        embedding_model_config = orchestration_config.get('embedding_model')
        if not embedding_model_config:
            raise ValueError("No embedding model config found in orchestration config")
        
        embedding_model_name = embedding_model_config['model_name']
        trust_remote_code = embedding_model_config.get('trust_remote_code', True)
        if verbose:
            print(f"Using embedding model from config: {embedding_model_name}")
    
    # Check if we need to process any papers
    if dry_run:
        papers_without_embeddings = PaperRepository.get_papers_without_embeddings()
        if len(papers_without_embeddings) == 0:
            print("All papers already have embeddings!")
            return
        print(f"DRY RUN: Would process {len(papers_without_embeddings)} papers")
        for paper in papers_without_embeddings[:5]:  # Show first 5 as examples
            print(f"  - Paper ID {paper['id']}: {paper['title'][:100]}...")
        if len(papers_without_embeddings) > 5:
            print(f"  ... and {len(papers_without_embeddings) - 5} more papers")
        return
    
    # Initialize embedding model
    if verbose:
        print(f"Initializing embedding model: {embedding_model_name}")
    
    # Determine best device for embeddings
    device = None
    if torch.backends.mps.is_available():
        device = "mps"
        if verbose:
            print(f"🚀 Using Apple Silicon GPU (MPS) for embeddings")
    elif torch.cuda.is_available():
        device = "cuda"
        if verbose:
            print(f"🚀 Using CUDA GPU for embeddings")
    else:
        device = "cpu"
        if verbose:
            print(f"💻 Using CPU for embeddings")
    
    embedding_model = SentenceTransformerInference(
        embedding_model_name, 
        remote_code=trust_remote_code,
        device=device
    )
    
    # Use optimized pipeline if requested
    if use_optimized_pipeline:
        if verbose:
            print("🚀 Using optimized embedding pipeline with I/O overlap")
            
        # Optionally find optimal batch size
        if batch_size == 256:  # Default value - auto-optimize
            optimal_batch_size = optimize_embedding_batch_size(embedding_model, verbose=verbose)
            batch_size = optimal_batch_size
        
        # Run optimized pipeline
        pipeline = OptimizedEmbeddingPipeline(
            embedding_model=embedding_model,
            batch_size=batch_size,
            prefetch_size=2
        )
        
        stats = pipeline.process_papers_without_embeddings(
            use_bulk_operations=True,
            verbose=verbose
        )
        
        if verbose:
            print(f"\nBackfill complete!")
            print(f"Successfully processed: {stats['papers_processed']} papers")
            if stats.get('errors', 0) > 0:
                print(f"Errors encountered: {stats['errors']} papers")
            print(f"⚡ Rate: {stats.get('papers_per_second', 0):.1f} papers/second")
        
        return
    
    # Fall back to original implementation
    # Get papers without embeddings
    papers_without_embeddings = PaperRepository.get_papers_without_embeddings()
    if verbose:
        print(f"Found {len(papers_without_embeddings)} papers without embeddings")
        if batch_size > 1:
            print(f"⚡ Using batch processing with batch size: {batch_size}")
    
    if len(papers_without_embeddings) == 0:
        if verbose:
            print("All papers already have embeddings!")
        return
    
    # Process papers in batches
    processed_count = 0
    error_count = 0
    
    if batch_size <= 1:
        # No batching - process one by one
        for paper in tqdm(papers_without_embeddings, desc="Processing papers", disable=not verbose):
            try:
                # Generate embedding for the paper's abstract
                embedding = embedding_model.invoke(paper['abstract'])
                
                # Convert to list if needed
                if hasattr(embedding, 'tolist'):
                    embedding = embedding.tolist()
                elif not isinstance(embedding, list):
                    embedding = list(embedding)
                
                # Update the paper with the new embedding
                PaperRepository.update_embedding(paper['id'], embedding)
                processed_count += 1
                
            except Exception as e:
                if verbose:
                    print(f"\nError processing paper ID {paper['id']}: {e}")
                error_count += 1
                continue
    else:
        # Use SentenceTransformer's efficient built-in batching
        if verbose:
            print(f"⚡ Using SentenceTransformer built-in batching with batch_size={batch_size}")
        
        # Extract all abstracts
        abstracts = [paper['abstract'] for paper in papers_without_embeddings]
        
        try:
            # Generate all embeddings at once using efficient batching
            if verbose:
                print(f"🧠 Generating embeddings for {len(abstracts)} papers...")
            
            all_embeddings = embedding_model.invoke(
                abstracts,
                batch_size=batch_size,
                show_progress_bar=verbose
            )
            
            # Update papers with their embeddings
            if verbose:
                print(f"💾 Updating database with embeddings...")
            
            for paper, embedding in tqdm(
                zip(papers_without_embeddings, all_embeddings), 
                desc="Updating papers", 
                total=len(papers_without_embeddings),
                disable=not verbose
            ):
                try:
                    # Convert to list if needed
                    if hasattr(embedding, 'tolist'):
                        embedding = embedding.tolist()
                    elif not isinstance(embedding, list):
                        embedding = list(embedding)
                    
                    # Update the paper with the new embedding
                    PaperRepository.update_embedding(paper['id'], embedding)
                    processed_count += 1
                    
                except Exception as e:
                    if verbose:
                        print(f"\nError updating paper ID {paper['id']}: {e}")
                    error_count += 1
                    continue
                    
        except Exception as e:
            if verbose:
                print(f"\nError during batch embedding generation: {e}")
                print("Falling back to individual processing...")
            
            # Fall back to individual processing
            for paper in tqdm(papers_without_embeddings, desc="Processing individually", disable=not verbose):
                try:
                    embedding = embedding_model.invoke(paper['abstract'])
                    
                    if hasattr(embedding, 'tolist'):
                        embedding = embedding.tolist()
                    elif not isinstance(embedding, list):
                        embedding = list(embedding)
                    
                    PaperRepository.update_embedding(paper['id'], embedding)
                    processed_count += 1
                    
                except Exception as e2:
                    if verbose:
                        print(f"\nError processing paper ID {paper['id']} individually: {e2}")
                    error_count += 1
    
    if verbose:
        print(f"\nBackfill complete!")
        print(f"Successfully processed: {processed_count} papers")
        if error_count > 0:
            print(f"Errors encountered: {error_count} papers")
        if batch_size > 1:
            print(f"⚡ Batch processing improved efficiency: processed {processed_count} papers in batches of {batch_size}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Backfill embeddings for papers without them")
    parser.add_argument(
        "--embedding-model", 
        help="Embedding model name (default: from orchestration config)"
    )
    parser.add_argument(
        "--trust-remote-code", 
        action="store_true", 
        default=True,
        help="Trust remote code for embedding model (default: True)"
    )
    parser.add_argument(
        "--batch-size", 
        type=int, 
        default=256,
        help="Embedding batch size (1 = no batching, higher = more efficient, default: 256)"
    )
    parser.add_argument(
        "--dry-run", 
        action="store_true",
        help="Show what would be done without making changes"
    )
    parser.add_argument(
        "--verbose", "-v", 
        action="store_true", 
        default=True,
        help="Enable verbose output (default: True)"
    )
    parser.add_argument(
        "--quiet", "-q", 
        action="store_true",
        help="Disable verbose output"
    )
    parser.add_argument(
        "--use-optimized-pipeline",
        action="store_true",
        default=True,
        help="Use optimized pipeline with I/O overlap (default: True)"
    )
    parser.add_argument(
        "--no-optimized-pipeline",
        action="store_false",
        dest="use_optimized_pipeline",
        help="Disable optimized pipeline and use original implementation"
    )
    
    args = parser.parse_args()
    
    # Handle verbose/quiet flags
    verbose = args.verbose and not args.quiet
    
    try:
        asyncio.run(backfill_embeddings(
            embedding_model_name=args.embedding_model,
            trust_remote_code=args.trust_remote_code,
            batch_size=args.batch_size,
            dry_run=args.dry_run,
            verbose=verbose,
            use_optimized_pipeline=args.use_optimized_pipeline
        ))
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 