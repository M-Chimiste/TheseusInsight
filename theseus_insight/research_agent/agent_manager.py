"""
Agent management system for multi-agent research orchestration.

This module provides individual agent lifecycle management, execution coordination,
and status tracking for the multi-agent research system.
"""

import asyncio
import logging
import time
import traceback
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor

from .agent_types import AgentType, get_agent_system_prompt
from .question_generator import GeneratedQuestion
from .model_router import get_model
from .tools.unified_search import UnifiedSearchTool

logger = logging.getLogger(__name__)


class AgentStatus(Enum):
    """Agent execution status."""
    QUEUED = "queued"
    INITIALIZING = "initializing"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AgentProgress:
    """Progress tracking for an individual agent."""
    agent_id: int
    agent_type: AgentType
    status: AgentStatus
    current_task: str
    progress_percentage: float = 0.0
    sources_found: int = 0
    execution_time: float = 0.0
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class AgentResult:
    """Result from an individual agent's research."""
    agent_id: int
    agent_type: AgentType
    question: str
    response: str
    sources_gathered: List[Dict[str, Any]] = field(default_factory=list)
    execution_time: float = 0.0
    success: bool = True
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ResearchAgent:
    """
    Individual research agent that executes a specific research question
    using its specialized approach and the available search tools.
    """
    
    def __init__(
        self,
        agent_id: int,
        agent_type: AgentType,
        model_config: Dict[str, Any],
        search_tool: UnifiedSearchTool,
        task_timeout: int = 300
    ):
        """
        Initialize a research agent.
        
        Args:
            agent_id: Unique identifier for this agent
            agent_type: Type of agent specialization
            model_config: Configuration for the LLM model
            search_tool: Unified search tool for research
            task_timeout: Maximum execution time in seconds
        """
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.model_config = model_config
        self.search_tool = search_tool
        self.task_timeout = task_timeout
        
        # Get the appropriate model for this agent type
        self.model = get_model(agent_type.value, model_config)
        
        # Progress tracking
        self.progress = AgentProgress(
            agent_id=agent_id,
            agent_type=agent_type,
            status=AgentStatus.QUEUED,
            current_task="Waiting to start"
        )
        
        # Cancellation support
        self._cancelled = False
    
    async def execute_research(
        self, 
        question: GeneratedQuestion,
        progress_callback: Optional[Callable[[AgentProgress], None]] = None
    ) -> AgentResult:
        """
        Execute research for the given question.
        
        Args:
            question: The specialized question to research
            progress_callback: Optional callback for progress updates
            
        Returns:
            AgentResult with research findings
        """
        start_time = time.time()
        self.progress.started_at = datetime.now(timezone.utc)
        
        try:
            # Update status to initializing
            self._update_progress(
                status=AgentStatus.INITIALIZING,
                current_task="Initializing research agent",
                progress_callback=progress_callback
            )
            
            # Build the system prompt for this agent type
            system_prompt = get_agent_system_prompt(self.agent_type, question.question)
            
            # Update status to processing
            self._update_progress(
                status=AgentStatus.PROCESSING,
                current_task="Conducting research and analysis",
                progress_percentage=0.1,
                progress_callback=progress_callback
            )
            
            # Execute the research workflow
            result = await self._run_research_workflow(
                question, 
                system_prompt, 
                progress_callback
            )
            
            # Update final status
            self.progress.completed_at = datetime.now(timezone.utc)
            execution_time = time.time() - start_time
            
            self._update_progress(
                status=AgentStatus.COMPLETED,
                current_task="Research completed successfully",
                progress_percentage=100.0,
                execution_time=execution_time,
                progress_callback=progress_callback
            )
            
            return AgentResult(
                agent_id=self.agent_id,
                agent_type=self.agent_type,
                question=question.question,
                response=result["response"],
                sources_gathered=result["sources"],
                execution_time=execution_time,
                success=True,
                metadata={
                    "specialization_focus": question.specialization_focus,
                    "search_strategy": question.search_strategy,
                    "sources_count": len(result["sources"])
                }
            )
            
        except asyncio.CancelledError:
            self._update_progress(
                status=AgentStatus.CANCELLED,
                current_task="Research cancelled",
                error_message="Task was cancelled",
                progress_callback=progress_callback
            )
            
            return AgentResult(
                agent_id=self.agent_id,
                agent_type=self.agent_type,
                question=question.question,
                response="Research was cancelled before completion",
                execution_time=time.time() - start_time,
                success=False,
                error_message="Task was cancelled"
            )
            
        except Exception as e:
            logger.error(f"Agent {self.agent_id} failed: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            self._update_progress(
                status=AgentStatus.FAILED,
                current_task="Research failed with error",
                error_message=str(e),
                progress_callback=progress_callback
            )
            
            return AgentResult(
                agent_id=self.agent_id,
                agent_type=self.agent_type,
                question=question.question,
                response=f"Research failed due to error: {str(e)}",
                execution_time=time.time() - start_time,
                success=False,
                error_message=str(e)
            )
    
    async def _run_research_workflow(
        self,
        question: GeneratedQuestion,
        system_prompt: str,
        progress_callback: Optional[Callable[[AgentProgress], None]] = None
    ) -> Dict[str, Any]:
        """Run the core research workflow for this agent."""
        
        # Check for cancellation
        if self._cancelled:
            raise asyncio.CancelledError()
        
        # Step 1: Initial search for sources
        self._update_progress(
            current_task="Searching for relevant sources",
            progress_percentage=20.0,
            progress_callback=progress_callback
        )
        
        # Use the unified search tool to find relevant papers
        search_config = self._get_search_config(question.search_strategy)
        sources = await self._search_for_sources(question.question, search_config)
        
        self._update_progress(
            current_task=f"Found {len(sources)} sources, analyzing content",
            progress_percentage=50.0,
            sources_found=len(sources),
            progress_callback=progress_callback
        )
        
        # Step 2: Process sources and generate response
        if self._cancelled:
            raise asyncio.CancelledError()
            
        # Build context from sources
        context = self._build_context_from_sources(sources)
        
        self._update_progress(
            current_task="Generating research response",
            progress_percentage=80.0,
            progress_callback=progress_callback
        )
        
        # Step 3: Generate response using the LLM
        research_prompt = self._build_research_prompt(
            system_prompt, 
            question.question, 
            context
        )
        
        response = await self._generate_response(research_prompt)
        
        return {
            "response": response,
            "sources": sources
        }
    
    def _get_search_config(self, search_strategy: str) -> Dict[str, Any]:
        """Get search configuration based on the agent's search strategy."""
        
        base_config = {
            "local_limit": 15,
            "external_limit": 10
        }
        
        if search_strategy == "broad_comprehensive":
            return {
                "local_limit": 20,
                "external_limit": 15
            }
        elif search_strategy == "targeted_analytical":
            return {
                "local_limit": 12,
                "external_limit": 8
            }
        elif search_strategy == "verification_focused":
            return {
                "local_limit": 10,
                "external_limit": 12
            }
        elif search_strategy == "alternative_seeking":
            return {
                "local_limit": 8,
                "external_limit": 15
            }
        
        return base_config
    
    async def _search_for_sources(
        self, 
        query: str, 
        search_config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Search for relevant sources using the unified search tool."""
        
        try:
            # Run search in a thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor(max_workers=1) as executor:
                sources = await loop.run_in_executor(
                    executor,
                    lambda: self.search_tool.search(
                        query=query,
                        local_limit=search_config["local_limit"],
                        external_limit=search_config["external_limit"]
                    )
                )
            
            return sources
            
        except Exception as e:
            logger.error(f"Search failed for agent {self.agent_id}: {e}")
            return []
    
    def _build_context_from_sources(self, sources: List[Dict[str, Any]]) -> str:
        """Build context string from retrieved sources."""
        
        if not sources:
            return "No relevant sources found."
        
        context_parts = []
        for i, source in enumerate(sources[:10]):  # Limit to top 10 sources
            title = source.get("title", "Unknown Title")
            abstract = source.get("abstract", "")
            url = source.get("url", "")
            
            source_context = f"Source {i+1}: {title}"
            if abstract:
                # Truncate abstract if too long
                if len(abstract) > 500:
                    abstract = abstract[:500] + "..."
                source_context += f"\nAbstract: {abstract}"
            
            if url:
                source_context += f"\nURL: {url}"
            
            context_parts.append(source_context)
        
        return "\n\n---\n\n".join(context_parts)
    
    def _build_research_prompt(
        self, 
        system_prompt: str, 
        question: str, 
        context: str
    ) -> str:
        """Build the complete research prompt for the LLM."""
        
        return f"""{system_prompt}

Based on the following sources and information, please provide a comprehensive response to the research question.

Research Question: {question}

Available Sources and Information:
{context}

Please provide a thorough analysis that:
1. Addresses the research question directly
2. Uses evidence from the provided sources
3. Applies your specialized perspective ({self.agent_type.value})
4. Includes relevant citations where appropriate
5. Identifies any limitations or gaps in the available information

Response:"""
    
    async def _generate_response(self, prompt: str) -> str:
        """Generate response using the LLM."""
        
        try:
            # Run model inference in a thread pool
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor(max_workers=1) as executor:
                # Fix model invocation - use messages and system_prompt instead of prompt
                messages = [{"role": "user", "content": prompt}]
                response = await loop.run_in_executor(
                    executor,
                    lambda: self.model.invoke(
                        messages=messages,
                        system_prompt=f"You are a specialized research agent focusing on {self.agent_type.value} research.",
                        schema=None
                    )
                )
            
            # ModelClient.invoke() returns a string directly, not an object with .content
            return response
            
        except Exception as e:
            logger.error(f"Response generation failed for agent {self.agent_id}: {e}")
            return f"Failed to generate response: {str(e)}"
    
    def _update_progress(
        self,
        status: Optional[AgentStatus] = None,
        current_task: Optional[str] = None,
        progress_percentage: Optional[float] = None,
        sources_found: Optional[int] = None,
        execution_time: Optional[float] = None,
        error_message: Optional[str] = None,
        progress_callback: Optional[Callable[[AgentProgress], None]] = None
    ):
        """Update agent progress and notify callback."""
        
        if status is not None:
            self.progress.status = status
        if current_task is not None:
            self.progress.current_task = current_task
        if progress_percentage is not None:
            self.progress.progress_percentage = progress_percentage
        if sources_found is not None:
            self.progress.sources_found = sources_found
        if execution_time is not None:
            self.progress.execution_time = execution_time
        if error_message is not None:
            self.progress.error_message = error_message
        
        # Notify callback if provided
        if progress_callback:
            try:
                progress_callback(self.progress)
            except Exception as e:
                logger.error(f"Progress callback failed: {e}")
    
    def cancel(self):
        """Cancel the agent's execution."""
        self._cancelled = True


class AgentManager:
    """
    Manager for coordinating multiple research agents in parallel execution.
    """
    
    def __init__(
        self,
        model_config: Dict[str, Any],
        search_tool: UnifiedSearchTool,
        max_concurrent_agents: int = 6,
        task_timeout: int = 300
    ):
        """
        Initialize the agent manager.
        
        Args:
            model_config: Configuration for LLM models
            search_tool: Unified search tool for research
            max_concurrent_agents: Maximum number of agents to run concurrently
            task_timeout: Default timeout for agent tasks
        """
        self.model_config = model_config
        self.search_tool = search_tool
        self.max_concurrent_agents = max_concurrent_agents
        self.task_timeout = task_timeout
        
        # Active agents tracking
        self.active_agents: Dict[int, ResearchAgent] = {}
        self.agent_tasks: Dict[int, asyncio.Task] = {}
        
    async def execute_agents(
        self,
        questions: List[GeneratedQuestion],
        progress_callback: Optional[Callable[[int, AgentProgress], None]] = None
    ) -> List[AgentResult]:
        """
        Execute multiple research agents in parallel.
        
        Args:
            questions: List of generated questions for agents
            progress_callback: Optional callback for progress updates (agent_id, progress)
            
        Returns:
            List of agent results
        """
        
        logger.info(f"Starting execution of {len(questions)} research agents")
        
        # Create agents
        agents = []
        for question in questions:
            agent = ResearchAgent(
                agent_id=question.agent_id,
                agent_type=question.agent_type,
                model_config=self.model_config,
                search_tool=self.search_tool,
                task_timeout=self.task_timeout
            )
            agents.append(agent)
            self.active_agents[question.agent_id] = agent
        
        # Create progress callback wrapper
        def agent_progress_callback(agent_id: int):
            def callback(progress: AgentProgress):
                if progress_callback:
                    progress_callback(agent_id, progress)
            return callback
        
        # Execute agents in parallel with concurrency limit
        semaphore = asyncio.Semaphore(self.max_concurrent_agents)
        
        async def execute_agent(agent: ResearchAgent, question: GeneratedQuestion):
            async with semaphore:
                return await agent.execute_research(
                    question, 
                    agent_progress_callback(agent.agent_id)
                )
        
        # Start all agent tasks
        tasks = []
        for agent, question in zip(agents, questions):
            task = asyncio.create_task(execute_agent(agent, question))
            tasks.append(task)
            self.agent_tasks[agent.agent_id] = task
        
        try:
            # Wait for all agents to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results and handle any exceptions
            final_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Agent {questions[i].agent_id} failed with exception: {result}")
                    # Create a failed result
                    failed_result = AgentResult(
                        agent_id=questions[i].agent_id,
                        agent_type=questions[i].agent_type,
                        question=questions[i].question,
                        response=f"Agent failed with exception: {str(result)}",
                        execution_time=0.0,
                        success=False,
                        error_message=str(result)
                    )
                    final_results.append(failed_result)
                else:
                    final_results.append(result)
            
            logger.info(f"Completed execution of {len(final_results)} agents")
            return final_results
            
        finally:
            # Clean up
            for agent_id in list(self.active_agents.keys()):
                self.active_agents.pop(agent_id, None)
                self.agent_tasks.pop(agent_id, None)
    
    def cancel_all_agents(self):
        """Cancel all active agents."""
        for agent in self.active_agents.values():
            agent.cancel()
        
        for task in self.agent_tasks.values():
            if not task.done():
                task.cancel()
    
    def get_agent_progress(self, agent_id: int) -> Optional[AgentProgress]:
        """Get progress for a specific agent."""
        agent = self.active_agents.get(agent_id)
        return agent.progress if agent else None
    
    def get_all_agent_progress(self) -> Dict[int, AgentProgress]:
        """Get progress for all active agents."""
        return {
            agent_id: agent.progress 
            for agent_id, agent in self.active_agents.items()
        } 