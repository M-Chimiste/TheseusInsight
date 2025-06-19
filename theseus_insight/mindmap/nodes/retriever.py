"""
Retriever Node for Mind-Map Explorer

This node performs similarity search to find papers related to the seed paper
using vector embeddings and the database's similarity search capabilities.
"""

import logging
from typing import Dict, Any, List

from ..state import MindMapState, Message, create_paper_node, create_mindmap_edge

logger = logging.getLogger(__name__)


class RetrieverNode:
    """
    Node responsible for retrieving similar papers using vector similarity search.
    
    Uses the database's similarity search functionality to find papers most
    similar to the seed paper based on embedding vectors.
    """
    
    def __init__(self, db):
        """
        Initialize the Retriever Node.
        
        Args:
            db: Database instance (PaperDatabase)
        """
        self.db = db
        
    def __call__(self, state: MindMapState) -> Dict[str, Any]:
        """
        Execute similarity search to find related papers.
        
        Args:
            state: Current mind-map workflow state
            
        Returns:
            Updated state with similar_papers and edges populated
        """
        try:
            seed_paper = state.get("seed_paper")
            
            if not seed_paper:
                logger.error("No seed paper found in state")
                return {
                    "errors": ["No seed paper found in state"],
                    "messages": [Message(role="assistant", content="Error: No seed paper found")]
                }
            
            seed_paper_id = seed_paper["id"]
            k_neighbors = state.get("k_neighbors", 15)
            similarity_threshold = state.get("similarity_threshold", 0.3)
            
            logger.info(f"Retrieving {k_neighbors} similar papers for seed {seed_paper_id} (threshold: {similarity_threshold})")
            
            # Perform similarity search using database method
            try:
                similar_papers_data = self.db.find_similar_papers_mindmap(
                    seed_paper_id=seed_paper_id,
                    k=k_neighbors,
                    similarity_threshold=similarity_threshold
                )
                
                if not similar_papers_data:
                    logger.warning(f"No similar papers found for seed {seed_paper_id}")
                    return {
                        "similar_papers": [],
                        "edges": [],
                        "warnings": [f"No similar papers found for seed {seed_paper_id}"],
                        "current_node": "retriever",
                        "messages": [Message(
                            role="assistant", 
                            content=f"No similar papers found for seed paper (threshold: {similarity_threshold})"
                        )]
                    }
                
                # Convert database results to PaperNode objects
                similar_papers = []
                edges = []
                
                for paper_data in similar_papers_data:
                    # Handle both cosine_similarity and similarity_distance fields
                    similarity_score = paper_data.get('cosine_similarity', 
                                                    1.0 - paper_data.get('similarity_distance', 0.0))
                    
                    # Create paper node
                    paper_node = create_paper_node(paper_data, similarity_score)
                    similar_papers.append(paper_node)
                    
                    # Create edge from seed to this paper
                    edge = create_mindmap_edge(
                        source_id=seed_paper_id,
                        target_id=paper_node["id"],
                        similarity_score=similarity_score
                    )
                    edges.append(edge)
                
                logger.info(f"Successfully retrieved {len(similar_papers)} similar papers")
                
                # Log similarity score distribution for debugging
                if similar_papers:
                    scores = [p["similarity_score"] for p in similar_papers]
                    logger.info(f"Similarity scores - min: {min(scores):.3f}, max: {max(scores):.3f}, avg: {sum(scores)/len(scores):.3f}")
                
                return {
                    "similar_papers": similar_papers,
                    "edges": edges,
                    "current_node": "retriever",
                    "messages": [Message(
                        role="assistant", 
                        content=f"Found {len(similar_papers)} similar papers (scores: {min(scores):.3f}-{max(scores):.3f})"
                    )]
                }
                
            except Exception as e:
                logger.error(f"Database similarity search failed: {e}")
                return {
                    "errors": [f"Similarity search failed: {e}"],
                    "messages": [Message(role="assistant", content=f"Error in similarity search: {e}")]
                }
            
        except Exception as e:
            logger.error(f"Error in retriever: {str(e)}")
            return {
                "errors": [f"Retrieval failed: {str(e)}"],
                "messages": [Message(role="assistant", content=f"Error in paper retrieval: {str(e)}")]
            }
    
    def get_node_info(self) -> Dict[str, Any]:
        """Get information about this node."""
        return {
            "node_type": "retriever",
            "description": "Performs similarity search to find related papers",
            "inputs": ["seed_paper", "k_neighbors", "similarity_threshold"],
            "outputs": ["similar_papers", "edges"]
        }


def create_retriever_node(db) -> RetrieverNode:
    """
    Factory function to create a RetrieverNode.
    
    Args:
        db: Database instance
        
    Returns:
        Configured RetrieverNode instance
    """
    return RetrieverNode(db) 