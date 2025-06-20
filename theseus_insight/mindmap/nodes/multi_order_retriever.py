"""
Multi-Order Retriever Node for Mind-Map Explorer

This node performs iterative similarity search to find papers related to multiple
source papers across multiple expansion orders, enabling complex mind-map generation.
"""

import logging
from typing import Dict, Any, List, Set

from ..state import MindMapState, Message, create_paper_node, create_mindmap_edge
import yake

logger = logging.getLogger(__name__)


class MultiOrderRetrieverNode:
    """
    Node responsible for multi-order retrieval using iterative similarity search.
    
    Performs expansion across multiple orders:
    - Order 1: Find papers similar to seed paper
    - Order 2: Find papers similar to each paper from Order 1
    - Order N: Find papers similar to each paper from Order N-1
    
    Controls exponential growth with max_nodes_per_order parameter.
    """
    
    def __init__(self, db):
        """
        Initialize the Multi-Order Retriever Node.
        
        Args:
            db: Database instance (PaperDatabase)
        """
        self.db = db
        self.logger = logging.getLogger(__name__)
        self.keyword_extractor = yake.KeywordExtractor(lan="en", n=1, top=5)
        
    def __call__(self, state: MindMapState) -> Dict[str, Any]:
        """
        Execute multi-order similarity search to find related papers.
        
        Args:
            state: Current mind-map workflow state
            
        Returns:
            Updated state with papers from all expansion orders
        """
        try:
            seed_paper = state.get("seed_paper")
            
            if not seed_paper:
                logger.error("No seed paper found in state")
                return {
                    "errors": ["No seed paper found in state"],
                    "messages": [Message(role="assistant", content="Error: No seed paper found")]
                }
            
            expansion_order = state.get("expansion_order", 1)
            max_nodes_per_order = state.get("max_nodes_per_order", 20)
            k_neighbors = state.get("k_neighbors", 15)
            similarity_threshold = state.get("similarity_threshold", 0.3)
            
            logger.info(f"Starting multi-order retrieval: {expansion_order} orders, max {max_nodes_per_order} nodes per order")
            
            # Initialize tracking structures
            all_papers = {seed_paper["id"]: seed_paper}
            papers_by_order = {0: [seed_paper["id"]]}  # Order 0 is the seed
            all_edges = []
            processed_papers = set()  # Track papers we've already expanded from
            
            # Perform expansion for each order
            for current_order in range(1, expansion_order + 1):
                logger.info(f"Processing expansion order {current_order}")
                
                # Get source papers from previous order
                source_paper_ids = papers_by_order.get(current_order - 1, [])
                if not source_paper_ids:
                    logger.warning(f"No source papers for order {current_order}")
                    break
                
                # Limit the number of papers to expand from to control growth
                if len(source_paper_ids) > max_nodes_per_order:
                    # Sort by similarity score and take top papers
                    source_papers_with_scores = [
                        (pid, all_papers[pid].get("similarity_score", 0.0)) 
                        for pid in source_paper_ids
                    ]
                    source_papers_with_scores.sort(key=lambda x: x[1], reverse=True)
                    source_paper_ids = [pid for pid, _ in source_papers_with_scores[:max_nodes_per_order]]
                    logger.info(f"Limited source papers to top {len(source_paper_ids)} by similarity")
                
                current_order_papers = []
                
                # Expand from each source paper
                for source_paper_id in source_paper_ids:
                    if source_paper_id in processed_papers:
                        continue  # Skip papers we've already processed
                    
                    try:
                        # Find similar papers for this source
                        similar_papers_data = self.db.find_similar_papers_mindmap(
                            seed_paper_id=source_paper_id,
                            k=k_neighbors,
                            similarity_threshold=similarity_threshold
                        )
                        
                        # Process found papers
                        for paper_data in similar_papers_data:
                            paper_id = paper_data.get('id')
                            
                            # Skip if we already have this paper
                            if paper_id in all_papers:
                                continue
                            
                            # Handle similarity score
                            similarity_score = paper_data.get('cosine_similarity', 
                                                            1.0 - paper_data.get('similarity_distance', 0.0))
                            
                            # Create paper node
                            paper_node = create_paper_node(paper_data, similarity_score)
                            all_papers[paper_id] = paper_node
                            current_order_papers.append(paper_id)
                            
                            # Create edge from source to this paper
                            edge = create_mindmap_edge(
                                source_id=source_paper_id,
                                target_id=paper_id,
                                similarity_score=similarity_score
                            )
                            all_edges.append(edge)

                            kw = self.db.get_paper_keywords(paper_id)
                            if not kw:
                                try:
                                    text_kw = f"{paper_data['title']} {paper_data['abstract']}"
                                    kw_scores = self.keyword_extractor.extract_keywords(text_kw)
                                    kw = [w for w, _ in kw_scores]
                                    self.db.update_paper_keywords(paper_id, kw)
                                except Exception:
                                    kw = []
                            paper_node["keywords"] = kw
                        
                        # Mark this paper as processed
                        processed_papers.add(source_paper_id)
                        
                    except Exception as e:
                        logger.warning(f"Failed to expand from paper {source_paper_id}: {e}")
                        continue
                
                # Store papers found in this order
                papers_by_order[current_order] = current_order_papers
                
                logger.info(f"Order {current_order}: Found {len(current_order_papers)} new papers")
                
                # Stop if we didn't find any new papers
                if not current_order_papers:
                    logger.info(f"No new papers found at order {current_order}, stopping expansion")
                    break
                
                # Control exponential growth - if we have too many papers, stop
                total_papers = len(all_papers)
                if total_papers > 500:  # Hard limit to prevent overwhelming graphs
                    logger.warning(f"Reached maximum paper limit ({total_papers}), stopping expansion")
                    break
            
            # Convert all_papers dict to list for similar_papers (for compatibility)
            similar_papers = [paper for paper_id, paper in all_papers.items() 
                            if paper_id != seed_paper["id"]]
            
            # Log final statistics
            total_papers = len(all_papers)
            total_edges = len(all_edges)
            logger.info(f"Multi-order retrieval complete: {total_papers} total papers, {total_edges} edges")
            
            # Log papers by order for debugging
            for order, paper_ids in papers_by_order.items():
                logger.info(f"Order {order}: {len(paper_ids)} papers")
            
            return {
                "similar_papers": similar_papers,
                "edges": all_edges,
                "all_papers": all_papers,
                "papers_by_order": papers_by_order,
                "current_node": "multi_order_retriever",
                "messages": [Message(
                    role="assistant", 
                    content=f"Multi-order expansion complete: {total_papers} papers across {len(papers_by_order)} orders"
                )]
            }
            
        except Exception as e:
            logger.error(f"Error in multi-order retriever: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {
                "errors": [f"Multi-order retrieval failed: {str(e)}"],
                "messages": [Message(role="assistant", content=f"Error in multi-order retrieval: {str(e)}")]
            }
    
    def get_node_info(self) -> Dict[str, Any]:
        """Get information about this node."""
        return {
            "node_type": "multi_order_retriever",
            "description": "Performs multi-order similarity search for complex mind-map generation",
            "inputs": ["seed_paper", "expansion_order", "max_nodes_per_order", "k_neighbors", "similarity_threshold"],
            "outputs": ["similar_papers", "edges", "all_papers", "papers_by_order"]
        }


def create_multi_order_retriever_node(db) -> MultiOrderRetrieverNode:
    """
    Factory function to create a MultiOrderRetrieverNode.
    
    Args:
        db: Database instance
        
    Returns:
        Configured MultiOrderRetrieverNode instance
    """
    return MultiOrderRetrieverNode(db) 