"""
Embed Seed Node for Mind-Map Explorer

This node ensures the seed paper has an embedding for similarity search.
If no embedding exists, it generates one using the configured embedding model.
"""

import logging
from typing import Dict, Any

from ..state import MindMapState, Message
from ...inference.llm import LLMModelFactory
from ...data_access import PaperRepository

logger = logging.getLogger(__name__)


class EmbedSeedNode:
    """
    Node responsible for ensuring seed paper has an embedding.
    
    Checks if the seed paper has an embedding and generates one if needed
    using the configured embedding model.
    """
    
    def __init__(self):
        """Initialize the Embed Seed Node."""
        pass
        
    def __call__(self, state: MindMapState) -> Dict[str, Any]:
        """
        Execute seed paper embedding generation if needed.
        
        Args:
            state: Current mind-map workflow state
            
        Returns:
            Updated state with embedding confirmation
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
            logger.info(f"Checking embedding for seed paper ID: {seed_paper_id}")
            
            # Check if paper already has embedding in database
            paper_data = PaperRepository.get_paper_by_id(seed_paper_id)
            has_embedding = paper_data and paper_data.get('embedding') is not None
            
            if has_embedding:
                logger.info(f"Seed paper {seed_paper_id} already has embedding")
                return {
                    "current_node": "embed_seed",
                    "messages": [Message(
                        role="assistant", 
                        content=f"Seed paper embedding confirmed (ID: {seed_paper_id})"
                    )]
                }
            
            # Generate embedding if needed
            logger.info(f"Generating embedding for seed paper {seed_paper_id}")
            
            # Get embedding model configuration
            embedding_config = state.get("embedding_model_config", {})
            if not embedding_config:
                logger.error("No embedding model configuration found")
                return {
                    "errors": ["No embedding model configuration found"],
                    "messages": [Message(role="assistant", content="Error: No embedding model configuration")]
                }
            
            # Create embedding model
            model_type = embedding_config.get("provider", "sentence-transformer")
            model_name = embedding_config.get("model_name", "Alibaba-NLP/gte-large-en-v1.5")
            
            try:
                embedding_model = LLMModelFactory.create_model(
                    model_type=model_type,
                    model_name=model_name,
                    **embedding_config
                )
            except Exception as e:
                logger.error(f"Failed to create embedding model: {e}")
                return {
                    "errors": [f"Failed to create embedding model: {e}"],
                    "messages": [Message(role="assistant", content=f"Error creating embedding model: {e}")]
                }
            
            # Generate embedding from title and abstract
            text_to_embed = f"{seed_paper['title']} {seed_paper['abstract']}"
            
            try:
                embedding = embedding_model.invoke(
                    text_to_embed,
                    to_list=True,  # Convert to list for database storage
                    normalize=True  # Normalize for cosine similarity
                )
                
                # Update paper in database with embedding
                PaperRepository.update_paper_embedding(seed_paper_id, embedding)
                
                logger.info(f"Successfully generated and saved embedding for seed paper {seed_paper_id}")
                
                return {
                    "current_node": "embed_seed",
                    "messages": [Message(
                        role="assistant", 
                        content=f"Generated embedding for seed paper (ID: {seed_paper_id})"
                    )]
                }
                
            except Exception as e:
                logger.error(f"Failed to generate embedding: {e}")
                return {
                    "errors": [f"Failed to generate embedding: {e}"],
                    "messages": [Message(role="assistant", content=f"Error generating embedding: {e}")]
                }
            
        except Exception as e:
            logger.error(f"Error in embed seed: {str(e)}")
            return {
                "errors": [f"Embed seed failed: {str(e)}"],
                "messages": [Message(role="assistant", content=f"Error in embedding generation: {str(e)}")]
            }
    
    def get_node_info(self) -> Dict[str, Any]:
        """Get information about this node."""
        return {
            "node_type": "embed_seed",
            "description": "Ensures seed paper has embedding for similarity search",
            "inputs": ["seed_paper", "embedding_model_config"],
            "outputs": ["embedding_confirmation"]
        }


def create_embed_seed_node() -> EmbedSeedNode:
    """
    Factory function to create an EmbedSeedNode.
        
    Returns:
        Configured EmbedSeedNode instance
    """
    return EmbedSeedNode() 