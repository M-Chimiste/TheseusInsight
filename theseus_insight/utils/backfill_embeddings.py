#!/usr/bin/env python3
"""
Utility script to backfill embeddings for papers that don't have them yet.
This is useful when upgrading from a version without embeddings to one with embeddings.
"""

import os
import sys
import json
from typing import Optional
from tqdm import tqdm

# Add the project root to the path so we can import theseus_insight modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from theseus_insight.data_model.data_handling import PaperDatabase
from theseus_insight.inference import SentenceTransformerInference


def backfill_embeddings(
    db_url: str,
    embedding_model_name: Optional[str] = None,
    trust_remote_code: bool = True,
    batch_size: int = 10,
    dry_run: bool = False
):
    """
    Backfill embeddings for papers that don't have them.
    
    Args:
        db_url: Database connection URL
        embedding_model_name: Name of the embedding model to use. If None, tries to get from orchestration config.
        trust_remote_code: Whether to trust remote code for the embedding model
        batch_size: How many papers to process at once
        dry_run: If True, only shows what would be done without making changes
    """
    print(f"Connecting to database: {db_url}")
    db = PaperDatabase(db_url)
    
    # Get embedding model configuration
    if embedding_model_name is None:
        print("No embedding model specified, trying to get from orchestration config...")
        orchestration_json = db.get_setting("orchestration")
        if not orchestration_json:
            raise ValueError("No orchestration config found in database and no embedding model specified")
        
        orchestration_config = json.loads(orchestration_json)
        embedding_model_config = orchestration_config.get('embedding_model')
        if not embedding_model_config:
            raise ValueError("No embedding model config found in orchestration config")
        
        embedding_model_name = embedding_model_config['model_name']
        trust_remote_code = embedding_model_config.get('trust_remote_code', True)
        print(f"Using embedding model from config: {embedding_model_name}")
    
    # Get papers without embeddings
    papers_without_embeddings = db.get_papers_without_embeddings()
    print(f"Found {len(papers_without_embeddings)} papers without embeddings")
    
    if len(papers_without_embeddings) == 0:
        print("All papers already have embeddings!")
        return
    
    if dry_run:
        print(f"DRY RUN: Would process {len(papers_without_embeddings)} papers")
        for paper in papers_without_embeddings[:5]:  # Show first 5 as examples
            print(f"  - Paper ID {paper['id']}: {paper['title'][:100]}...")
        if len(papers_without_embeddings) > 5:
            print(f"  ... and {len(papers_without_embeddings) - 5} more papers")
        return
    
    # Initialize embedding model
    print(f"Initializing embedding model: {embedding_model_name}")
    embedding_model = SentenceTransformerInference(
        embedding_model_name, 
        remote_code=trust_remote_code
    )
    
    # Process papers in batches
    processed_count = 0
    error_count = 0
    
    for i in tqdm(range(0, len(papers_without_embeddings), batch_size), desc="Processing batches"):
        batch = papers_without_embeddings[i:i + batch_size]
        
        for paper in batch:
            try:
                # Generate embedding for the paper's abstract
                embedding = embedding_model.invoke(paper['abstract'])
                
                # Convert to list if needed
                if hasattr(embedding, 'tolist'):
                    embedding = embedding.tolist()
                elif not isinstance(embedding, list):
                    embedding = list(embedding)
                
                # Update the paper with the new embedding
                db.update_paper_embedding(paper['id'], embedding)
                processed_count += 1
                
            except Exception as e:
                print(f"\nError processing paper ID {paper['id']}: {e}")
                error_count += 1
                continue
    
    print(f"\nBackfill complete!")
    print(f"Successfully processed: {processed_count} papers")
    if error_count > 0:
        print(f"Errors encountered: {error_count} papers")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Backfill embeddings for papers without them")
    parser.add_argument(
        "--db-url", 
        default=os.getenv("DATABASE_URL", "postgresql://theseus:theseus@localhost:5432/theseusdb"),
        help="Database connection URL (default: from DATABASE_URL env var)"
    )
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
        default=10,
        help="Batch size for processing (default: 10)"
    )
    parser.add_argument(
        "--dry-run", 
        action="store_true",
        help="Show what would be done without making changes"
    )
    
    args = parser.parse_args()
    
    try:
        backfill_embeddings(
            db_url=args.db_url,
            embedding_model_name=args.embedding_model,
            trust_remote_code=args.trust_remote_code,
            batch_size=args.batch_size,
            dry_run=args.dry_run
        )
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 