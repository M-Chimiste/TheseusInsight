"""
Build Mind-Map Node for Mind-Map Explorer

This node constructs the final mind-map data structure with layout information,
combining all retrieved papers, summaries, and relationships into a format
ready for frontend visualization.
"""

import logging
import math
from typing import Dict, Any, List, Tuple

from ..state import MindMapState, Message, PaperNode

logger = logging.getLogger(__name__)


class BuildMindMapNode:
    """
    Node responsible for building the final mind-map data structure.
    
    Takes all retrieved papers, summaries, and relationships and constructs
    a complete mind-map with layout positioning for frontend visualization.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the Build Mind-Map Node.
        
        Args:
            config: Configuration dictionary containing layout settings
        """
        self.config = config
        self.default_layout = config.get("default_layout", "force")
        self.canvas_width = config.get("canvas_width", 1200)
        self.canvas_height = config.get("canvas_height", 800)
        self.seed_position = config.get("seed_position", "center")
        
    def __call__(self, state: MindMapState) -> Dict[str, Any]:
        """
        Execute mind-map construction with layout positioning.
        
        Args:
            state: Current mind-map workflow state
            
        Returns:
            Updated state with complete mindmap_data and nodes
        """
        try:
            seed_paper = state.get("seed_paper")
            similar_papers = state.get("similar_papers", [])
            edges = state.get("edges", [])
            summaries = state.get("summaries", {})
            
            if not seed_paper:
                logger.error("No seed paper found in state")
                return {
                    "errors": ["No seed paper found in state"],
                    "messages": [Message(role="assistant", content="Error: No seed paper found")]
                }
            
            logger.info(f"Building mind-map with {len(similar_papers)} similar papers")
            
            # Create complete node list with positioning
            all_papers = [seed_paper] + similar_papers
            nodes = self._create_positioned_nodes(all_papers, summaries, state)
            
            # Create final mind-map data structure
            mindmap_data = self._create_mindmap_data(nodes, edges, seed_paper, state)
            
            # Generate summary of the mind-map generation process
            generation_summary = self._create_generation_summary(state, nodes, edges)
            
            logger.info(f"Successfully built mind-map with {len(nodes)} nodes and {len(edges)} edges")
            
            return {
                "nodes": nodes,
                "mindmap_data": mindmap_data,
                "generation_summary": generation_summary,
                "current_node": "build_mindmap",
                "messages": [Message(
                    role="assistant", 
                    content=f"Built mind-map with {len(nodes)} nodes and {len(edges)} connections"
                )]
            }
            
        except Exception as e:
            logger.error(f"Error in build mind-map: {str(e)}")
            return {
                "errors": [f"Mind-map construction failed: {str(e)}"],
                "messages": [Message(role="assistant", content=f"Error building mind-map: {str(e)}")]
            }
    
    def _create_positioned_nodes(
        self, 
        papers: List[PaperNode], 
        summaries: Dict[int, str],
        state: MindMapState
    ) -> List[PaperNode]:
        """
        Create nodes with layout positioning.
        
        Args:
            papers: List of paper nodes
            summaries: Dictionary of paper summaries
            state: Current workflow state
            
        Returns:
            List of positioned nodes
        """
        layout_algorithm = state.get("layout_algorithm", self.default_layout)
        
        if layout_algorithm == "circular":
            return self._create_circular_layout(papers, summaries)
        elif layout_algorithm == "hierarchical":
            return self._create_hierarchical_layout(papers, summaries)
        else:  # Default to force-directed layout positions
            return self._create_force_layout(papers, summaries)
    
    def _create_circular_layout(
        self, 
        papers: List[PaperNode], 
        summaries: Dict[int, str]
    ) -> List[PaperNode]:
        """
        Create circular layout with seed at center.
        
        Args:
            papers: List of paper nodes
            summaries: Dictionary of paper summaries
            
        Returns:
            List of positioned nodes
        """
        positioned_nodes = []
        
        # Seed paper at center
        seed_paper = papers[0]  # First paper is always seed
        seed_node = seed_paper.copy()
        seed_node.update({
            "x": self.canvas_width / 2,
            "y": self.canvas_height / 2,
            "summary": summaries.get(seed_paper["id"], "")
        })
        positioned_nodes.append(seed_node)
        
        # Other papers in circle around seed
        similar_papers = papers[1:]
        if similar_papers:
            radius = min(self.canvas_width, self.canvas_height) * 0.3
            angle_step = 2 * math.pi / len(similar_papers)
            
            for i, paper in enumerate(similar_papers):
                angle = i * angle_step
                x = self.canvas_width / 2 + radius * math.cos(angle)
                y = self.canvas_height / 2 + radius * math.sin(angle)
                
                node = paper.copy()
                node.update({
                    "x": x,
                    "y": y,
                    "summary": summaries.get(paper["id"], ""),
                    "keywords": paper.get("keywords", []),
                })
                positioned_nodes.append(node)
        
        return positioned_nodes
    
    def _create_hierarchical_layout(
        self, 
        papers: List[PaperNode], 
        summaries: Dict[int, str]
    ) -> List[PaperNode]:
        """
        Create hierarchical layout sorted by similarity score.
        
        Args:
            papers: List of paper nodes
            summaries: Dictionary of paper summaries
            
        Returns:
            List of positioned nodes
        """
        positioned_nodes = []
        
        # Seed paper at top center
        seed_paper = papers[0]
        seed_node = seed_paper.copy()
        seed_node.update({
            "x": self.canvas_width / 2,
            "y": 100,
            "summary": summaries.get(seed_paper["id"], "")
        })
        positioned_nodes.append(seed_node)
        
        # Sort similar papers by similarity score
        similar_papers = sorted(papers[1:], key=lambda p: p.get("similarity_score", 0), reverse=True)
        
        if similar_papers:
            # Arrange in rows below seed
            papers_per_row = 5
            row_height = 150
            start_y = 250
            
            for i, paper in enumerate(similar_papers):
                row = i // papers_per_row
                col = i % papers_per_row
                
                # Center each row
                row_width = min(len(similar_papers) - row * papers_per_row, papers_per_row)
                x_offset = (self.canvas_width - (row_width - 1) * 200) / 2
                
                x = x_offset + col * 200
                y = start_y + row * row_height
                
                node = paper.copy()
                node.update({
                    "x": x,
                    "y": y,
                    "summary": summaries.get(paper["id"], ""),
                    "keywords": paper.get("keywords", []),
                })
                positioned_nodes.append(node)
        
        return positioned_nodes
    
    def _create_force_layout(
        self, 
        papers: List[PaperNode], 
        summaries: Dict[int, str]
    ) -> List[PaperNode]:
        """
        Create force-directed layout with initial positioning.
        
        Args:
            papers: List of paper nodes
            summaries: Dictionary of paper summaries
            
        Returns:
            List of positioned nodes with initial force-layout positions
        """
        positioned_nodes = []
        
        # Seed paper at center
        seed_paper = papers[0]
        seed_node = seed_paper.copy()
        seed_node.update({
            "x": self.canvas_width / 2,
            "y": self.canvas_height / 2,
            "summary": summaries.get(seed_paper["id"], "")
        })
        positioned_nodes.append(seed_node)
        
        # Similar papers positioned based on similarity score
        similar_papers = papers[1:]
        if similar_papers:
            for i, paper in enumerate(similar_papers):
                # Use similarity score to determine distance from center
                similarity = paper.get("similarity_score", 0.5)
                base_radius = min(self.canvas_width, self.canvas_height) * 0.2
                radius = base_radius + (1 - similarity) * base_radius
                
                # Distribute around circle with some randomness
                angle = (i / len(similar_papers)) * 2 * math.pi
                # Add slight randomness to avoid perfect circles
                angle += (hash(paper["id"]) % 100) / 100 * 0.5
                
                x = self.canvas_width / 2 + radius * math.cos(angle)
                y = self.canvas_height / 2 + radius * math.sin(angle)
                
                # Ensure nodes stay within canvas bounds
                x = max(50, min(self.canvas_width - 50, x))
                y = max(50, min(self.canvas_height - 50, y))
                
                node = paper.copy()
                node.update({
                    "x": x,
                    "y": y,
                    "summary": summaries.get(paper["id"], ""),
                    "keywords": paper.get("keywords", []),
                })
                positioned_nodes.append(node)
        
        return positioned_nodes
    
    def _create_mindmap_data(
        self, 
        nodes: List[PaperNode], 
        edges: List[Dict[str, Any]], 
        seed_paper: PaperNode,
        state: MindMapState
    ) -> Dict[str, Any]:
        """
        Create the final mind-map data dictionary for the frontend.
        """
        # Convert nodes to a simpler dictionary format for JSON serialization
        final_nodes = []
        for node in nodes:
            final_nodes.append({
                "id": node.get("id"),
                "title": node.get("title"),
                "summary": node.get("summary"),
                "similarity_score": node.get("similarity_score"),
                "is_seed": node.get("id") == seed_paper["id"],
                "has_fulltext": node.get("has_fulltext", False),
                "url": node.get("url"),
                "date": node.get("date"),
                "keywords": node.get("keywords", []),
                "position": {"x": node.get("x", 0), "y": node.get("y", 0)},
            })
            
        # Ensure edges use consistent 'source_id' and 'target_id' keys
        final_edges = []
        for edge in edges:
            final_edges.append({
                "source_id": edge.get("source_id"),
                "target_id": edge.get("target_id"),
                "similarity_score": edge.get("similarity_score"),
                "relationship_type": edge.get("relationship_type"),
            })

        return {
            "nodes": final_nodes,
            "edges": final_edges,
            "seed_paper_id": seed_paper["id"],
            "layout_algorithm": state.get("layout_algorithm", self.default_layout),
            "generation_timestamp": state.get("start_time"),
            "parameters": {
                "k_neighbors": state.get("k_neighbors"),
                "similarity_threshold": state.get("similarity_threshold"),
            },
            "statistics": {
                "nodes_count": len(final_nodes),
                "edges_count": len(final_edges),
            },
            "metadata": {
                "llm_model": state.get("llm_model_config", {}).get("model_name"),
            }
        }
    
    def _create_generation_summary(
        self, 
        state: MindMapState, 
        nodes: List[PaperNode], 
        edges: List[Dict[str, Any]]
    ) -> str:
        """
        Create a summary of the mind-map generation process.
        
        Args:
            state: Current workflow state
            nodes: Generated nodes
            edges: Generated edges
            
        Returns:
            Generation summary string
        """
        seed_paper = state.get("seed_paper")
        summaries_count = len(state.get("summaries", {}))
        
        if not seed_paper:
            return "Mind-map generation completed with errors."
        
        similarity_scores = [n.get("similarity_score", 0) for n in nodes[1:]]
        
        summary_parts = [
            f"Generated mind-map for '{seed_paper['title']}'",
            f"Found {len(nodes)-1} related papers with similarities ranging from {min(similarity_scores, default=0):.3f} to {max(similarity_scores, default=0):.3f}",
            f"Created {summaries_count} LLM-powered summaries",
            f"Built {len(edges)} connections using {state.get('layout_algorithm', 'force')} layout"
        ]
        
        return ". ".join(summary_parts) + "."
    
    def get_node_info(self) -> Dict[str, Any]:
        """Get information about this node."""
        return {
            "node_type": "build_mindmap",
            "description": "Constructs final mind-map data structure with layout positioning",
            "inputs": ["seed_paper", "similar_papers", "edges", "summaries"],
            "outputs": ["nodes", "mindmap_data", "generation_summary"]
        }


def create_build_mindmap_node(config: Dict[str, Any]) -> BuildMindMapNode:
    """
    Factory function to create a BuildMindMapNode.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Configured BuildMindMapNode instance
    """
    return BuildMindMapNode(config) 