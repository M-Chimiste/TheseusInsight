"""
LangGraph Workflow for Mind-Map Explorer

Defines the complete mind-map generation workflow with state management,
node orchestration, and progress tracking for interactive paper visualization.
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional, Callable
from langgraph.graph import StateGraph, END

from .state import MindMapState, create_initial_mindmap_state, get_progress_summary, has_required_data
from .nodes import (
    SelectSeedNode,
    EmbedSeedNode,
    RetrieverNode,
    MultiOrderRetrieverNode,
    SummariserNode,
    BuildMindMapNode
)

logger = logging.getLogger(__name__)


class MindMapWorkflow:
    """
    LangGraph workflow for the mind-map explorer.
    
    Orchestrates the complete mind-map generation process from seed paper
    selection through final visualization data construction.
    """
    
    def __init__(
        self,
        db,
        config: Dict[str, Any],
        default_k_neighbors: int = 15,
        default_similarity_threshold: float = 0.3,
        default_layout: str = "force"
    ):
        """
        Initialize the mind-map workflow.
        
        Args:
            db: Database instance (PaperDatabase)
            config: Configuration dictionary containing model settings
            default_k_neighbors: Default number of similar papers to find
            default_similarity_threshold: Default similarity threshold
            default_layout: Default layout algorithm
        """
        self.db = db
        self.config = config
        self.default_k_neighbors = default_k_neighbors
        self.default_similarity_threshold = default_similarity_threshold
        self.default_layout = default_layout
        self.logger = logging.getLogger(__name__)
        
        # Initialize nodes (nodes now use repositories directly)
        self.select_seed = SelectSeedNode()
        self.embed_seed = EmbedSeedNode()
        self.retriever = RetrieverNode()
        self.multi_order_retriever = MultiOrderRetrieverNode()
        self.summariser = SummariserNode(config)
        self.build_mindmap = BuildMindMapNode(config)
        
        # Build the workflow graph
        self.workflow = self._build_workflow()
        # Compile the workflow
        self.app = self.workflow.compile()
        
        # Task ID for progress tracking (set when workflow runs)
        self.current_task_id = None
    
    def _build_workflow(self) -> StateGraph:
        """
        Build the LangGraph workflow.
        
        Returns:
            Compiled StateGraph workflow
        """
        # Create the state graph
        workflow = StateGraph(MindMapState)
        
        # Add nodes with progress tracking wrappers
        workflow.add_node("select_seed", self._select_seed_with_progress)
        workflow.add_node("embed_seed", self._embed_seed_with_progress)
        workflow.add_node("retriever", self._retriever_with_progress)
        workflow.add_node("multi_order_retriever", self._multi_order_retriever_with_progress)
        workflow.add_node("summariser", self._summariser_with_progress)
        workflow.add_node("build_mindmap", self._build_mindmap_with_progress)
        
        # Set entry point
        workflow.set_entry_point("select_seed")
        
        # Add conditional routing based on expansion order
        workflow.add_edge("select_seed", "embed_seed")
        workflow.add_conditional_edges(
            "embed_seed",
            self._route_to_retriever,
            {
                "single_order": "retriever",
                "multi_order": "multi_order_retriever"
            }
        )
        workflow.add_edge("retriever", "summariser")
        workflow.add_edge("multi_order_retriever", "summariser")
        workflow.add_edge("summariser", "build_mindmap")
        workflow.add_edge("build_mindmap", END)
        
        return workflow
    
    def _route_to_retriever(self, state: MindMapState) -> str:
        """Route to appropriate retriever based on expansion order."""
        expansion_order = state.get("expansion_order", 1)
        self.logger.info(f"=== ROUTING DECISION ===")
        self.logger.info(f"Expansion order from state: {expansion_order}")
        if expansion_order > 1:
            self.logger.info(f"Routing to MULTI-ORDER retriever (expansion_order={expansion_order})")
            return "multi_order"
        else:
            self.logger.info(f"Routing to SINGLE-ORDER retriever (expansion_order={expansion_order})")
            return "single_order"
    
    async def generate_mindmap(
        self,
        seed_paper_id: int,
        k_neighbors: Optional[int] = None,
        similarity_threshold: Optional[float] = None,
        expansion_order: Optional[int] = None,
        max_nodes_per_order: Optional[int] = None,
        layout_algorithm: Optional[str] = None,
        embedding_model_config: Optional[Dict[str, Any]] = None,
        llm_model_config: Optional[Dict[str, Any]] = None,
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a mind-map for the given seed paper.
        
        Args:
            seed_paper_id: ID of the seed paper
            k_neighbors: Number of similar papers to find
            similarity_threshold: Minimum similarity threshold
            layout_algorithm: Layout algorithm to use
            embedding_model_config: Embedding model configuration
            llm_model_config: LLM model configuration
            task_id: Task ID for progress tracking
            
        Returns:
            Mind-map generation results
        """
        try:
            self.logger.info(f"Starting mind-map generation for paper {seed_paper_id}")
            self.logger.info(f"Task ID: {task_id}")
            self.logger.info(f"Parameters: k={k_neighbors}, threshold={similarity_threshold}, layout={layout_algorithm}")
            
            # Set task ID for progress tracking
            self.current_task_id = task_id
            
            # Initialize state
            self.logger.info("Creating initial state...")
            self.logger.info(f"=== PARAMETERS BEING PASSED ===")
            self.logger.info(f"seed_paper_id: {seed_paper_id}")
            self.logger.info(f"k_neighbors: {k_neighbors} (default: {self.default_k_neighbors})")
            self.logger.info(f"similarity_threshold: {similarity_threshold} (default: {self.default_similarity_threshold})")
            self.logger.info(f"expansion_order: {expansion_order} (default: 1)")
            self.logger.info(f"max_nodes_per_order: {max_nodes_per_order} (default: 20)")
            self.logger.info(f"layout_algorithm: {layout_algorithm}")
            self.logger.info(f"=== END PARAMETERS ===")
            
            initial_state = create_initial_mindmap_state(
                seed_paper_id=seed_paper_id,
                k_neighbors=k_neighbors or self.default_k_neighbors,
                similarity_threshold=similarity_threshold or self.default_similarity_threshold,
                expansion_order=expansion_order or 1,
                max_nodes_per_order=max_nodes_per_order or 20,
                task_id=task_id or "",
                embedding_model_config=embedding_model_config,
                llm_model_config=llm_model_config
            )
            self.logger.info(f"Initial state created with keys: {list(initial_state.keys())}")
            self.logger.info(f"=== ACTUAL STATE VALUES ===")
            self.logger.info(f"State k_neighbors: {initial_state.get('k_neighbors')}")
            self.logger.info(f"State similarity_threshold: {initial_state.get('similarity_threshold')}")
            self.logger.info(f"State expansion_order: {initial_state.get('expansion_order')}")
            self.logger.info(f"State max_nodes_per_order: {initial_state.get('max_nodes_per_order')}")
            self.logger.info(f"=== END STATE VALUES ===")
            self.logger.info(f"LLM model config in state: {initial_state.get('llm_model_config')}")
            self.logger.info(f"Embedding model config in state: {initial_state.get('embedding_model_config')}")
            
            # Set layout algorithm if provided
            if layout_algorithm:
                initial_state["layout_algorithm"] = layout_algorithm
            
            # Set start time
            initial_state["start_time"] = datetime.now().isoformat()
            
            self.logger.info("About to call workflow.ainvoke...")
            self.logger.info(f"Workflow app type: {type(self.app)}")
            
            # Run the workflow
            final_state = await self.app.ainvoke(initial_state)
            
            self.logger.info("Workflow completed successfully!")
            self.logger.info(f"Final state keys: {list(final_state.keys())}")
            
            # Extract results
            results = self._extract_results(final_state)
            
            self.logger.info("Mind-map generation completed successfully")
            self.logger.info(f"Results: success={results.get('success')}, nodes={len(results.get('mindmap_data', {}).get('nodes', []))}")
            return results
            
        except Exception as e:
            error_str = str(e)
            self.logger.error(f"Error in mind-map generation: {error_str}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            
            return {
                "success": False,
                "error": error_str,
                "seed_paper_id": seed_paper_id,
                "mindmap_data": None
            }
    
    def generate_mindmap_sync(
        self,
        seed_paper_id: int,
        k_neighbors: Optional[int] = None,
        similarity_threshold: Optional[float] = None,
        expansion_order: Optional[int] = None,
        max_nodes_per_order: Optional[int] = None,
        layout_algorithm: Optional[str] = None,
        embedding_model_config: Optional[Dict[str, Any]] = None,
        llm_model_config: Optional[Dict[str, Any]] = None,
        task_id: Optional[str] = None,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        Generate a mind-map synchronously for local LLM resource management.
        
        This method uses a fully synchronous workflow to prevent overwhelming
        local hardware with concurrent LLM calls.
        
        Args:
            seed_paper_id: ID of the seed paper
            k_neighbors: Number of similar papers to find
            similarity_threshold: Minimum similarity threshold
            expansion_order: Expansion order for multi-level retrieval
            max_nodes_per_order: Maximum nodes per expansion order
            layout_algorithm: Layout algorithm to use
            embedding_model_config: Embedding model configuration
            llm_model_config: LLM model configuration
            task_id: Task ID for progress tracking
            progress_callback: Sync callback for progress updates
            
        Returns:
            Mind-map generation results
        """
        try:
            self.logger.info(f"=== generate_mindmap_sync STARTED ===")
            self.logger.info(f"Starting synchronous mind-map generation for paper {seed_paper_id}")
            self.logger.info(f"Task ID: {task_id}")
            self.logger.info(f"Progress callback provided: {progress_callback is not None}")
            
            # Set task ID and progress callback for progress tracking
            self.current_task_id = task_id
            self.sync_progress_callback = progress_callback
            
            if progress_callback:
                try:
                    progress_callback("initializing", 5, "Initializing mind-map workflow")
                except Exception as e:
                    self.logger.error(f"Progress callback error: {e}")
            
            # Initialize state
            self.logger.info("Creating initial state...")
            self.logger.info(f"=== PARAMETERS BEING PASSED ===")
            self.logger.info(f"seed_paper_id: {seed_paper_id}")
            self.logger.info(f"k_neighbors: {k_neighbors} (default: {self.default_k_neighbors})")
            self.logger.info(f"similarity_threshold: {similarity_threshold} (default: {self.default_similarity_threshold})")
            self.logger.info(f"expansion_order: {expansion_order} (default: 1)")
            self.logger.info(f"max_nodes_per_order: {max_nodes_per_order} (default: 20)")
            self.logger.info(f"layout_algorithm: {layout_algorithm}")
            self.logger.info(f"=== END PARAMETERS ===")
            
            initial_state = create_initial_mindmap_state(
                seed_paper_id=seed_paper_id,
                k_neighbors=k_neighbors or self.default_k_neighbors,
                similarity_threshold=similarity_threshold or self.default_similarity_threshold,
                expansion_order=expansion_order or 1,
                max_nodes_per_order=max_nodes_per_order or 20,
                task_id=task_id or "",
                embedding_model_config=embedding_model_config,
                llm_model_config=llm_model_config
            )
            self.logger.info(f"Initial state created with keys: {list(initial_state.keys())}")
            self.logger.info(f"=== ACTUAL STATE VALUES ===")
            self.logger.info(f"State k_neighbors: {initial_state.get('k_neighbors')}")
            self.logger.info(f"State similarity_threshold: {initial_state.get('similarity_threshold')}")
            self.logger.info(f"State expansion_order: {initial_state.get('expansion_order')}")
            self.logger.info(f"State max_nodes_per_order: {initial_state.get('max_nodes_per_order')}")
            self.logger.info(f"=== END STATE VALUES ===")
            self.logger.info(f"LLM model config in state: {initial_state.get('llm_model_config')}")
            self.logger.info(f"Embedding model config in state: {initial_state.get('embedding_model_config')}")
            
            # Set layout algorithm if provided
            if layout_algorithm:
                initial_state["layout_algorithm"] = layout_algorithm
            
            # Set start time
            initial_state["start_time"] = datetime.now().isoformat()
            
            self.logger.info("About to call workflow.invoke (synchronous)...")
            # Create and use a synchronous workflow for sync execution
            sync_workflow = self._build_sync_workflow()
            sync_app = sync_workflow.compile()
            
            # Run the workflow synchronously
            final_state = sync_app.invoke(initial_state)
            
            self.logger.info("Workflow completed successfully!")
            self.logger.info(f"Final state keys: {list(final_state.keys())}")
            
            # Extract results
            results = self._extract_results(final_state)
            
            if progress_callback:
                try:
                    progress_callback("completed", 100, "Mind-map generation completed")
                except Exception as e:
                    self.logger.error(f"Progress callback error: {e}")
            
            self.logger.info("Synchronous mind-map generation completed successfully")
            self.logger.info(f"Results: success={results.get('success')}, nodes={len(results.get('mindmap_data', {}).get('nodes', []))}")
            self.logger.info("=== generate_mindmap_sync COMPLETED ===")
            return results
            
        except Exception as e:
            error_str = str(e)
            self.logger.error(f"=== generate_mindmap_sync FAILED ===")
            self.logger.error(f"Error in synchronous mind-map generation: {error_str}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            
            if progress_callback:
                try:
                    progress_callback("failed", 0, f"Mind-map generation failed: {error_str}")
                except Exception as callback_error:
                    self.logger.error(f"Error calling failure progress callback: {callback_error}")
            
            return {
                "success": False,
                "error": error_str,
                "seed_paper_id": seed_paper_id,
                "mindmap_data": None
            }
    
    async def _select_seed_with_progress(self, state: MindMapState) -> MindMapState:
        """Select seed node with progress tracking."""
        self.logger.info("=== _select_seed_with_progress STARTED ===")
        self.logger.info(f"Current task ID: {self.current_task_id}")
        self.logger.info(f"Has progress callback: {hasattr(self, 'progress_callback') and self.progress_callback is not None}")
        
        if self.current_task_id and hasattr(self, 'progress_callback') and self.progress_callback:
            try:
                self.logger.info("Calling progress callback for select_seed start...")
                await self.progress_callback("select_seed", 20, f"Retrieving paper {state.get('seed_paper_id')} from database")
                self.logger.info("Progress callback completed successfully")
            except Exception as e:
                self.logger.error(f"Progress callback error: {e}")
        
        self.logger.info("About to call self.select_seed...")
        result = self.select_seed(state)
        self.logger.info(f"select_seed completed, result keys: {list(result.keys()) if result else 'None'}")
        
        if self.current_task_id and "seed_paper" in result and hasattr(self, 'progress_callback') and self.progress_callback:
            try:
                seed_paper = result.get("seed_paper")
                self.logger.info("Calling progress callback for select_seed completion...")
                await self.progress_callback("select_seed", 25, f"Selected: {seed_paper.get('title', 'Unknown Title')}")
                self.logger.info("Progress callback completed successfully")
            except Exception as e:
                self.logger.error(f"Progress callback error: {e}")
        
        self.logger.info("=== _select_seed_with_progress COMPLETED ===")
        return result

    async def _embed_seed_with_progress(self, state: MindMapState) -> MindMapState:
        """Embed seed node with progress tracking."""
        self.logger.info("=== _embed_seed_with_progress STARTED ===")
        
        if self.current_task_id and hasattr(self, 'progress_callback') and self.progress_callback:
            try:
                self.logger.info("Calling progress callback for embed_seed start...")
                await self.progress_callback("embed_seed", 30, "Ensuring seed paper has embedding for similarity search")
                self.logger.info("Progress callback completed successfully")
            except Exception as e:
                self.logger.error(f"Progress callback error: {e}")
        
        self.logger.info("About to call self.embed_seed...")
        result = self.embed_seed(state)
        self.logger.info(f"embed_seed completed, result keys: {list(result.keys()) if result else 'None'}")
        
        if self.current_task_id and hasattr(self, 'progress_callback') and self.progress_callback:
            try:
                self.logger.info("Calling progress callback for embed_seed completion...")
                await self.progress_callback("embed_seed", 35, "Seed paper embedding confirmed")
                self.logger.info("Progress callback completed successfully")
            except Exception as e:
                self.logger.error(f"Progress callback error: {e}")
        
        self.logger.info("=== _embed_seed_with_progress COMPLETED ===")
        return result

    async def _retriever_with_progress(self, state: MindMapState) -> MindMapState:
        """Retriever node with progress tracking."""
        self.logger.info("=== _retriever_with_progress STARTED ===")
        
        if self.current_task_id and hasattr(self, 'progress_callback') and self.progress_callback:
            try:
                k_neighbors = state.get("k_neighbors", 15)
                self.logger.info("Calling progress callback for retriever start...")
                await self.progress_callback("retriever", 40, f"Searching for {k_neighbors} most similar papers")
                self.logger.info("Progress callback completed successfully")
            except Exception as e:
                self.logger.error(f"Progress callback error: {e}")
        
        self.logger.info("About to call self.retriever...")
        result = self.retriever(state)
        self.logger.info(f"retriever completed, result keys: {list(result.keys()) if result else 'None'}")
        
        if self.current_task_id and "similar_papers" in result and hasattr(self, 'progress_callback') and self.progress_callback:
            try:
                similar_count = len(result.get("similar_papers", []))
                self.logger.info("Calling progress callback for retriever completion...")
                await self.progress_callback("retriever", 50, f"Found {similar_count} similar papers")
                self.logger.info("Progress callback completed successfully")
            except Exception as e:
                self.logger.error(f"Progress callback error: {e}")
        
        self.logger.info("=== _retriever_with_progress COMPLETED ===")
        return result

    async def _multi_order_retriever_with_progress(self, state: MindMapState) -> MindMapState:
        """Multi-order retriever node with progress tracking."""
        self.logger.info("=== _multi_order_retriever_with_progress STARTED ===")
        
        if self.current_task_id and hasattr(self, 'progress_callback') and self.progress_callback:
            try:
                expansion_order = state.get("expansion_order", 1)
                max_nodes_per_order = state.get("max_nodes_per_order", 20)
                self.logger.info("Calling progress callback for multi-order retriever start...")
                await self.progress_callback("multi_order_retriever", 40, f"Multi-order expansion: {expansion_order} orders, max {max_nodes_per_order} nodes per order")
                self.logger.info("Progress callback completed successfully")
            except Exception as e:
                self.logger.error(f"Progress callback error: {e}")
        
        self.logger.info("About to call self.multi_order_retriever...")
        result = self.multi_order_retriever(state)
        self.logger.info(f"multi_order_retriever completed, result keys: {list(result.keys()) if result else 'None'}")
        
        if self.current_task_id and "similar_papers" in result and hasattr(self, 'progress_callback') and self.progress_callback:
            try:
                similar_count = len(result.get("similar_papers", []))
                total_papers = len(result.get("all_papers", {}))
                self.logger.info("Calling progress callback for multi-order retriever completion...")
                await self.progress_callback("multi_order_retriever", 50, f"Multi-order expansion complete: {total_papers} total papers found")
                self.logger.info("Progress callback completed successfully")
            except Exception as e:
                self.logger.error(f"Progress callback error: {e}")
        
        self.logger.info("=== _multi_order_retriever_with_progress COMPLETED ===")
        return result

    async def _summariser_with_progress(self, state: MindMapState) -> MindMapState:
        """Summariser node with progress tracking."""
        self.logger.info("=== _summariser_with_progress STARTED ===")
        
        if self.current_task_id and hasattr(self, 'progress_callback') and self.progress_callback:
            try:
                paper_count = len(state.get("similar_papers", [])) + 1  # +1 for seed
                self.logger.info("Calling progress callback for summariser start...")
                await self.progress_callback("summariser", 60, f"Creating LLM-powered summaries for {paper_count} papers")
                self.logger.info("Progress callback completed successfully")
            except Exception as e:
                self.logger.error(f"Progress callback error: {e}")
        
        self.logger.info("About to call self.summariser...")
        result = self.summariser(state)
        self.logger.info(f"summariser completed, result keys: {list(result.keys()) if result else 'None'}")
        
        if self.current_task_id and "summaries" in result and hasattr(self, 'progress_callback') and self.progress_callback:
            try:
                summary_count = len(result.get("summaries", {}))
                self.logger.info("Calling progress callback for summariser completion...")
                await self.progress_callback("summariser", 75, f"Generated {summary_count} paper summaries")
                self.logger.info("Progress callback completed successfully")
            except Exception as e:
                self.logger.error(f"Progress callback error: {e}")
        
        self.logger.info("=== _summariser_with_progress COMPLETED ===")
        return result

    async def _build_mindmap_with_progress(self, state: MindMapState) -> MindMapState:
        """Build mind-map node with progress tracking."""
        self.logger.info("=== _build_mindmap_with_progress STARTED ===")
        
        if self.current_task_id and hasattr(self, 'progress_callback') and self.progress_callback:
            try:
                self.logger.info("Calling progress callback for build_mindmap start...")
                await self.progress_callback("build_mindmap", 80, "Constructing final mind-map with layout positioning")
                self.logger.info("Progress callback completed successfully")
            except Exception as e:
                self.logger.error(f"Progress callback error: {e}")
        
        self.logger.info("About to call self.build_mindmap...")
        result = self.build_mindmap(state)
        self.logger.info(f"build_mindmap completed, result keys: {list(result.keys()) if result else 'None'}")
        
        if self.current_task_id and "mindmap_data" in result and hasattr(self, 'progress_callback') and self.progress_callback:
            try:
                mindmap_data = result.get("mindmap_data", {})
                node_count = len(mindmap_data.get("nodes", []))
                edge_count = len(mindmap_data.get("edges", []))
                self.logger.info("Calling progress callback for build_mindmap completion...")
                await self.progress_callback("build_mindmap", 90, f"Built mind-map with {node_count} nodes and {edge_count} connections")
                self.logger.info("Progress callback completed successfully")
            except Exception as e:
                self.logger.error(f"Progress callback error: {e}")
        
        self.logger.info("=== _build_mindmap_with_progress COMPLETED ===")
        return result

    def _extract_results(self, final_state: MindMapState) -> Dict[str, Any]:
        """
        Extract and format results from the final state.
        
        Args:
            final_state: Final state after workflow completion
            
        Returns:
            Formatted results dictionary
        """
        mindmap_data = final_state.get("mindmap_data", {})
        generation_summary = final_state.get("generation_summary", "")
        errors = final_state.get("errors", [])
        
        return {
            "success": len(errors) == 0,
            "seed_paper_id": final_state.get("seed_paper_id"),
            "mindmap_data": mindmap_data,
            "generation_summary": generation_summary,
            "statistics": {
                "nodes_count": len(mindmap_data.get("nodes", [])),
                "edges_count": len(mindmap_data.get("edges", [])),
                "summaries_generated": len(final_state.get("summaries", {})),
                "layout_algorithm": final_state.get("layout_algorithm", "force")
            },
            "parameters": {
                "k_neighbors": final_state.get("k_neighbors", 15),
                "similarity_threshold": final_state.get("similarity_threshold", 0.3)
            },
            "errors": errors,
            "warnings": final_state.get("warnings", [])
        }
    
    async def run_async(
        self,
        paper_id: int,
        k: int = 15,
        similarity_threshold: float = 0.3,
        layout_algorithm: str = "force",
        model_config_override: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        Run the mind-map workflow asynchronously with progress callback support.
        
        This method is designed to be called by the TaskManager and provides
        progress updates via the callback function.
        
        Args:
            paper_id: ID of the seed paper
            k: Number of similar papers to find
            similarity_threshold: Minimum similarity threshold
            layout_algorithm: Layout algorithm to use
            model_config_override: Model configuration override
            progress_callback: Async callback for progress updates
            
        Returns:
            Mind-map generation results
        """
        self.logger.info(f"=== run_async STARTED ===")
        self.logger.info(f"Paper ID: {paper_id}")
        self.logger.info(f"Progress callback provided: {progress_callback is not None}")
        self.logger.info(f"Progress callback type: {type(progress_callback) if progress_callback else 'None'}")
        
        self.progress_callback = progress_callback
        self.logger.info(f"Set self.progress_callback: {self.progress_callback is not None}")
        
        try:
            if progress_callback:
                self.logger.info("Calling initial progress callback...")
                await progress_callback("initializing", 5, "Initializing mind-map workflow")
                self.logger.info("Initial progress callback completed")
            
            # Determine LLM model configuration
            llm_model_config = model_config_override
            
            if not llm_model_config:
                # Extract from orchestration config
                if "mind_map_config" in self.config and "summarization_model" in self.config["mind_map_config"]:
                    llm_model_config = self.config["mind_map_config"]["summarization_model"].copy()
                
                # Remove trust_remote_code from LLM config as it's only for embedding models
                if llm_model_config and "trust_remote_code" in llm_model_config:
                    del llm_model_config["trust_remote_code"]
            
            # Extract embedding model config
            embedding_model_config = None
            if "embedding_model" in self.config:
                embedding_model_config = self.config["embedding_model"]
            
            if progress_callback:
                self.logger.info("Calling select_seed progress callback...")
                await progress_callback("select_seed", 15, "Selecting seed paper")
                self.logger.info("Select_seed progress callback completed")
            
            # Generate a temporary task ID for internal progress tracking
            import uuid
            internal_task_id = str(uuid.uuid4())
            self.logger.info(f"Generated internal task ID: {internal_task_id}")
            
            # Generate the mind-map with internal task ID for progress tracking
            self.logger.info("About to call generate_mindmap...")
            result = await self.generate_mindmap(
                seed_paper_id=paper_id,
                k_neighbors=k,
                similarity_threshold=similarity_threshold,
                layout_algorithm=layout_algorithm,
                embedding_model_config=embedding_model_config,
                llm_model_config=llm_model_config,
                task_id=internal_task_id
            )
            self.logger.info("generate_mindmap completed")
            
            if progress_callback:
                self.logger.info("Calling completion progress callback...")
                await progress_callback("completed", 100, "Mind-map generation completed")
                self.logger.info("Completion progress callback completed")
            
            self.logger.info("=== run_async COMPLETED ===")
            return result
            
        except Exception as e:
            self.logger.error(f"=== run_async FAILED ===")
            self.logger.error(f"Error: {str(e)}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            
            if progress_callback:
                try:
                    await progress_callback("failed", 0, f"Mind-map generation failed: {str(e)}")
                except Exception as callback_error:
                    self.logger.error(f"Error calling failure progress callback: {callback_error}")
            return {"error": str(e), "success": False}

    def get_workflow_info(self) -> Dict[str, Any]:
        """Get information about the workflow configuration."""
        return {
            "workflow_type": "mindmap_explorer",
            "default_k_neighbors": self.default_k_neighbors,
            "default_similarity_threshold": self.default_similarity_threshold,
            "default_layout": self.default_layout,
            "nodes": {
                "select_seed": self.select_seed.get_node_info(),
                "embed_seed": self.embed_seed.get_node_info(),
                "retriever": self.retriever.get_node_info(),
                "summariser": self.summariser.get_node_info(),
                "build_mindmap": self.build_mindmap.get_node_info()
            }
        }

    def _build_sync_workflow(self) -> StateGraph:
        """Build the synchronous workflow graph for mind-map generation."""
        # Create workflow graph
        workflow = StateGraph(MindMapState)
        
        # Add nodes with synchronous progress tracking wrappers
        workflow.add_node("select_seed", self._select_seed_with_sync_progress)
        workflow.add_node("embed_seed", self._embed_seed_with_sync_progress)
        workflow.add_node("single_order", self._retriever_with_sync_progress)
        workflow.add_node("multi_order", self._multi_order_retriever_with_sync_progress)
        workflow.add_node("summariser", self._summariser_with_sync_progress)
        workflow.add_node("build_mindmap", self._build_mindmap_with_sync_progress)
        
        # Set entry point
        workflow.set_entry_point("select_seed")
        
        # Add edges with conditional routing for retriever selection
        workflow.add_edge("select_seed", "embed_seed")
        workflow.add_conditional_edges(
            "embed_seed",
            self._route_to_retriever,
            {
                "single_order": "single_order",
                "multi_order": "multi_order"
            }
        )
        workflow.add_edge("single_order", "summariser")
        workflow.add_edge("multi_order", "summariser")
        workflow.add_edge("summariser", "build_mindmap")
        workflow.add_edge("build_mindmap", END)
        
        return workflow

    def _select_seed_with_sync_progress(self, state: MindMapState) -> MindMapState:
        """Select seed node with synchronous progress tracking."""
        self.logger.info("=== _select_seed_with_sync_progress STARTED ===")
        self.logger.info(f"Current task ID: {self.current_task_id}")
        self.logger.info(f"Has sync progress callback: {hasattr(self, 'sync_progress_callback') and self.sync_progress_callback is not None}")
        
        if self.current_task_id and hasattr(self, 'sync_progress_callback') and self.sync_progress_callback:
            try:
                self.logger.info("Calling sync progress callback for select_seed start...")
                self.sync_progress_callback("select_seed", 20, f"Retrieving paper {state.get('seed_paper_id')} from database")
                self.logger.info("Sync progress callback completed successfully")
            except Exception as e:
                self.logger.error(f"Sync progress callback error: {e}")
        
        self.logger.info("About to call self.select_seed...")
        result = self.select_seed(state)
        self.logger.info(f"select_seed completed, result keys: {list(result.keys()) if result else 'None'}")
        
        if self.current_task_id and "seed_paper" in result and hasattr(self, 'sync_progress_callback') and self.sync_progress_callback:
            try:
                seed_paper = result.get("seed_paper")
                self.logger.info("Calling sync progress callback for select_seed completion...")
                self.sync_progress_callback("select_seed", 25, f"Selected: {seed_paper.get('title', 'Unknown Title')}")
                self.logger.info("Sync progress callback completed successfully")
            except Exception as e:
                self.logger.error(f"Sync progress callback error: {e}")
        
        self.logger.info("=== _select_seed_with_sync_progress COMPLETED ===")
        return result

    def _embed_seed_with_sync_progress(self, state: MindMapState) -> MindMapState:
        """Embed seed node with synchronous progress tracking."""
        self.logger.info("=== _embed_seed_with_sync_progress STARTED ===")
        
        if self.current_task_id and hasattr(self, 'sync_progress_callback') and self.sync_progress_callback:
            try:
                self.logger.info("Calling sync progress callback for embed_seed start...")
                self.sync_progress_callback("embed_seed", 30, "Ensuring seed paper has embedding for similarity search")
                self.logger.info("Sync progress callback completed successfully")
            except Exception as e:
                self.logger.error(f"Sync progress callback error: {e}")
        
        self.logger.info("About to call self.embed_seed...")
        result = self.embed_seed(state)
        self.logger.info(f"embed_seed completed, result keys: {list(result.keys()) if result else 'None'}")
        
        if self.current_task_id and hasattr(self, 'sync_progress_callback') and self.sync_progress_callback:
            try:
                self.logger.info("Calling sync progress callback for embed_seed completion...")
                self.sync_progress_callback("embed_seed", 35, "Seed paper embedding confirmed")
                self.logger.info("Sync progress callback completed successfully")
            except Exception as e:
                self.logger.error(f"Sync progress callback error: {e}")
        
        self.logger.info("=== _embed_seed_with_sync_progress COMPLETED ===")
        return result

    def _retriever_with_sync_progress(self, state: MindMapState) -> MindMapState:
        """Retriever node with synchronous progress tracking."""
        self.logger.info("=== _retriever_with_sync_progress STARTED ===")
        
        if self.current_task_id and hasattr(self, 'sync_progress_callback') and self.sync_progress_callback:
            try:
                k_neighbors = state.get("k_neighbors", 15)
                self.logger.info("Calling sync progress callback for retriever start...")
                self.sync_progress_callback("retriever", 40, f"Searching for {k_neighbors} most similar papers")
                self.logger.info("Sync progress callback completed successfully")
            except Exception as e:
                self.logger.error(f"Sync progress callback error: {e}")
        
        self.logger.info("About to call self.retriever...")
        result = self.retriever(state)
        self.logger.info(f"retriever completed, result keys: {list(result.keys()) if result else 'None'}")
        
        if self.current_task_id and "similar_papers" in result and hasattr(self, 'sync_progress_callback') and self.sync_progress_callback:
            try:
                similar_count = len(result.get("similar_papers", []))
                self.logger.info("Calling sync progress callback for retriever completion...")
                self.sync_progress_callback("retriever", 50, f"Found {similar_count} similar papers")
                self.logger.info("Sync progress callback completed successfully")
            except Exception as e:
                self.logger.error(f"Sync progress callback error: {e}")
        
        self.logger.info("=== _retriever_with_sync_progress COMPLETED ===")
        return result

    def _multi_order_retriever_with_sync_progress(self, state: MindMapState) -> MindMapState:
        """Multi-order retriever node with synchronous progress tracking."""
        self.logger.info("=== _multi_order_retriever_with_sync_progress STARTED ===")
        
        if self.current_task_id and hasattr(self, 'sync_progress_callback') and self.sync_progress_callback:
            try:
                expansion_order = state.get("expansion_order", 1)
                max_nodes_per_order = state.get("max_nodes_per_order", 20)
                self.logger.info("Calling sync progress callback for multi-order retriever start...")
                self.sync_progress_callback("multi_order_retriever", 40, f"Multi-order expansion: {expansion_order} orders, max {max_nodes_per_order} nodes per order")
                self.logger.info("Sync progress callback completed successfully")
            except Exception as e:
                self.logger.error(f"Sync progress callback error: {e}")
        
        self.logger.info("About to call self.multi_order_retriever...")
        result = self.multi_order_retriever(state)
        self.logger.info(f"multi_order_retriever completed, result keys: {list(result.keys()) if result else 'None'}")
        
        if self.current_task_id and "similar_papers" in result and hasattr(self, 'sync_progress_callback') and self.sync_progress_callback:
            try:
                similar_count = len(result.get("similar_papers", []))
                total_papers = len(result.get("all_papers", {}))
                self.logger.info("Calling sync progress callback for multi-order retriever completion...")
                self.sync_progress_callback("multi_order_retriever", 50, f"Multi-order expansion complete: {total_papers} total papers found")
                self.logger.info("Sync progress callback completed successfully")
            except Exception as e:
                self.logger.error(f"Sync progress callback error: {e}")
        
        self.logger.info("=== _multi_order_retriever_with_sync_progress COMPLETED ===")
        return result

    def _summariser_with_sync_progress(self, state: MindMapState) -> MindMapState:
        """Summariser node with synchronous progress tracking."""
        self.logger.info("=== _summariser_with_sync_progress STARTED ===")
        
        if self.current_task_id and hasattr(self, 'sync_progress_callback') and self.sync_progress_callback:
            try:
                paper_count = len(state.get("similar_papers", [])) + 1  # +1 for seed
                self.logger.info("Calling sync progress callback for summariser start...")
                self.sync_progress_callback("summariser", 60, f"Creating LLM-powered summaries for {paper_count} papers")
                self.logger.info("Sync progress callback completed successfully")
                
                # Pass the callback to the summariser node for granular progress
                self.summariser.sync_progress_callback = self.sync_progress_callback
                
            except Exception as e:
                self.logger.error(f"Sync progress callback error: {e}")
        
        self.logger.info("About to call self.summariser...")
        result = self.summariser(state)
        self.logger.info(f"summariser completed, result keys: {list(result.keys()) if result else 'None'}")
        
        if self.current_task_id and "summaries" in result and hasattr(self, 'sync_progress_callback') and self.sync_progress_callback:
            try:
                summary_count = len(result.get("summaries", {}))
                self.logger.info("Calling sync progress callback for summariser completion...")
                self.sync_progress_callback("summariser", 75, f"Generated {summary_count} paper summaries")
                self.logger.info("Sync progress callback completed successfully")
            except Exception as e:
                self.logger.error(f"Sync progress callback error: {e}")
        
        self.logger.info("=== _summariser_with_sync_progress COMPLETED ===")
        return result

    def _build_mindmap_with_sync_progress(self, state: MindMapState) -> MindMapState:
        """Build mind-map node with synchronous progress tracking."""
        self.logger.info("=== _build_mindmap_with_sync_progress STARTED ===")
        
        if self.current_task_id and hasattr(self, 'sync_progress_callback') and self.sync_progress_callback:
            try:
                self.logger.info("Calling sync progress callback for build_mindmap start...")
                self.sync_progress_callback("build_mindmap", 80, "Constructing final mind-map with layout positioning")
                self.logger.info("Sync progress callback completed successfully")
            except Exception as e:
                self.logger.error(f"Sync progress callback error: {e}")
        
        self.logger.info("About to call self.build_mindmap...")
        result = self.build_mindmap(state)
        self.logger.info(f"build_mindmap completed, result keys: {list(result.keys()) if result else 'None'}")
        
        if self.current_task_id and "mindmap_data" in result and hasattr(self, 'sync_progress_callback') and self.sync_progress_callback:
            try:
                mindmap_data = result.get("mindmap_data", {})
                node_count = len(mindmap_data.get("nodes", []))
                edge_count = len(mindmap_data.get("edges", []))
                self.logger.info("Calling sync progress callback for build_mindmap completion...")
                self.sync_progress_callback("build_mindmap", 90, f"Built mind-map with {node_count} nodes and {edge_count} connections")
                self.logger.info("Sync progress callback completed successfully")
            except Exception as e:
                self.logger.error(f"Sync progress callback error: {e}")
        
        self.logger.info("=== _build_mindmap_with_sync_progress COMPLETED ===")
        return result


def create_mindmap_workflow(
    db,
    config: Dict[str, Any],
    **workflow_config
) -> MindMapWorkflow:
    """
    Factory function to create a mind-map workflow.
    
    Args:
        db: Database instance
        config: Configuration dictionary containing model settings
        **workflow_config: Additional workflow configuration parameters
                         - default_k_neighbors: int (default 15)
                         - default_similarity_threshold: float (default 0.3)
                         - default_layout: str (default "force")
        
    Returns:
        Configured MindMapWorkflow instance
    """
    return MindMapWorkflow(
        db=db,
        config=config,
        default_k_neighbors=workflow_config.get('default_k_neighbors', 15),
        default_similarity_threshold=workflow_config.get('default_similarity_threshold', 0.3),
        default_layout=workflow_config.get('default_layout', 'force')
    ) 