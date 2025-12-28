"""
Multi-agent research orchestrator for TheseusInsight.

This module provides the main orchestration system that coordinates the entire
multi-agent research workflow, from question generation through agent execution
to final synthesis, following the make-it-heavy methodology.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Callable, Union
from dataclasses import dataclass

from .agent_types import AgentType, get_default_agent_configuration, validate_agent_configuration, get_agent_specialization
from .question_generator import QuestionGenerator, GeneratedQuestion, QuestionGenerationResult
from .agent_manager import AgentManager, AgentResult, AgentProgress
from .synthesis_agent import SynthesisAgent, SynthesisResult
from .tools.unified_search import UnifiedSearchTool

logger = logging.getLogger(__name__)


@dataclass
class OrchestrationConfig:
    """Configuration for multi-agent orchestration."""
    parallel_agents: int = 4
    task_timeout: int = 300
    max_concurrent_agents: int = 6
    agent_types: Optional[List[AgentType]] = None
    synthesis_config: Optional[Dict[str, Any]] = None
    question_generation_config: Optional[Dict[str, Any]] = None


@dataclass
class OrchestrationProgress:
    """Progress tracking for the entire orchestration."""
    phase: str  # "question_generation", "agent_execution", "synthesis", "completed"
    overall_progress: float
    agents_progress: Dict[int, AgentProgress]
    current_status: str
    estimated_completion: Optional[datetime] = None
    error_message: Optional[str] = None


@dataclass
class OrchestrationResult:
    """Final result of multi-agent orchestration."""
    original_question: str
    final_answer: str
    generation_summary: str
    
    # Question generation results
    generated_questions: List[GeneratedQuestion]
    question_generation_success: bool
    
    # Agent execution results
    agent_results: List[AgentResult]
    successful_agents: int
    failed_agents: int
    
    # Synthesis results
    synthesis_result: SynthesisResult
    
    # Overall metadata
    execution_time: float
    success: bool
    error_message: Optional[str] = None
    
    # Make compatible with existing workflow results
    @property
    def statistics(self) -> Dict[str, Any]:
        """Generate statistics compatible with existing workflow."""
        return {
            "research_loops": 1,  # Multi-agent is conceptually one "loop"
            "total_sources_found": sum(len(r.sources_gathered) for r in self.agent_results),
            "selected_sources": len([r for r in self.agent_results if r.success]),
            "evidence_pieces": self.successful_agents,
            "evidence_sufficient": self.success,
            "compression_used": False,  # Multi-agent doesn't use compression
            "agents_used": len(self.agent_results),
            "synthesis_confidence": self.synthesis_result.metadata.confidence_score if self.synthesis_result else 0.0
        }
    
    @property
    def sub_queries(self) -> List[str]:
        """Get sub-queries for compatibility."""
        return [q.question for q in self.generated_questions]
    
    @property
    def sources_gathered(self) -> List[Dict[str, Any]]:
        """Get all sources for compatibility."""
        all_sources = []
        for result in self.agent_results:
            all_sources.extend(result.sources_gathered)
        return all_sources
    
    @property
    def judged_sources(self) -> List[Dict[str, Any]]:
        """Get judged sources for compatibility (same as sources for multi-agent)."""
        return self.sources_gathered
    
    @property
    def evidence(self) -> List[str]:
        """Get evidence pieces for compatibility."""
        return [result.response for result in self.agent_results if result.success]
    
    @property
    def compressed_notes(self) -> str:
        """Get compressed notes for compatibility (synthesis summary)."""
        return self.generation_summary
    
    @property
    def workflow_messages(self) -> List[Dict[str, Any]]:
        """Get workflow messages for compatibility."""
        messages = []
        
        # Question generation message
        messages.append({
            "type": "question_generation",
            "content": f"Generated {len(self.generated_questions)} specialized research questions",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        # Agent execution messages
        for result in self.agent_results:
            messages.append({
                "type": "agent_execution",
                "agent_id": result.agent_id,
                "agent_type": result.agent_type.value,
                "content": f"Agent completed research with {len(result.sources_gathered)} sources",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "success": result.success
            })
        
        # Synthesis message
        if self.synthesis_result:
            messages.append({
                "type": "synthesis",
                "content": self.synthesis_result.generation_summary,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "success": self.synthesis_result.success
            })
        
        return messages


class MultiAgentOrchestrator:
    """
    Main orchestrator for multi-agent research workflow.
    
    Coordinates the entire process:
    1. Question generation - decompose user question into specialized sub-questions
    2. Agent execution - run multiple specialized agents in parallel
    3. Synthesis - combine agent responses into comprehensive final answer
    """
    
    def __init__(
        self,
        model_config: Dict[str, Any],
        search_tool: UnifiedSearchTool,
        config: Optional[OrchestrationConfig] = None
    ):
        """
        Initialize the multi-agent orchestrator.
        
        Args:
            model_config: Configuration for LLM models
            search_tool: Unified search tool for research
            config: Optional orchestration configuration
        """
        self.model_config = model_config
        self.search_tool = search_tool
        self.config = config or OrchestrationConfig()
        
        # Initialize components
        self.question_generator = QuestionGenerator(model_config)
        self.agent_manager = AgentManager(
            model_config=model_config,
            search_tool=search_tool,
            max_concurrent_agents=self.config.max_concurrent_agents,
            task_timeout=self.config.task_timeout
        )
        self.synthesis_agent = SynthesisAgent(model_config)
        
        # Progress tracking
        self.current_progress = OrchestrationProgress(
            phase="idle",
            overall_progress=0.0,
            agents_progress={},
            current_status="Ready to start research"
        )
        
        # Task ID for progress tracking
        self.current_task_id: Optional[str] = None
        
    async def orchestrate_research(
        self,
        research_question: str,
        task_id: Optional[str] = None,
        progress_callback: Optional[Callable[[str, OrchestrationProgress], None]] = None,
        config_overrides: Optional[Dict[str, Any]] = None
    ) -> OrchestrationResult:
        """
        Orchestrate the complete multi-agent research workflow.
        
        Args:
            research_question: The original research question
            task_id: Optional task ID for progress tracking
            progress_callback: Optional callback for progress updates
            config_overrides: Optional configuration overrides
            
        Returns:
            OrchestrationResult with comprehensive research findings
        """
        
        start_time = time.time()
        self.current_task_id = task_id
        
        logger.info(f"Starting multi-agent orchestration for: {research_question[:100]}")
        
        try:
            # Apply configuration overrides
            effective_config = self._apply_config_overrides(config_overrides)
            
            # Phase 1: Question Generation
            self._update_progress(
                phase="question_generation",
                overall_progress=0.1,
                current_status="Generating specialized research questions",
                progress_callback=progress_callback
            )
            
            question_result = await self._generate_questions(
                research_question, effective_config
            )
            
            if not question_result.success or not question_result.generated_questions:
                return self._create_failed_result(
                    research_question,
                    "Question generation failed",
                    time.time() - start_time,
                    question_result=question_result  # Fix: use correct parameter name
                )
            
            # Phase 2: Agent Execution
            self._update_progress(
                phase="agent_execution",
                overall_progress=0.2,
                current_status=f"Executing {len(question_result.generated_questions)} specialized research agents",
                progress_callback=progress_callback
            )
            
            agent_results = await self._execute_agents(
                question_result.generated_questions,
                progress_callback
            )
            
            # Check if we have any successful results
            successful_results = [r for r in agent_results if r.success]
            if not successful_results:
                return self._create_failed_result(
                    research_question,
                    "All agents failed to complete research",
                    time.time() - start_time,
                    question_result=question_result,
                    agent_results=agent_results
                )
            
            # Phase 3: Synthesis
            self._update_progress(
                phase="synthesis",
                overall_progress=0.8,
                current_status="Synthesizing agent responses into final answer",
                progress_callback=progress_callback
            )
            
            synthesis_result = await self._synthesize_responses(
                research_question,
                agent_results,
                effective_config.get("synthesis_config")
            )
            
            # Phase 4: Completion
            execution_time = time.time() - start_time
            
            self._update_progress(
                phase="completed",
                overall_progress=1.0,
                current_status="Multi-agent research completed successfully",
                progress_callback=progress_callback
            )
            
            # Create final result
            result = OrchestrationResult(
                original_question=research_question,
                final_answer=synthesis_result.final_answer,
                generation_summary=synthesis_result.generation_summary,
                generated_questions=question_result.generated_questions,
                question_generation_success=question_result.success,
                agent_results=agent_results,
                successful_agents=len(successful_results),
                failed_agents=len(agent_results) - len(successful_results),
                synthesis_result=synthesis_result,
                execution_time=execution_time,
                success=synthesis_result.success
            )
            
            logger.info(f"Multi-agent orchestration completed in {execution_time:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"Orchestration failed: {e}")
            
            self._update_progress(
                phase="failed",
                overall_progress=0.0,
                current_status="Multi-agent research failed",
                error_message=str(e),
                progress_callback=progress_callback
            )
            
            return self._create_failed_result(
                research_question,
                str(e),
                time.time() - start_time
            )
    
    async def _generate_questions(
        self,
        research_question: str,
        config: Dict[str, Any]
    ) -> QuestionGenerationResult:
        """Generate specialized questions for each agent."""
        
        # Determine agent configuration
        if self.config.agent_types:
            agent_types = self.config.agent_types
        else:
            agent_types = get_default_agent_configuration(self.config.parallel_agents)
        
        # Validate configuration
        if not validate_agent_configuration(agent_types):
            logger.error(f"Invalid agent configuration: {agent_types}")
            agent_types = get_default_agent_configuration(4)  # Fallback
        
        # Generate questions
        return await self.question_generator.generate_questions(
            research_question=research_question,
            agent_types=agent_types,
            context=config.get("question_generation_config")
        )
    
    async def _execute_agents(
        self,
        questions: List[GeneratedQuestion],
        progress_callback: Optional[Callable[[str, OrchestrationProgress], None]] = None
    ) -> List[AgentResult]:
        """Execute all research agents in parallel."""
        
        def agent_progress_wrapper(agent_id: int, progress: AgentProgress):
            # Update our progress tracking
            self.current_progress.agents_progress[agent_id] = progress
            
            # Calculate overall progress (20% to 80% during agent execution)
            completed_agents = len([p for p in self.current_progress.agents_progress.values() 
                                  if p.status.value in ["completed", "failed", "cancelled"]])
            total_agents = len(questions)
            
            if total_agents > 0:
                agent_progress_ratio = completed_agents / total_agents
                overall_progress = 0.2 + (agent_progress_ratio * 0.6)  # 20% to 80%
                
                self._update_progress(
                    overall_progress=overall_progress,
                    current_status=f"Running agents: {completed_agents}/{total_agents} completed",
                    progress_callback=progress_callback
                )
        
        return await self.agent_manager.execute_agents(
            questions=questions,
            progress_callback=agent_progress_wrapper
        )
    
    async def _synthesize_responses(
        self,
        original_question: str,
        agent_results: List[AgentResult],
        synthesis_config: Optional[Dict[str, Any]] = None
    ) -> SynthesisResult:
        """Synthesize agent responses into final answer."""
        
        return await self.synthesis_agent.synthesize_responses(
            original_question=original_question,
            agent_results=agent_results,
            synthesis_config=synthesis_config
        )
    
    def _apply_config_overrides(
        self, 
        config_overrides: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Apply configuration overrides to base configuration."""
        
        base_config = {
            "parallel_agents": self.config.parallel_agents,
            "task_timeout": self.config.task_timeout,
            "max_concurrent_agents": self.config.max_concurrent_agents,
            "agent_types": self.config.agent_types,
            "synthesis_config": self.config.synthesis_config,
            "question_generation_config": self.config.question_generation_config
        }
        
        if config_overrides:
            base_config.update(config_overrides)
        
        return base_config
    
    def _update_progress(
        self,
        phase: Optional[str] = None,
        overall_progress: Optional[float] = None,
        current_status: Optional[str] = None,
        error_message: Optional[str] = None,
        progress_callback: Optional[Callable[[str, OrchestrationProgress], None]] = None
    ):
        """Update orchestration progress and notify callback."""
        
        if phase is not None:
            self.current_progress.phase = phase
        if overall_progress is not None:
            self.current_progress.overall_progress = overall_progress
        if current_status is not None:
            self.current_progress.current_status = current_status
        if error_message is not None:
            self.current_progress.error_message = error_message
        
        # Estimate completion time
        if overall_progress and overall_progress > 0.1:
            # Simple linear estimation based on current progress
            estimated_total_time = time.time() / overall_progress
            self.current_progress.estimated_completion = datetime.now(timezone.utc)
        
        # Notify callback
        if progress_callback and self.current_task_id:
            try:
                progress_callback(self.current_task_id, self.current_progress)
            except Exception as e:
                logger.error(f"Progress callback failed: {e}")
    
    def _create_failed_result(
        self,
        research_question: str,
        error_message: str,
        execution_time: float,
        question_result: Optional[QuestionGenerationResult] = None,
        agent_results: Optional[List[AgentResult]] = None
    ) -> OrchestrationResult:
        """Create a failed orchestration result."""
        
        # Create empty/failed components for missing parts
        if question_result is None:
            question_result = QuestionGenerationResult(
                original_question=research_question,
                generated_questions=[],
                generation_reasoning="Question generation failed",
                success=False,
                error_message=error_message
            )
        
        if agent_results is None:
            agent_results = []
        
        # Create failed synthesis result
        from .synthesis_agent import SynthesisMetadata
        failed_synthesis = SynthesisResult(
            final_answer=f"Multi-agent research failed: {error_message}",
            generation_summary=f"Research orchestration failed during execution: {error_message}",
            agent_contributions={},
            conflicts_found=[],
            metadata=SynthesisMetadata(
                total_agents=len(agent_results),
                successful_agents=len([r for r in agent_results if r.success]),
                failed_agents=len([r for r in agent_results if not r.success]),
                conflicts_identified=0,
                conflicts_resolved=0,
                synthesis_strategy="failed",
                confidence_score=0.0,
                sources_integrated=0
            ),
            success=False,
            error_message=error_message
        )
        
        return OrchestrationResult(
            original_question=research_question,
            final_answer=failed_synthesis.final_answer,
            generation_summary=failed_synthesis.generation_summary,
            generated_questions=question_result.generated_questions,
            question_generation_success=question_result.success,
            agent_results=agent_results,
            successful_agents=len([r for r in agent_results if r.success]),
            failed_agents=len([r for r in agent_results if not r.success]),
            synthesis_result=failed_synthesis,
            execution_time=execution_time,
            success=False,
            error_message=error_message
        )
    
    def cancel_orchestration(self):
        """Cancel the current orchestration."""
        logger.info("Cancelling multi-agent orchestration")
        
        # Cancel all active agents
        self.agent_manager.cancel_all_agents()
        
        # Update progress
        self.current_progress.phase = "cancelled"
        self.current_progress.current_status = "Multi-agent research cancelled"
        self.current_progress.error_message = "Orchestration was cancelled by user request"
    
    def get_current_progress(self) -> OrchestrationProgress:
        """Get current orchestration progress."""
        return self.current_progress
    
    def get_orchestration_info(self) -> Dict[str, Any]:
        """Get information about the orchestration configuration."""
        
        agent_types = self.config.agent_types or get_default_agent_configuration(self.config.parallel_agents)
        
        return {
            "orchestration_type": "multi_agent",
            "parallel_agents": self.config.parallel_agents,
            "max_concurrent_agents": self.config.max_concurrent_agents,
            "task_timeout": self.config.task_timeout,
            "agent_types": [agent_type.value for agent_type in agent_types],
            "agent_specializations": {
                agent_type.value: {
                    "name": specialization.name,
                    "description": specialization.description,
                    "focus_areas": specialization.focus_areas
                }
                for agent_type in set(agent_types)
                for specialization in [get_agent_specialization(agent_type)]
            },
            "model_config": {
                "question_generator": self.model_config.get("question_generator", "default"),
                "agents": {agent_type.value: self.model_config.get(agent_type.value, "default") 
                          for agent_type in set(agent_types)},
                "synthesis_agent": self.model_config.get("synthesis_agent", "default")
            }
        } 