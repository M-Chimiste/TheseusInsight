"""
Summariser Node for Mind-Map Explorer

This node generates concise, LLM-powered summaries for each paper in the mind-map
to provide quick insights without requiring full abstract reading.
"""

import logging
from typing import Dict, Any, List
import asyncio

from ..state import MindMapState, Message
from ...inference.llm import LLMModelFactory

logger = logging.getLogger(__name__)


class SummariserNode:
    """
    Node responsible for generating LLM-powered summaries for mind-map papers.
    
    Takes the retrieved papers and generates concise, informative summaries
    that highlight key contributions and relevance to the seed paper.
    """
    
    def __init__(self, config: Dict[str, Any], db=None):
        """
        Initialize the Summariser Node.
        
        Args:
            config: Configuration dictionary containing LLM settings
            db: Database instance for caching summaries
        """
        self.config = config
        # No hard character cap; rely on LLM token limit
        self.max_summary_length = None
        self.batch_size = config.get("summary_batch_size", 5)
        self.progress_callback = None  # Will be set during workflow execution
        self.db = db
        
    def __call__(self, state: MindMapState) -> Dict[str, Any]:
        """
        Execute LLM-powered summarization for all papers.
        
        Args:
            state: Current mind-map workflow state
            
        Returns:
            Updated state with summaries populated
        """
        try:
            seed_paper = state.get("seed_paper")
            similar_papers = state.get("similar_papers", [])
            
            if not seed_paper:
                logger.error("No seed paper found in state")
                return {
                    "errors": ["No seed paper found in state"],
                    "messages": [Message(role="assistant", content="Error: No seed paper found")]
                }
            
            if not similar_papers:
                logger.warning("No similar papers found for summarization")
                return {
                    "summaries": {},
                    "current_node": "summariser",
                    "messages": [Message(role="assistant", content="No papers to summarize")]
                }
            
            logger.info(f"Generating summaries for {len(similar_papers)} papers")
            
            # Get LLM model configuration
            llm_config = state.get("llm_model_config", {})
            logger.info(f"DEBUG: LLM config received in summariser: {llm_config}")
            logger.info(f"DEBUG: LLM config type: {type(llm_config)}")
            logger.info(f"DEBUG: LLM config empty check: {not llm_config}")
            
            if not llm_config:
                logger.warning("No LLM model configuration found, using fallback summaries")
                print("No LLM model configuration found, using fallback summaries")
                # Use fallback summaries instead of failing
                summaries = {}
                all_papers = [seed_paper] + similar_papers
                for paper in all_papers:
                    summaries[paper["id"]] = self._create_fallback_summary(paper)
                
                return {
                    "summaries": summaries,
                    "current_node": "summariser",
                    "warnings": ["Used fallback summaries due to missing LLM configuration"],
                    "messages": [Message(role="assistant", content=f"Generated {len(summaries)} fallback summaries")]
                }
            
            # Create LLM model
            try:
                model_type = llm_config.get("model_type", llm_config.get("provider", "ollama"))
                
                # Filter out parameters that should not be passed to LLM models
                # trust_remote_code is specific to sentence transformers/embedding models
                excluded_params = ["model_type", "provider", "trust_remote_code"]
                filtered_config = {k: v for k, v in llm_config.items() 
                                 if k not in excluded_params}
                
                logger.info(f"DEBUG: Creating LLM model with type: {model_type}")
                logger.info(f"DEBUG: Filtered LLM config: {filtered_config}")
                print(f"DEBUG: About to create LLM model - type: {model_type}, config: {filtered_config}")
                
                llm_model = LLMModelFactory.create_model(
                    model_type=model_type,
                    **filtered_config
                )
                logger.info(f"DEBUG: LLM model created successfully: {type(llm_model)}")
                print(f"DEBUG: LLM model created successfully: {type(llm_model)}")
            except Exception as e:
                logger.error(f"Failed to create LLM model: {e}")
                print(f"DEBUG: Failed to create LLM model: {e}")
                return {
                    "errors": [f"Failed to create LLM model: {e}"],
                    "messages": [Message(role="assistant", content=f"Error creating LLM model: {e}")]
                }
            
            # Generate summaries for all papers (including seed)
            all_papers = [seed_paper] + similar_papers
            summaries = {}
            
            # Attempt to fetch cached summaries from DB if available
            papers_to_summarize = []
            if self.db is not None:
                for p in all_papers:
                    cached = None
                    try:
                        cached = self.db.get_paper_summary(p["id"])
                    except Exception:
                        cached = None
                    if cached:
                        summaries[p["id"]] = cached
                    else:
                        papers_to_summarize.append(p)
            else:
                papers_to_summarize = all_papers
            
            if not papers_to_summarize:
                logger.info("All summaries retrieved from cache; skipping LLM calls")
                return {
                    "summaries": summaries,
                    "current_node": "summariser",
                    "messages": [Message(role="assistant", content="Loaded cached summaries")]
                }
            
            try:
                # Process papers in batches to avoid overwhelming the LLM
                for i in range(0, len(papers_to_summarize), self.batch_size):
                    batch = papers_to_summarize[i:i + self.batch_size]
                    print(f"DEBUG: Processing batch {i//self.batch_size + 1} with {len(batch)} papers")
                    batch_summaries = self._generate_batch_summaries(
                        batch, seed_paper, llm_model
                    )
                    summaries.update(batch_summaries)
                    print(f"DEBUG: Batch {i//self.batch_size + 1} completed, got {len(batch_summaries)} summaries")
                    
                    logger.info(f"Generated summaries for batch {i//self.batch_size + 1}/{(len(papers_to_summarize) + self.batch_size - 1)//self.batch_size}")
                    
                    # Save newly generated summaries to DB if possible
                    if self.db is not None:
                        for pid, summ in batch_summaries.items():
                            try:
                                self.db.update_paper_summary(pid, summ)
                            except Exception:
                                pass
                
                logger.info(f"Successfully generated {len(summaries)} summaries")
                
                return {
                    "summaries": summaries,
                    "current_node": "summariser",
                    "messages": [Message(
                        role="assistant", 
                        content=f"Generated {len(summaries)} paper summaries"
                    )]
                }
                
            except Exception as e:
                logger.error(f"Failed to generate summaries: {e}")
                return {
                    "errors": [f"Summary generation failed: {e}"],
                    "messages": [Message(role="assistant", content=f"Error generating summaries: {e}")]
                }
            
        except Exception as e:
            logger.error(f"Error in summariser: {str(e)}")
            return {
                "errors": [f"Summarization failed: {str(e)}"],
                "messages": [Message(role="assistant", content=f"Error in summarization: {str(e)}")]
            }
    
    def _generate_batch_summaries(
        self, 
        papers: List[Dict[str, Any]], 
        seed_paper: Dict[str, Any], 
        llm_model
    ) -> Dict[int, str]:
        """
        Generate summaries for a batch of papers.
        
        Args:
            papers: List of papers to summarize
            seed_paper: The seed paper for context
            llm_model: LLM model instance
            
        Returns:
            Dictionary mapping paper IDs to summaries
        """
        summaries = {}
        
        for i, paper in enumerate(papers, 1):
            try:
                logger.info(f"Generating summary for paper {i}/{len(papers)}: {paper['id']}")
                logger.info(f"Paper title: {paper['title'][:80]}...")
                print(f"DEBUG: Generating summary for paper {paper['id']}: {paper['title'][:50]}...")
                
                # Calculate progress within summarization phase (60-75)
                # This provides granular progress during the potentially long summarization phase
                summary_start_progress = 60
                summary_end_progress = 75
                individual_progress = summary_start_progress + ((i-1) / len(papers)) * (summary_end_progress - summary_start_progress)
                
                # Call progress callback if available (for synchronous execution)
                if hasattr(self, 'sync_progress_callback') and self.sync_progress_callback:
                    try:
                        self.sync_progress_callback(
                            "summariser", 
                            individual_progress, 
                            f"Generating summary {i}/{len(papers)}: {paper['title'][:40]}..."
                        )
                    except Exception as e:
                        logger.error(f"Progress callback error during summary {i}: {e}")
                
                summary = self._generate_single_summary(paper, seed_paper, llm_model)
                summaries[paper["id"]] = summary
                
                logger.info(f"Completed summary {i}/{len(papers)} for paper {paper['id']}")
                logger.info(f"Summary preview: {summary[:150]}...")
                print(f"DEBUG: Summary generated for paper {paper['id']}: {summary[:100]}...")
                
            except Exception as e:
                logger.error(f"Failed to generate summary for paper {paper['id']}: {e}")
                print(f"DEBUG: Failed to generate summary for paper {paper['id']}: {e}")
                # Provide fallback summary
                summaries[paper["id"]] = self._create_fallback_summary(paper)
        
        return summaries
    
    def _generate_single_summary(
        self, 
        paper: Dict[str, Any], 
        seed_paper: Dict[str, Any], 
        llm_model
    ) -> str:
        """
        Generate a single paper summary using LLM.
        
        Args:
            paper: Paper to summarize
            seed_paper: Seed paper for context
            llm_model: LLM model instance
            
        Returns:
            Generated summary string
        """
        # Create prompt for summarization
        is_seed = paper["id"] == seed_paper["id"]
        
        if is_seed:
            prompt = f"""Summarize this research paper in exactly one sentence ({self.max_summary_length} characters max).
Focus on the main contribution and key findings.

Title: {paper['title']}
Abstract: {paper['abstract']}

Summary:"""
        else:
            prompt = f"""Summarize this research paper in exactly one sentence ({self.max_summary_length} characters max).
Focus on how it relates to the seed paper and its main contribution.

Seed Paper: {seed_paper['title']}
Paper to Summarize: {paper['title']}
Abstract: {paper['abstract']}
Similarity Score: {paper.get('similarity_score', 0.0):.3f}

Summary:"""
        
        system_prompt = "You are a research assistant that creates concise, informative summaries of academic papers. Always respond with exactly one sentence."
        
        messages = [{"role": "user", "content": prompt}]
        
        try:
            print(f"DEBUG: About to invoke LLM for paper {paper['id']}")
            print(f"DEBUG: Prompt length: {len(prompt)} characters")
            response = llm_model.invoke(messages, system_prompt)
            print(f"DEBUG: LLM response received: {response[:100]}...")
            
            # Clean and truncate response
            summary = response.strip()
            
            return summary
            
        except Exception as e:
            logger.error(f"LLM invocation failed for paper {paper['id']}: {e}")
            print(f"DEBUG: LLM invocation failed for paper {paper['id']}: {e}")
            return self._create_fallback_summary(paper)
    
    def _create_fallback_summary(self, paper: Dict[str, Any]) -> str:
        """
        Create a fallback summary when LLM generation fails.
        
        Args:
            paper: Paper to create fallback summary for
            
        Returns:
            Fallback summary string
        """
        abstract = paper.get("abstract", "")
        return abstract
    
    def get_node_info(self) -> Dict[str, Any]:
        """Get information about this node."""
        return {
            "node_type": "summariser",
            "description": "Generates LLM-powered summaries for mind-map papers",
            "inputs": ["seed_paper", "similar_papers", "llm_model_config"],
            "outputs": ["summaries"]
        }


def create_summariser_node(config: Dict[str, Any]) -> SummariserNode:
    """
    Factory function to create a SummariserNode.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Configured SummariserNode instance
    """
    return SummariserNode(config) 