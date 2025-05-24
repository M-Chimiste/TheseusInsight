#!/usr/bin/env python3
"""
Example script demonstrating the new similarity search functionality in Theseus Insight.
"""

import os
import sys
import json
import requests
from typing import List, Dict, Any

# Configuration
API_BASE_URL = "http://localhost:8000/api"
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://theseus:theseus@localhost:5432/theseusdb")

def search_by_text(query_text: str, limit: int = 10, similarity_threshold: float = 0.7) -> Dict[str, Any]:
    """
    Example: Search for papers using semantic text search.
    """
    url = f"{API_BASE_URL}/papers/similarity-search"
    payload = {
        "query_text": query_text,
        "limit": limit,
        "similarity_threshold": similarity_threshold
    }
    
    print(f"🔍 Searching for papers similar to: '{query_text}'")
    response = requests.post(url, json=payload)
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Found {data['total_results']} similar papers")
        return data
    else:
        print(f"❌ Error: {response.status_code} - {response.text}")
        return {}

def find_similar_to_paper(paper_id: int, limit: int = 10, similarity_threshold: float = 0.7) -> Dict[str, Any]:
    """
    Example: Find papers similar to an existing paper.
    """
    url = f"{API_BASE_URL}/papers/{paper_id}/similar"
    params = {
        "limit": limit,
        "similarity_threshold": similarity_threshold
    }
    
    print(f"🔍 Finding papers similar to paper ID {paper_id}")
    response = requests.get(url, params=params)
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Found {data['total_similar']} similar papers")
        return data
    else:
        print(f"❌ Error: {response.status_code} - {response.text}")
        return {}

def get_papers_without_embeddings() -> Dict[str, Any]:
    """
    Example: Get papers that don't have embeddings yet.
    """
    url = f"{API_BASE_URL}/papers/without-embeddings"
    
    print("🔍 Getting papers without embeddings")
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Found {data['count']} papers without embeddings")
        return data
    else:
        print(f"❌ Error: {response.status_code} - {response.text}")
        return {}

def update_paper_embedding(paper_id: int) -> Dict[str, Any]:
    """
    Example: Generate embedding for a specific paper.
    """
    url = f"{API_BASE_URL}/papers/{paper_id}/update-embedding"
    
    print(f"🔄 Updating embedding for paper ID {paper_id}")
    response = requests.post(url)
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ {data['message']}")
        return data
    else:
        print(f"❌ Error: {response.status_code} - {response.text}")
        return {}

def display_paper_summary(paper: Dict[str, Any], include_similarity: bool = False):
    """
    Helper function to display a paper summary.
    """
    print(f"  📄 ID: {paper['id']}")
    print(f"     Title: {paper['title'][:80]}{'...' if len(paper['title']) > 80 else ''}")
    print(f"     Score: {paper['score']:.2f}")
    print(f"     Date: {paper['date']}")
    if include_similarity and 'similarity_score' in paper and paper['similarity_score'] is not None:
        print(f"     Similarity: {paper['similarity_score']:.3f}")
    print()

def main():
    """
    Main function demonstrating various similarity search scenarios.
    """
    print("🚀 Theseus Insight Similarity Search Examples")
    print("=" * 50)
    
    # Example 1: Text-based semantic search
    print("\n📝 Example 1: Text-based Semantic Search")
    print("-" * 40)
    
    text_results = search_by_text(
        query_text="machine learning for natural language processing",
        limit=5,
        similarity_threshold=0.6
    )
    
    if text_results and text_results.get('results'):
        print(f"Results for query: '{text_results['query_text']}'")
        for i, paper in enumerate(text_results['results'][:3], 1):  # Show top 3
            print(f"\n{i}.")
            display_paper_summary(paper, include_similarity=True)
    
    # Example 2: Find papers similar to an existing paper
    print("\n🔗 Example 2: Find Similar Papers to Existing Paper")
    print("-" * 50)
    
    # First, let's get a paper ID from the text search results
    if text_results and text_results.get('results'):
        reference_paper_id = text_results['results'][0]['id']
        print(f"Using paper ID {reference_paper_id} as reference")
        
        similar_results = find_similar_to_paper(
            paper_id=reference_paper_id,
            limit=5,
            similarity_threshold=0.6
        )
        
        if similar_results:
            print(f"\nReference paper:")
            display_paper_summary(similar_results['reference_paper'])
            
            print(f"Similar papers:")
            for i, paper in enumerate(similar_results['similar_papers'][:3], 1):  # Show top 3
                print(f"\n{i}.")
                display_paper_summary(paper, include_similarity=True)
    
    # Example 3: Check for papers without embeddings
    print("\n🔍 Example 3: Papers Without Embeddings")
    print("-" * 40)
    
    no_embedding_results = get_papers_without_embeddings()
    if no_embedding_results and no_embedding_results.get('papers'):
        print(f"Found {no_embedding_results['count']} papers without embeddings")
        
        # Show first few papers without embeddings
        for i, paper in enumerate(no_embedding_results['papers'][:3], 1):
            print(f"\n{i}.")
            display_paper_summary(paper)
        
        # Example 4: Update embedding for one of these papers
        if no_embedding_results['papers']:
            print("\n🔄 Example 4: Update Paper Embedding")
            print("-" * 35)
            
            paper_to_update = no_embedding_results['papers'][0]['id']
            update_result = update_paper_embedding(paper_to_update)
    else:
        print("✅ All papers have embeddings!")
    
    print("\n🎉 Examples completed!")
    print("\n💡 Tips:")
    print("- Adjust similarity_threshold to get more/fewer results")
    print("- Use the similarity_score to understand result relevance")
    print("- Papers without embeddings can't be used for similarity search")
    print("- The reference paper is excluded from its own similarity search results")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1) 