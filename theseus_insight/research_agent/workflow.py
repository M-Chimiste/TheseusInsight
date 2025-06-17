"""
LangGraph Workflow for Research Agent

Defines the complete research workflow with conditional routing,
state management, and node orchestration for comprehensive research tasks.
"""

import logging
from datetime import datetime
from typing import Dict, Any, Literal
from langgraph.graph import StateGraph, END

from .state import OverallState, Message, create_initial_state, needs_compression
from .nodes import (
    QueryPlannerNode,
    RetrieverUnifiedNode,
    EvidenceSelectorNode,
    FullTextProcessorNode,
    ScratchpadCompressNode,
    AnswerGeneratorNode
)
from .tools import UnifiedSearchTool


class ResearchAgentWorkflow:
    """
    LangGraph workflow for the research agent.
    
    Orchestrates the complete research process from query planning
    through final answer generation with conditional routing based
    on evidence sufficiency and token budget constraints.
    """
    
    def __init__(
        self,
        config: Dict[str, Any],
        unified_search_tool: UnifiedSearchTool,
        max_research_loops: int = 3,
        max_research_context_tokens: int = 15000,
        compress_to_ratio: float = 0.2,
        enable_full_text: bool = True,
        full_text_top_n: int = 20
    ):
        """
        Initialize the research agent workflow.
        
        Args:
            config: Configuration dictionary containing model settings
            unified_search_tool: Configured unified search tool
            max_research_loops: Maximum number of research iterations
            max_research_context_tokens: Token budget for evidence
            compress_to_ratio: Compression ratio for token management
            enable_full_text: Whether to enable full text processing of PDFs
            full_text_top_n: Number of top sources to process for full text
        """
        self.config = config
        self.unified_search_tool = unified_search_tool
        self.max_research_loops = max_research_loops
        self.max_research_context_tokens = max_research_context_tokens
        self.compress_to_ratio = compress_to_ratio
        self.enable_full_text = enable_full_text
        self.full_text_top_n = full_text_top_n
        self.logger = logging.getLogger(__name__)
        
        # Initialize nodes with config instead of model_client
        self.query_planner = QueryPlannerNode(config)
        self.retriever_unified = RetrieverUnifiedNode(unified_search_tool)
        self.evidence_selector = EvidenceSelectorNode(config)
        self.full_text_processor = FullTextProcessorNode(
            config,
            top_n=full_text_top_n,
            enable_processing=enable_full_text,
            max_chunk_tokens=config.get('research_agent_model_config', {}).get('max_chunk_tokens', 8000),
            summary_target_tokens=config.get('research_agent_model_config', {}).get('summary_target_tokens', 1500)
        )
        self.scratchpad_compress = ScratchpadCompressNode(
            config, 
            max_tokens=max_research_context_tokens,
            compression_ratio=compress_to_ratio
        )
        self.answer_generator = AnswerGeneratorNode(config)
        
        # Build the workflow graph
        self.workflow = self._build_workflow()
        # Compile with increased recursion limit and error handling
        self.app = self.workflow.compile()
        
        # Task ID for progress tracking (set when workflow runs)
        self.current_task_id = None
    
    def _build_workflow(self) -> StateGraph:
        """
        Build the LangGraph workflow with conditional routing.
        
        Returns:
            Compiled StateGraph workflow
        """
        # Create the state graph
        workflow = StateGraph(OverallState)
        
        # Add nodes with progress tracking wrappers
        workflow.add_node("query_planner", self._query_planner_with_progress)
        workflow.add_node("retriever_unified", self._retriever_unified_with_progress)
        workflow.add_node("evidence_selector", self._evidence_selector_with_progress)
        workflow.add_node("full_text_processor", self._full_text_processor_with_progress)
        workflow.add_node("scratchpad_compress", self._scratchpad_compress_with_progress)
        workflow.add_node("answer_generator", self._answer_generator_with_progress)
        
        # Set entry point
        workflow.set_entry_point("query_planner")
        
        # Add edges with conditional routing
        workflow.add_edge("query_planner", "retriever_unified")
        workflow.add_edge("retriever_unified", "evidence_selector")
        workflow.add_edge("evidence_selector", "full_text_processor")
        
        # Conditional routing from full_text_processor
        workflow.add_conditional_edges(
            "full_text_processor",
            self._coverage_route,
            {
                "continue_research": "query_planner",
                "compress_evidence": "scratchpad_compress", 
                "generate_answer": "answer_generator"
            }
        )
        
        # From compression, always go to answer generation
        workflow.add_edge("scratchpad_compress", "answer_generator")
        
        # Answer generation is the end
        workflow.add_edge("answer_generator", END)
        
        return workflow
    
    def _coverage_route(self, state: OverallState) -> Literal["continue_research", "compress_evidence", "generate_answer"]:
        """
        Determine the next step based on evidence sufficiency and token budget.
        
        Args:
            state: Current research agent state
            
        Returns:
            Next node to execute
        """
        try:
            loop_count = state.get("research_loop_count", 0)
            is_sufficient = state.get("is_sufficient", False)
            sources_gathered = state.get("sources_gathered", [])
            evidence = state.get("evidence", [])
            
            self.logger.info(f"Coverage routing - Loop count: {loop_count}, Max: {self.max_research_loops}, Sufficient: {is_sufficient}")
            self.logger.info(f"Current state - Sources: {len(sources_gathered)}, Evidence: {len(evidence)}")
            
            # INFINITE LOOP PREVENTION: Force completion in various scenarios
            has_any_evidence = len(sources_gathered) > 0 or len(evidence) > 0
            
            # Force completion if we've hit the maximum research loops
            if loop_count >= self.max_research_loops:
                self.logger.warning(f"Maximum research loops ({self.max_research_loops}) reached - FORCE COMPLETION")
                return self._handle_final_routing(state)
            
            # Force completion if we're on the last allowed loop and have ANY evidence
            if loop_count >= (self.max_research_loops - 1) and has_any_evidence:
                self.logger.warning(f"Final loop ({loop_count + 1}/{self.max_research_loops}) with evidence available - FORCE COMPLETION")
                return self._handle_final_routing(state)
            
            # Force completion if we have substantial evidence regardless of LLM assessment
            substantial_evidence = len(evidence) >= 2 and len(sources_gathered) >= 3
            if substantial_evidence and loop_count >= 1:
                self.logger.warning(f"Loop {loop_count}: Have substantial evidence ({len(evidence)} pieces, {len(sources_gathered)} sources) - FORCE COMPLETION")
                return self._handle_final_routing(state)
            
            # Force completion if we're making no progress (same evidence count as previous loops)
            if loop_count >= 2 and len(evidence) <= 1:
                self.logger.warning(f"Loop {loop_count}: No progress in evidence gathering - FORCE COMPLETION with available evidence")
                return self._handle_final_routing(state)
            
            # Check evidence sufficiency (but with overrides above)
            if not is_sufficient:
                # Evidence is not sufficient, continue research only if we haven't hit safety limits
                self.logger.info(f"Evidence insufficient, continuing research (loop {loop_count + 1})")
                return "continue_research"
            
            # Evidence is sufficient, check token budget
            if needs_compression(state):
                self.logger.info("Evidence sufficient but exceeds token budget, compressing")
                return "compress_evidence"
            
            # Evidence is sufficient and within budget
            self.logger.info("Evidence sufficient and within token budget, generating answer")
            return "generate_answer"
            
        except Exception as e:
            self.logger.error(f"Error in coverage routing: {e}")
            # Fallback to answer generation to prevent infinite loops
            return self._handle_final_routing(state)
    
    def _handle_final_routing(self, state: OverallState) -> Literal["compress_evidence", "generate_answer"]:
        """
        Handle final routing when research loops are exhausted or errors occur.
        
        Args:
            state: Current research agent state
            
        Returns:
            Final routing decision
        """
        # Check if we need compression even for final answer
        if needs_compression(state):
            return "compress_evidence"
        else:
            return "generate_answer"
    
    async def run_research(self, research_question: str, config: Dict[str, Any] = None, task_id: str = None) -> Dict[str, Any]:
        """
        Run the complete research workflow.
        
        Args:
            research_question: The research question to investigate
            config: Optional configuration overrides
            
        Returns:
            Final research results
        """
        try:
            self.logger.info(f"Starting research workflow for: {research_question[:100]}")
            
            # Set task ID for progress tracking
            self.current_task_id = task_id
            
            # Apply configuration overrides if provided
            if config:
                self._apply_config_overrides(config)
            
            # Initialize state
            initial_state = create_initial_state(
                research_question=research_question,
                task_id=task_id or "",
                max_loops=self.max_research_loops,
                max_tokens=self.max_research_context_tokens
            )
            
            # Run the workflow with increased recursion limit
            final_state = await self.app.ainvoke(initial_state, {"recursion_limit": 75})
            
            # Extract results
            results = self._extract_results(final_state)
            
            self.logger.info("Research workflow completed successfully")
            return results
            
        except Exception as e:
            error_str = str(e)
            self.logger.error(f"Error in research workflow: {error_str}")
            
            # Check if it's a recursion limit error and try graceful fallback
            if "recursion_limit" in error_str.lower() or "recursion limit" in error_str.lower():
                self.logger.warning("Recursion limit reached - attempting graceful fallback to answer generation")
                return await self._graceful_fallback_research(research_question, initial_state, error_str)
            
            return {
                "success": False,
                "error": error_str,
                "research_question": research_question,
                "partial_results": None
            }
    
    def run_research_sync(self, research_question: str, config: Dict[str, Any] = None, task_id: str = None) -> Dict[str, Any]:
        """
        Run the research workflow synchronously.
        
        Args:
            research_question: The research question to investigate
            config: Optional configuration overrides
            
        Returns:
            Final research results
        """
        try:
            self.logger.info(f"Starting synchronous research workflow for: {research_question[:100]}")
            
            # Set task ID for progress tracking
            self.current_task_id = task_id
            
            # Apply configuration overrides if provided
            if config:
                self._apply_config_overrides(config)
            
            # Initialize state
            initial_state = create_initial_state(
                research_question=research_question,
                task_id=task_id or "",
                max_loops=self.max_research_loops,
                max_tokens=self.max_research_context_tokens
            )
            
            # Run the workflow synchronously with increased recursion limit
            final_state = self.app.invoke(initial_state, {"recursion_limit": 75})
            
            # Extract results
            results = self._extract_results(final_state)
            
            self.logger.info("Synchronous research workflow completed successfully")
            return results
            
        except Exception as e:
            error_str = str(e)
            self.logger.error(f"Error in synchronous research workflow: {error_str}")
            
            # Check if it's a recursion limit error and try graceful fallback
            if "recursion_limit" in error_str.lower() or "recursion limit" in error_str.lower():
                self.logger.warning("Recursion limit reached - attempting graceful fallback to answer generation")
                return self._graceful_fallback_research_sync(research_question, initial_state, error_str)
            
            return {
                "success": False,
                "error": error_str,
                "research_question": research_question,
                "partial_results": None
            }
    
    def _query_planner_with_progress(self, state: OverallState) -> OverallState:
        """Query planner node with progress tracking."""
        if self.current_task_id:
            self._update_task_progress(self.current_task_id, "query_planner", {
                "status": "Planning research queries",
                "description": "Breaking down your question into focused research queries"
            })
        result = self.query_planner(state)
        if self.current_task_id and "sub_queries" in result:
            self._update_task_progress(self.current_task_id, "query_planner", {
                "status": "Query planning complete",
                "description": f"Generated {len(result.get('sub_queries', []))} focused research queries",
                "sub_queries": result.get('sub_queries', [])
            })
        return result

    def _retriever_unified_with_progress(self, state: OverallState) -> OverallState:
        """Retriever unified node with progress tracking."""
        if self.current_task_id:
            sub_queries = state.get("sub_queries", [])
            self._update_task_progress(self.current_task_id, "retriever_unified", {
                "status": "Searching for sources",
                "description": f"Searching {len(sub_queries)} sub-queries across local database and ArXiv"
            })
        result = self.retriever_unified(state)
        if self.current_task_id and "sources_gathered" in result:
            sources_count = len(result.get('sources_gathered', []))
            # Calculate unique sources for more accurate reporting
            unique_sources = set()
            local_count = 0
            external_count = 0
            for source in result.get('sources_gathered', []):
                paper_info = source.get("paper_info")
                if paper_info:
                    unique_id = paper_info.title or paper_info.url or str(source)
                    unique_sources.add(unique_id)
                    if source.get('source_type') == 'local':
                        local_count += 1
                    elif source.get('source_type') == 'external':
                        external_count += 1
            
            unique_count = len(unique_sources)
            self._update_task_progress(self.current_task_id, "retriever_unified", {
                "status": "Source search complete",
                "description": f"Found {unique_count} unique sources ({local_count} local, {external_count} external)",
                "sources_found": unique_count,
                "total_raw_sources": sources_count
            })
        return result

    def _evidence_selector_with_progress(self, state: OverallState) -> OverallState:
        """Evidence selector node with progress tracking."""
        if self.current_task_id:
            sources_count = len(state.get("sources_gathered", []))
            # Count unique sources by deduplication to give accurate progress
            unique_sources = set()
            for source in state.get("sources_gathered", []):
                paper_info = source.get("paper_info")
                if paper_info:
                    # Use title or URL as unique identifier
                    unique_id = paper_info.title or paper_info.url or str(source)
                    unique_sources.add(unique_id)
            
            unique_count = len(unique_sources)
            self._update_task_progress(self.current_task_id, "evidence_selector", {
                "status": "Evaluating evidence quality",
                "description": f"Evaluating {unique_count} unique sources ({sources_count} total with duplicates)"
            })
        result = self.evidence_selector(state)
        if self.current_task_id:
            evidence_count = len(result.get('evidence', []))
            is_sufficient = result.get('is_sufficient', False)
            loop_count = result.get('research_loop_count', 0)
            self._update_task_progress(self.current_task_id, "evidence_selector", {
                "status": "Evidence evaluation complete",
                "description": f"Selected {evidence_count} pieces of evidence (Loop {loop_count + 1})",
                "evidence_count": evidence_count,
                "is_sufficient": is_sufficient,
                "research_loop": loop_count + 1
            })
        return result

    def _scratchpad_compress_with_progress(self, state: OverallState) -> OverallState:
        """Scratchpad compress node with progress tracking."""
        if self.current_task_id:
            evidence_count = len(state.get("evidence", []))
            self._update_task_progress(self.current_task_id, "scratchpad_compress", {
                "status": "Compressing evidence",
                "description": f"Compressing {evidence_count} pieces of evidence to fit token budget"
            })
        result = self.scratchpad_compress(state)
        if self.current_task_id:
            compressed_notes = result.get('compressed_notes', '')
            self._update_task_progress(self.current_task_id, "scratchpad_compress", {
                "status": "Evidence compression complete",
                "description": f"Compressed evidence to {len(compressed_notes)} characters",
                "compressed_length": len(compressed_notes)
            })
        return result

    def _full_text_processor_with_progress(self, state: OverallState) -> OverallState:
        """Full text processor node with progress tracking."""
        if self.current_task_id:
            judged_sources_count = len(state.get("judged_sources", []))
            self._update_task_progress(self.current_task_id, "full_text_processor", {
                "status": "Processing full text from PDFs",
                "description": f"Extracting full text from top {min(self.full_text_top_n, judged_sources_count)} sources"
            })
            
            # Pass task_id to the state so the node can access it
            state["task_id"] = self.current_task_id
            
        result = self.full_text_processor(state)
        if self.current_task_id:
            full_text_data = result.get('full_text_data', {})
            self._update_task_progress(self.current_task_id, "full_text_processor", {
                "status": "Full text processing complete",
                "description": f"Successfully processed full text from {len(full_text_data)} PDFs",
                "processed_count": len(full_text_data)
            })
        return result

    def _answer_generator_with_progress(self, state: OverallState) -> OverallState:
        """Answer generator node with progress tracking."""
        if self.current_task_id:
            evidence_count = len(state.get("evidence", []))
            sources_count = len(state.get("sources_gathered", []))
            self._update_task_progress(self.current_task_id, "answer_generator", {
                "status": "Generating final report",
                "description": f"Creating comprehensive report from {evidence_count} evidence pieces and {sources_count} sources"
            })
        result = self.answer_generator(state)
        if self.current_task_id:
            final_report = result.get('final_report', '')
            self._update_task_progress(self.current_task_id, "answer_generator", {
                "status": "Research complete",
                "description": f"Generated {len(final_report)} character research report",
                "report_length": len(final_report)
            })
        return result

    def _update_task_progress(self, task_id: str, node_name: str, progress_data: Dict[str, Any]) -> None:
        """
        Update task progress for WebSocket broadcasting.
        
        Args:
            task_id: The research task ID
            node_name: Current node being executed
            progress_data: Progress information for the node
        """
        try:
            # Import here to avoid circular imports
            from ..api.routers.research_agent import research_tasks
            
            if task_id in research_tasks:
                research_tasks[task_id]["progress"] = {
                    "current_node": node_name,
                    "timestamp": datetime.utcnow().isoformat(),
                    **progress_data
                }
                self.logger.info(f"Updated progress for task {task_id}: {node_name} - {progress_data}")
        except Exception as e:
            self.logger.warning(f"Could not update task progress: {e}")

    async def _graceful_fallback_research(self, research_question: str, initial_state: OverallState, error_msg: str) -> Dict[str, Any]:
        """
        Graceful fallback when recursion limit is reached.
        Try to generate an answer with whatever evidence we have.
        
        Args:
            research_question: The original research question
            initial_state: Initial state that was used
            error_msg: The original error message
            
        Returns:
            Research results with fallback answer
        """
        try:
            self.logger.info("Attempting graceful fallback - generating answer with available evidence")
            
            # Create a minimal state with basic information for answer generation
            fallback_state = {
                "messages": initial_state.get("messages", []),
                "original_question": research_question,  # Use the parameter directly for fallback
                "sub_queries": ["General research query (fallback)"],
                "sources_gathered": [],
                "judged_sources": [],
                "evidence": ["Limited evidence available due to research loop timeout."],
                "compressed_notes": "",
                "research_loop_count": self.max_research_loops,
                "is_sufficient": True,  # Force sufficient to generate answer
                "max_loops": self.max_research_loops,
                "current_token_count": 0,
                "max_research_context_tokens": self.max_research_context_tokens,
                "task_id": initial_state.get("task_id", "fallback"),
                "start_time": initial_state.get("start_time"),
                "current_node": "answer_generator",
                "errors": [f"Recursion limit reached: {error_msg}"],
                "warnings": ["Generated fallback answer due to research loop timeout"],
                "final_report": "",
                "citations": []
            }
            
            # Try to run just the answer generator
            answer_result = self.answer_generator(fallback_state)
            fallback_state.update(answer_result)
            
            # Extract results from fallback state
            results = self._extract_results(fallback_state)
            results["success"] = True
            results["fallback_used"] = True
            results["fallback_reason"] = "Recursion limit reached - graceful fallback to answer generation"
            
            self.logger.info("Graceful fallback completed successfully")
            return results
            
        except Exception as fallback_error:
            self.logger.error(f"Graceful fallback also failed: {fallback_error}")
            return {
                "success": False,
                "error": f"Original error: {error_msg}. Fallback error: {str(fallback_error)}",
                "research_question": research_question,
                "fallback_attempted": True,
                "partial_results": None
            }
    
    def _graceful_fallback_research_sync(self, research_question: str, initial_state: OverallState, error_msg: str) -> Dict[str, Any]:
        """
        Synchronous graceful fallback when recursion limit is reached.
        
        Args:
            research_question: The original research question
            initial_state: Initial state that was used
            error_msg: The original error message
            
        Returns:
            Research results with fallback answer
        """
        try:
            self.logger.info("Attempting synchronous graceful fallback - generating answer with available evidence")
            
            # Create a minimal state with basic information for answer generation
            fallback_state = {
                "messages": initial_state.get("messages", []),
                "original_question": research_question,  # Use the parameter directly for fallback
                "sub_queries": ["General research query (fallback)"],
                "sources_gathered": [],
                "judged_sources": [],
                "evidence": ["Limited evidence available due to research loop timeout."],
                "compressed_notes": "",
                "research_loop_count": self.max_research_loops,
                "is_sufficient": True,  # Force sufficient to generate answer
                "max_loops": self.max_research_loops,
                "current_token_count": 0,
                "max_research_context_tokens": self.max_research_context_tokens,
                "task_id": initial_state.get("task_id", "fallback"),
                "start_time": initial_state.get("start_time"),
                "current_node": "answer_generator",
                "errors": [f"Recursion limit reached: {error_msg}"],
                "warnings": ["Generated fallback answer due to research loop timeout"],
                "final_report": "",
                "citations": []
            }
            
            # Try to run just the answer generator
            answer_result = self.answer_generator(fallback_state)
            fallback_state.update(answer_result)
            
            # Extract results from fallback state
            results = self._extract_results(fallback_state)
            results["success"] = True
            results["fallback_used"] = True
            results["fallback_reason"] = "Recursion limit reached - graceful fallback to answer generation"
            
            self.logger.info("Synchronous graceful fallback completed successfully")
            return results
            
        except Exception as fallback_error:
            self.logger.error(f"Synchronous graceful fallback also failed: {fallback_error}")
            return {
                "success": False,
                "error": f"Original error: {error_msg}. Fallback error: {str(fallback_error)}",
                "research_question": research_question,
                "fallback_attempted": True,
                "partial_results": None
            }
    
    def _apply_config_overrides(self, config: Dict[str, Any]) -> None:
        """
        Apply configuration overrides to the workflow.
        
        Args:
            config: Configuration dictionary with overrides
        """
        # Update search configuration
        if "search_config" in config:
            self.retriever_unified.update_search_config(**config["search_config"])
        
        # Update evidence selection parameters
        if "evidence_config" in config:
            evidence_config = config["evidence_config"]
            if "min_evidence_threshold" in evidence_config:
                self.evidence_selector.min_evidence_threshold = evidence_config["min_evidence_threshold"]
            if "quality_threshold" in evidence_config:
                self.evidence_selector.quality_threshold = evidence_config["quality_threshold"]
        
        # Update compression settings
        if "compression_config" in config:
            self.scratchpad_compress.update_compression_settings(**config["compression_config"])
        
        # Update answer generation settings
        if "answer_config" in config:
            self.answer_generator.update_generation_settings(**config["answer_config"])
        
        self.logger.info(f"Applied configuration overrides: {list(config.keys())}")
    
    def _extract_results(self, final_state: OverallState) -> Dict[str, Any]:
        """
        Extract and format results from the final state.
        
        Args:
            final_state: Final state after workflow completion
            
        Returns:
            Formatted results dictionary
        """
        # Extract the final answer from messages
        final_answer = None
        generation_summary = None
        
        # Look for the final answer (last AI message)
        messages = final_state.get("messages", [])
        for message in reversed(messages):
            if isinstance(message, dict) and message.get("content"):
                if final_answer is None:
                    final_answer = message["content"]
                elif generation_summary is None:
                    generation_summary = message["content"]
                    break
            elif hasattr(message, 'content') and message.content:
                if final_answer is None:
                    final_answer = message.content
                elif generation_summary is None:
                    generation_summary = message.content
                    break
        
        # Calculate statistics
        sources_gathered = final_state.get("sources_gathered", [])
        judged_sources = final_state.get("judged_sources", [])
        evidence = final_state.get("evidence", [])
        
        total_sources = len(sources_gathered)
        selected_sources = len(judged_sources)
        evidence_pieces = len(evidence)
        
        # Get the research question from state (more reliable than parsing messages)
        research_question = final_state.get("original_question", "Research question not found")
        
        # Fallback to first message if original_question is not available
        if research_question == "Research question not found" and messages:
            first_msg = messages[0]
            if isinstance(first_msg, dict):
                research_question = first_msg.get("content", "Research question not found")
            elif hasattr(first_msg, 'content'):
                research_question = first_msg.content
        
        return {
            "success": True,
            "research_question": research_question,
            "final_answer": final_answer,
            "generation_summary": generation_summary,
            "statistics": {
                "research_loops": final_state.get("research_loop_count", 0),
                "total_sources_found": total_sources,
                "selected_sources": selected_sources,
                "evidence_pieces": evidence_pieces,
                "evidence_sufficient": final_state.get("is_sufficient", False),
                "compression_used": bool(final_state.get("compressed_notes", ""))
            },
            "sub_queries": final_state.get("sub_queries", []),
            "sources_gathered": sources_gathered,
            "judged_sources": judged_sources,
            "evidence": evidence,
            "compressed_notes": final_state.get("compressed_notes", ""),
            "workflow_messages": [
                {
                    "type": type(msg).__name__ if hasattr(msg, '__class__') else "dict",
                    "content": msg.get("content") if isinstance(msg, dict) else (msg.content if hasattr(msg, 'content') else str(msg))
                }
                for msg in messages
            ]
        }
    
    def get_workflow_info(self) -> Dict[str, Any]:
        """Get information about the workflow configuration."""
        return {
            "workflow_type": "research_agent",
            "max_research_loops": self.max_research_loops,
            "max_research_context_tokens": self.max_research_context_tokens,
            "compress_to_ratio": self.compress_to_ratio,
            "nodes": {
                "query_planner": self.query_planner.get_node_info(),
                "retriever_unified": self.retriever_unified.get_node_info(),
                "evidence_selector": self.evidence_selector.get_node_info(),
                "scratchpad_compress": self.scratchpad_compress.get_node_info(),
                "answer_generator": self.answer_generator.get_node_info()
            },
            "search_capabilities": self.unified_search_tool.get_search_statistics()
        }
    
    def update_workflow_config(
        self,
        max_research_loops: int = None,
        max_research_context_tokens: int = None,
        compress_to_ratio: float = None
    ) -> None:
        """
        Update workflow-level configuration.
        
        Args:
            max_research_loops: New maximum research loops
            max_research_context_tokens: New token budget
            compress_to_ratio: New compression ratio
        """
        if max_research_loops is not None:
            self.max_research_loops = max_research_loops
        if max_research_context_tokens is not None:
            self.max_research_context_tokens = max_research_context_tokens
            self.scratchpad_compress.max_tokens = max_research_context_tokens
        if compress_to_ratio is not None:
            self.compress_to_ratio = compress_to_ratio
            self.scratchpad_compress.compression_ratio = compress_to_ratio
        
        self.logger.info(f"Updated workflow config: loops={self.max_research_loops}, "
                        f"tokens={self.max_research_context_tokens}, ratio={self.compress_to_ratio}")


def create_research_workflow(
    config: Dict[str, Any],
    unified_search_tool: UnifiedSearchTool,
    **workflow_config
) -> ResearchAgentWorkflow:
    """
    Factory function to create a research agent workflow.
    
    Args:
        config: Configuration dictionary containing model settings
        unified_search_tool: Configured unified search tool
        **workflow_config: Additional workflow configuration parameters
                         - enable_full_text: bool (default True)
                         - full_text_top_n: int (default 20)
                         - max_research_loops: int (default 3)
                         - max_research_context_tokens: int (default 15000)
                         - compress_to_ratio: float (default 0.2)
        
    Returns:
        Configured ResearchAgentWorkflow instance
    """
    return ResearchAgentWorkflow(
        config=config,
        unified_search_tool=unified_search_tool,
        max_research_loops=workflow_config.get('max_research_loops', 3),
        max_research_context_tokens=workflow_config.get('max_research_context_tokens', 15000),
        compress_to_ratio=workflow_config.get('compress_to_ratio', 0.2),
        enable_full_text=workflow_config.get('enable_full_text', True),
        full_text_top_n=workflow_config.get('full_text_top_n', 20)
    ) 