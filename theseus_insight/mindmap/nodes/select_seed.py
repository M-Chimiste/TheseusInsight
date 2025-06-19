"""
Select Seed Node for Mind-Map Explorer

This node validates the seed paper ID and retrieves the complete paper
information from the database to use as the center of the mind-map.
"""

import logging
from typing import Dict, Any

from ..state import MindMapState, Message, create_paper_node

logger = logging.getLogger(__name__)


class SelectSeedNode:
    """
    Node responsible for validating and retrieving seed paper information.
    
    Takes the seed paper ID from the state and fetches the complete paper
    data from the database to use as the center of the mind-map.
    """
    
    def __init__(self, db):
        """
        Initialize the Select Seed Node.
        
        Args:
            db: Database instance (PaperDatabase)
        """
        self.db = db
        
    def __call__(self, state: MindMapState) -> Dict[str, Any]:
        """
        Execute seed paper selection and validation.
        
        Args:
            state: Current mind-map workflow state
            
        Returns:
            Updated state with seed_paper populated
        """
        try:
            seed_paper_id = state.get("seed_paper_id")
            
            if not seed_paper_id:
                logger.error("No seed paper ID provided")
                return {
                    "errors": ["No seed paper ID provided"],
                    "messages": [Message(role="assistant", content="Error: No seed paper ID provided")]
                }
            
            logger.info(f"Selecting seed paper with ID: {seed_paper_id}")
            
            # Retrieve paper from database
            paper_data = self.db.get_paper_by_id(seed_paper_id)
            
            if not paper_data:
                logger.error(f"Seed paper with ID {seed_paper_id} not found in database")
                return {
                    "errors": [f"Seed paper with ID {seed_paper_id} not found"],
                    "messages": [Message(role="assistant", content=f"Error: Paper with ID {seed_paper_id} not found")]
                }
            
            # Check if paper has embedding (required for similarity search)
            has_embedding = paper_data.get('embedding') is not None
            if not has_embedding:
                logger.warning(f"Seed paper {seed_paper_id} has no embedding - similarity search may be limited")
                
            # Create seed paper node
            seed_paper = create_paper_node(paper_data, similarity_score=1.0)  # Seed has perfect similarity to itself
            
            logger.info(f"Successfully selected seed paper: '{paper_data.get('title', 'Unknown Title')}'")
            
            return {
                "seed_paper": seed_paper,
                "current_node": "select_seed",
                "messages": [Message(
                    role="assistant", 
                    content=f"Selected seed paper: '{paper_data.get('title', 'Unknown Title')}' (ID: {seed_paper_id})"
                )]
            }
            
        except Exception as e:
            logger.error(f"Error in seed selection: {str(e)}")
            return {
                "errors": [f"Seed selection failed: {str(e)}"],
                "messages": [Message(role="assistant", content=f"Error selecting seed paper: {str(e)}")]
            }
    
    def get_node_info(self) -> Dict[str, Any]:
        """Get information about this node."""
        return {
            "node_type": "select_seed",
            "description": "Validates and retrieves seed paper information",
            "inputs": ["seed_paper_id"],
            "outputs": ["seed_paper"]
        }


def create_select_seed_node(db) -> SelectSeedNode:
    """
    Factory function to create a SelectSeedNode.
    
    Args:
        db: Database instance
        
    Returns:
        Configured SelectSeedNode instance
    """
    return SelectSeedNode(db) 