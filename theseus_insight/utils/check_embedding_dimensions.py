#!/usr/bin/env python3
"""
Utility script to check embedding dimensions in the database and identify inconsistencies.
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from theseus_insight.data_model.data_handling import PaperDatabase


def check_embedding_dimensions(db_path: str, fix_inconsistencies: bool = False, verbose: bool = True):
    """Check embedding dimensions across all papers in the database."""
    
    db = PaperDatabase(db_path)
    
    # Get all papers with embeddings
    with db.get_cursor() as cursor:
        cursor.execute("""
            SELECT id, title, embedding_model, embedding 
            FROM papers 
            WHERE embedding IS NOT NULL
            ORDER BY id
        """)
        rows = cursor.fetchall()
    
    if verbose:
        print(f"Found {len(rows)} papers with embeddings")
    
    if len(rows) == 0:
        print("No papers with embeddings found in database")
        return
    
    # Analyze dimensions
    dimension_counts = Counter()
    model_dimensions = {}
    problematic_papers = []
    
    for row in rows:
        paper_id, title, embedding_model, embedding_json = row
        
        try:
            embedding = json.loads(embedding_json)
            dimension = len(embedding)
            dimension_counts[dimension] += 1
            
            # Track dimensions by model
            if embedding_model not in model_dimensions:
                model_dimensions[embedding_model] = set()
            model_dimensions[embedding_model].add(dimension)
            
            # If this dimension is unusual, note the paper
            if dimension not in [768, 384, 1024, 512]:  # Common embedding dimensions
                problematic_papers.append({
                    'id': paper_id,
                    'title': title,
                    'model': embedding_model,
                    'dimension': dimension
                })
                
        except (json.JSONDecodeError, TypeError) as e:
            print(f"ERROR: Could not parse embedding for paper {paper_id}: {e}")
            problematic_papers.append({
                'id': paper_id,
                'title': title,
                'model': embedding_model,
                'dimension': 'INVALID_JSON'
            })
    
    # Report findings
    print("\n=== EMBEDDING DIMENSION ANALYSIS ===")
    print(f"Total papers analyzed: {len(rows)}")
    print(f"Unique dimensions found: {len(dimension_counts)}")
    
    print("\nDimension distribution:")
    for dimension, count in sorted(dimension_counts.items()):
        percentage = (count / len(rows)) * 100
        print(f"  {dimension}D: {count} papers ({percentage:.1f}%)")
    
    print(f"\nModels and their dimensions:")
    for model, dimensions in model_dimensions.items():
        if len(dimensions) > 1:
            print(f"  ⚠️  {model}: {sorted(dimensions)} (INCONSISTENT!)")
        else:
            print(f"  ✓  {model}: {list(dimensions)[0]}D")
    
    # Check for inconsistencies
    if len(dimension_counts) > 1:
        print(f"\n🚨 DIMENSION MISMATCH DETECTED!")
        print(f"Found {len(dimension_counts)} different embedding dimensions in database:")
        
        most_common_dim = dimension_counts.most_common(1)[0][0]
        print(f"Most common dimension: {most_common_dim}D ({dimension_counts[most_common_dim]} papers)")
        
        for dimension, count in dimension_counts.items():
            if dimension != most_common_dim:
                print(f"Incompatible dimension: {dimension}D ({count} papers)")
        
        if fix_inconsistencies:
            print(f"\n🔧 FIXING INCOMPATIBLE EMBEDDINGS...")
            
            # Get the current embedding model configuration
            orchestration_json = db.get_setting("orchestration")
            if orchestration_json:
                orchestration_config = json.loads(orchestration_json)
                embedding_config = orchestration_config.get('embedding_model', {})
                model_name = embedding_config.get('model_name', 'Alibaba-NLP/gte-modernbert-base')
                print(f"Current configured embedding model: {model_name}")
            else:
                model_name = 'Alibaba-NLP/gte-modernbert-base'
                print(f"No orchestration config found, using default: {model_name}")
            
            # Clear embeddings for papers with wrong dimensions
            papers_to_fix = []
            with db.get_cursor() as cursor:
                cursor.execute("""
                    SELECT id, embedding 
                    FROM papers 
                    WHERE embedding IS NOT NULL
                """)
                for paper_id, embedding_json in cursor.fetchall():
                    try:
                        embedding = json.loads(embedding_json)
                        if len(embedding) != most_common_dim:
                            papers_to_fix.append(paper_id)
                    except:
                        papers_to_fix.append(paper_id)
            
            if papers_to_fix:
                print(f"Clearing embeddings for {len(papers_to_fix)} papers with incompatible dimensions...")
                with db.get_cursor() as cursor:
                    for paper_id in papers_to_fix:
                        cursor.execute("UPDATE papers SET embedding = NULL WHERE id = ?", (paper_id,))
                
                print("✅ Incompatible embeddings cleared!")
                print("💡 Run the backfill utility to regenerate embeddings with the correct model:")
                print("   python -m theseus_insight.utils.backfill_embeddings")
            else:
                print("No papers to fix found.")
        else:
            print("\n💡 To fix these inconsistencies, run:")
            print("   python -m theseus_insight.utils.check_embedding_dimensions --fix")
    else:
        print(f"\n✅ All embeddings have consistent dimensions ({list(dimension_counts.keys())[0]}D)")
    
    if problematic_papers:
        print(f"\n📋 Papers with unusual dimensions:")
        for paper in problematic_papers[:10]:  # Show first 10
            print(f"  ID {paper['id']}: {paper['dimension']}D ({paper['model']}) - {paper['title'][:60]}...")
        if len(problematic_papers) > 10:
            print(f"  ... and {len(problematic_papers) - 10} more")


def main():
    parser = argparse.ArgumentParser(description="Check embedding dimensions in the database")
    parser.add_argument(
        "--db-path",
        type=str,
        default="data/theseus.db",
        help="Path to the database file (default: data/theseus.db)"
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Fix inconsistencies by clearing incompatible embeddings"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Reduce output verbosity"
    )
    
    args = parser.parse_args()
    
    try:
        check_embedding_dimensions(
            db_path=args.db_path,
            fix_inconsistencies=args.fix,
            verbose=not args.quiet
        )
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 