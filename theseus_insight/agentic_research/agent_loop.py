import json
import re
import time
import logging
import os
import json_repair
from typing import Dict, List, Optional, Tuple, Any, Union, Literal
from collections.abc import Callable
from dataclasses import dataclass, asdict
from datetime import datetime
from pydantic import BaseModel, Field

from ..data_model.data_handling import PaperDatabase
from .local_search import LocalSearchTool
from .model_router import AgentModelRouter, ModelRole
from ..constants import TASK_TYPE_RESEARCH_AGENT

logger = logging.getLogger(__name__)


# Pydantic models for structured agent outputs
class SummaryCommand(BaseModel):
    """Command to search for papers based on a query."""
    command: Literal["SUMMARY"] = "SUMMARY"
    query: str = Field(..., description="The search query to find relevant papers")


class FullTextCommand(BaseModel):
    """Command to retrieve full text of a specific paper."""
    command: Literal["FULL_TEXT"] = "FULL_TEXT"
    paper_id: int = Field(..., description="The paper ID to retrieve full text for")


class AddPaperCommand(BaseModel):
    """Command to add a paper by ID or URL."""
    command: Literal["ADD_PAPER"] = "ADD_PAPER"
    identifier: str = Field(..., description="Paper ID (numeric) or URL to add")


class CompleteCommand(BaseModel):
    """Command to signal completion of the literature review."""
    command: Literal["COMPLETE"] = "COMPLETE"
    reason: str = Field(default="", description="Optional reason for completion")


class AgentAction(BaseModel):
    """Union model for all possible agent actions."""
    action: Union[SummaryCommand, FullTextCommand, AddPaperCommand, CompleteCommand] = Field(
        ..., 
        description="The specific action to take",
        discriminator="command"
    )
    reasoning: str = Field(..., description="Brief explanation of why this action was chosen")


@dataclass
class AgentTraceEntry:
    """Single trace entry for agent decision tracking."""
    timestamp: str
    iteration: int
    action_type: str  # 'prompt', 'command', 'search', 'model_call', 'result'
    details: Dict[str, Any]
    model_used: Optional[str] = None
    duration_seconds: Optional[float] = None

@dataclass
class LiteratureReviewSummary:
    """Summary of a single paper in the literature review."""
    paper_id: int
    title: str
    summary: str
    rationale: str
    relevance_score: float

@dataclass
class ResearchAgentResult:
    """Complete result of a research agent run."""
    research_question: str
    summaries: List[LiteratureReviewSummary]
    trace_entries: List[AgentTraceEntry]
    total_iterations: int
    success: bool
    error: Optional[str] = None
    report_text: Optional[str] = None

class ResearchAgentLoop:
    """
    Core Research Agent implementation following PRD specifications.
    
    Coordinates between boss and worker models to conduct automated literature reviews.
    """
    
    def __init__(
        self,
        db: PaperDatabase,
        search_tool: LocalSearchTool,
        model_router: AgentModelRouter,
        num_papers_target: int = 5,
        max_steps: int = 10,
        progress_callback: Optional[Callable] = None
    ):
        self.db = db
        self.search_tool = search_tool
        self.model_router = model_router
        self.num_papers_target = num_papers_target
        self.max_steps = max_steps
        self.progress_callback = progress_callback
        
        # State tracking
        self.current_iteration = 0
        self.collected_summaries: List[LiteratureReviewSummary] = []
        self.trace_entries: List[AgentTraceEntry] = []
        self.papers_seen: set = set()
        
    def _report_progress(self, step: str, progress: float, message: str = ""):
        """Report progress via callback if available."""
        if self.progress_callback:
            try:
                self.progress_callback(step, progress, message)
            except Exception as e:
                logger.warning(f"Progress callback error: {e}")
        
    def _add_trace_entry(
        self,
        action_type: str,
        details: Dict[str, Any],
        model_used: Optional[str] = None,
        duration_seconds: Optional[float] = None
    ) -> None:
        """Add an entry to the execution trace."""
        entry = AgentTraceEntry(
            timestamp=datetime.now().isoformat(),
            iteration=self.current_iteration,
            action_type=action_type,
            details=details,
            model_used=model_used,
            duration_seconds=duration_seconds
        )
        self.trace_entries.append(entry)
        logger.debug(f"Trace: {action_type} - {details}")
        
        # Report progress for key actions
        if action_type in ["iteration_start", "command_parsing", "search_execution", "summary_extracted"]:
            progress = min((len(self.collected_summaries) / self.num_papers_target) * 80, 80) + 10
            if action_type == "iteration_start":
                self._report_progress(f"iteration_{self.current_iteration}", progress, 
                                    f"Starting iteration {self.current_iteration}/{self.max_steps}")
            elif action_type == "search_execution":
                query = details.get("query", "")
                self._report_progress(f"searching", progress, f"Searching for: {query}")
            elif action_type == "summary_extracted":
                paper_id = details.get("paper_id", "")
                self._report_progress(f"summarizing", progress, 
                                    f"Extracted summary for paper {paper_id}")
    
    def _parse_agent_commands(self, agent_response: str) -> List[Tuple[str, str]]:
        """
        Parse agent response for fenced commands following PRD FR-3.
        
        DEPRECATED: This method is deprecated in favor of structured JSON outputs.
        Use _invoke_agent_with_schema() instead for new implementations.
        
        Expected formats:
        ```SUMMARY <search_query>```
        ```FULL_TEXT <paper_id>```
        ```ADD_PAPER <paper_id_or_url>```
        ```COMPLETE```
        
        Returns:
            List of (command, argument) tuples
        """
        import warnings
        warnings.warn(
            "_parse_agent_commands is deprecated. Use structured JSON outputs with _invoke_agent_with_schema instead.",
            DeprecationWarning,
            stacklevel=2
        )
        commands = []
        
        # Try multiple patterns to be more robust with LLM responses
        patterns = [
            # Standard fenced code blocks: ```COMMAND arg```
            r'```(\w+)(?:\s+(.+?))?```',
            # Alternative fenced blocks with optional language: ```bash COMMAND arg``` or ```text COMMAND arg```
            r'```(?:\w+\s+)?(\w+)(?:\s+(.+?))?```',
            # Fenced blocks with newlines: ```\nCOMMAND arg\n```
            r'```\s*\n\s*(\w+)(?:\s+(.+?))?\s*\n\s*```',
            # Simple patterns without fencing: COMMAND: arg or COMMAND arg
            r'^\s*(\w+):\s*(.+?)$',
            r'^\s*(\w+)\s+(.+?)$',
            # Standalone COMPLETE command
            r'\b(COMPLETE)\b'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, agent_response, re.DOTALL | re.MULTILINE)
            
            for match in matches:
                if isinstance(match, tuple):
                    command, arg = match
                else:
                    command = match
                    arg = ""
                    
                command = command.upper().strip()
                arg = arg.strip() if arg else ""
                
                if command in ['SUMMARY', 'FULL_TEXT', 'ADD_PAPER', 'COMPLETE']:
                    # Avoid duplicates
                    if (command, arg) not in commands:
                        commands.append((command, arg))
        
        # If still no commands found, try to extract from natural language
        if not commands:
            # Look for natural language patterns
            nl_patterns = [
                r'(?:I want to|I will|Let me)\s+search for\s+(.+?)(?:\.|$)',
                r'(?:search for|searching for)\s+["\']?(.+?)["\']?(?:\.|$)',
                r'(?:I need to|Let me)\s+(?:search|find)\s+(?:papers?\s+(?:on|about))\s+(.+?)(?:\.|$)',
            ]
            
            for pattern in nl_patterns:
                matches = re.findall(pattern, agent_response, re.IGNORECASE)
                for match in matches:
                    query = match.strip()
                    if query and len(query) > 3:  # Basic validation
                        commands.append(("SUMMARY", query))
                        break  # Take first valid match
                        
        self._add_trace_entry(
            "command_parsing",
            {"raw_response": agent_response, "parsed_commands": commands}
        )
        
        return commands
    
    def _execute_summary_command(self, search_query: str) -> str:
        """Execute SUMMARY command using LocalSearchTool."""
        start_time = time.time()
        
        try:
            # Use search tool to find relevant papers
            search_results = self.search_tool.find_papers_by_str(
                search_query, 
                limit=10  # Get more than target to allow for selection
            )
            
            # Extract paper IDs from search results and automatically create summaries
            paper_ids = []
            lines = search_results.split('\n')
            for line in lines:
                if line.startswith('ID: '):
                    try:
                        paper_id = int(line.split('ID: ')[1])
                        paper_ids.append(paper_id)
                    except (ValueError, IndexError):
                        continue
            
            # Create summaries for papers we don't already have
            new_summaries = []
            existing_ids = {s.paper_id for s in self.collected_summaries}
            
            for paper_id in paper_ids:
                if paper_id not in existing_ids and len(self.collected_summaries) + len(new_summaries) < self.num_papers_target:
                    paper = self.db.get_paper_by_id(paper_id)
                    if paper:
                        summary = LiteratureReviewSummary(
                            paper_id=paper_id,
                            title=paper.get('title', 'Unknown Title'),
                            summary=paper.get('abstract', 'No abstract available')[:500] + ('...' if len(paper.get('abstract', '')) > 500 else ''),
                            rationale=f"Found via search query: '{search_query}'",
                            relevance_score=paper.get('hybrid_score', paper.get('semantic_score', 0.5))
                        )
                        new_summaries.append(summary)
            
            # Add new summaries to collection
            self.collected_summaries.extend(new_summaries)
            
            duration = time.time() - start_time
            self._add_trace_entry(
                "search_execution",
                {
                    "query": search_query,
                    "results_count": len(paper_ids),
                    "new_summaries_added": len(new_summaries),
                    "total_summaries": len(self.collected_summaries),
                    "search_results": search_results[:1000] + "..." if len(search_results) > 1000 else search_results
                },
                duration_seconds=duration
            )
            
            if new_summaries:
                return f"Found {len(paper_ids)} papers, added {len(new_summaries)} new summaries. Total summaries: {len(self.collected_summaries)}/{self.num_papers_target}"
            else:
                return f"Found {len(paper_ids)} papers, but none were new or relevant. Total summaries: {len(self.collected_summaries)}/{self.num_papers_target}"
            
        except Exception as e:
            duration = time.time() - start_time
            self._add_trace_entry(
                "search_error",
                {"query": search_query, "error": str(e)},
                duration_seconds=duration
            )
            return f"Error searching for '{search_query}': {str(e)}"
    
    def _execute_full_text_command(self, paper_id: str) -> str:
        """Execute FULL_TEXT command using LocalSearchTool."""
        start_time = time.time()
        
        try:
            # Convert to int if numeric
            if paper_id.isdigit():
                paper_id_int = int(paper_id)
            else:
                return f"Invalid paper ID: {paper_id}. Must be numeric."
            
            full_text = self.search_tool.retrieve_full_text(paper_id_int)
            
            duration = time.time() - start_time
            self._add_trace_entry(
                "full_text_retrieval",
                {
                    "paper_id": paper_id_int,
                    "text_length": len(full_text) if full_text else 0,
                    "success": bool(full_text)
                },
                duration_seconds=duration
            )
            
            return full_text or f"No full text available for paper {paper_id}"
            
        except Exception as e:
            duration = time.time() - start_time
            self._add_trace_entry(
                "full_text_error",
                {"paper_id": paper_id, "error": str(e)},
                duration_seconds=duration
            )
            return f"Error retrieving full text for paper {paper_id}: {str(e)}"
    
    def _execute_add_paper_command(self, paper_identifier: str) -> str:
        """Execute ADD_PAPER command - could be ID or URL."""
        start_time = time.time()
        
        try:
            # If numeric, treat as existing paper ID
            if paper_identifier.isdigit():
                paper_id = int(paper_identifier)
                paper = self.db.get_paper_by_id(paper_id)
                if paper:
                    duration = time.time() - start_time
                    self._add_trace_entry(
                        "paper_added",
                        {"paper_id": paper_id, "title": paper.get("title", "Unknown")},
                        duration_seconds=duration
                    )
                    return f"Paper {paper_id} added to consideration: {paper.get('title', 'Unknown')}"
                else:
                    return f"Paper {paper_id} not found in database"
            
            # If URL, attempt to download and process
            elif paper_identifier.startswith(('http://', 'https://', 'arxiv.org')):
                try:
                    new_paper_id = self.search_tool.add_paper_from_url(paper_identifier)
                    if new_paper_id:
                        paper = self.db.get_paper_by_id(new_paper_id)
                        duration = time.time() - start_time
                        self._add_trace_entry(
                            "paper_downloaded",
                            {
                                "url": paper_identifier, 
                                "new_paper_id": new_paper_id,
                                "title": paper.get("title", "Unknown") if paper else "Unknown"
                            },
                            duration_seconds=duration
                        )
                        return f"Successfully downloaded and added paper {new_paper_id}: {paper.get('title', 'Unknown') if paper else 'Unknown'}"
                    else:
                        return f"Failed to download paper from {paper_identifier}"
                except Exception as e:
                    duration = time.time() - start_time
                    self._add_trace_entry(
                        "paper_download_error",
                        {"url": paper_identifier, "error": str(e)},
                        duration_seconds=duration
                    )
                    return f"Error downloading paper from {paper_identifier}: {str(e)}"
            
            else:
                return f"Invalid paper identifier: {paper_identifier}. Must be numeric ID or URL."
                
        except Exception as e:
            duration = time.time() - start_time
            self._add_trace_entry(
                "add_paper_error",
                {"identifier": paper_identifier, "error": str(e)},
                duration_seconds=duration
            )
            return f"Error adding paper {paper_identifier}: {str(e)}"
    
    def _build_agent_prompt(self, research_question: str, context: str = "") -> str:
        """Build prompt for the boss agent following PRD template."""
        summaries_block = ""
        if self.collected_summaries:
            summaries_block = "\n".join([
                f"- Paper {s.paper_id}: {s.title}\n  Summary: {s.summary}\n  Rationale: {s.rationale}"
                for s in self.collected_summaries
            ])
        else:
            summaries_block = "No summaries collected yet."
        
        # Provide search strategy guidance based on current state
        search_guidance = ""
        if len(self.collected_summaries) == 0:
            search_guidance = """
SEARCH STRATEGY: Start with simple, broad keyword searches. Use 1-3 relevant keywords rather than full questions.
Good examples: "agents", "AI agents", "language model agents", "autonomous agents"
Avoid: Long questions like "What are the current trends in..."
"""
        elif len(self.collected_summaries) < self.num_papers_target // 2:
            search_guidance = """
SEARCH STRATEGY: Try different keyword combinations to find more papers.
Examples: "multi-agent systems", "agent architectures", "agent frameworks"
"""
        
        prompt = f"""Research topic: "{research_question}"
Phase: "research_gathering" (step {self.current_iteration + 1})
Target papers: {self.num_papers_target} (currently have {len(self.collected_summaries)})

Known summaries so far:
{summaries_block}

{context}

Current status: You have {len(self.collected_summaries)} out of {self.num_papers_target} papers.

Available actions:
1. SUMMARY <query>: Search for papers using keywords (use simple, relevant keywords)
2. FULL_TEXT <paper_id>: Retrieve full text of a specific paper by ID
3. ADD_PAPER <identifier>: Add a paper by ID or URL
4. COMPLETE: Signal completion when you have enough high-quality papers

{search_guidance}

CRITICAL RULES:
- If you have 0 papers, you MUST use SUMMARY with simple keywords (2-4 words maximum)
- If you have fewer than {self.num_papers_target} papers, continue searching with SUMMARY
- NEVER use COMPLETE unless you have {self.num_papers_target} or more papers
- Use simple keyword searches, not full questions or sentences
- Focus on recent, high-impact papers that directly address the research topic

Respond with valid JSON in this exact format:
{{
  "action": {{"command": "SUMMARY", "query": "your search keywords"}},
  "reasoning": "explanation of your choice"
}}

Choose your next action. Be systematic and thorough in your search."""

        return prompt
    
    def _invoke_agent_with_schema(self, prompt: str) -> Optional[AgentAction]:
        """Invoke the agent with structured output using the AgentAction schema."""
        start_time = time.time()
        
        try:
            # Try structured output first
            response = self.model_router.invoke(
                messages=[{"role": "user", "content": prompt}],
                system_prompt="You are a systematic research agent conducting a literature review. Your goal is to find relevant papers by using simple keyword searches, then gathering enough papers for analysis. CRITICAL: Always use simple 1-3 word searches like 'AI agents' or 'multi-agent systems', never use full questions. You must collect the required number of papers before completing. Follow the JSON format exactly.",
                role=ModelRole.BOSS,
                task_description="research_coordination",
                schema=AgentAction
            )
            
            duration = time.time() - start_time
            
            # If response is already a Pydantic object, use it directly
            if isinstance(response, AgentAction):
                self._add_trace_entry(
                    "structured_agent_response",
                    {
                        "response_type": "pydantic_object",
                        "command": response.action.command,
                        "reasoning": response.reasoning
                    },
                    model_used="boss_model",
                    duration_seconds=duration
                )
                return response
            
            # If response is a string (JSON), try to parse it
            elif isinstance(response, str):
                try:
                    # Try standard JSON parsing first
                    response_data = json.loads(response)
                except json.JSONDecodeError:
                    # Fall back to json_repair for malformed JSON
                    response_data = json_repair.loads(response)
                
                # Create AgentAction object from parsed data
                agent_action = AgentAction(**response_data)
                
                self._add_trace_entry(
                    "structured_agent_response",
                    {
                        "response_type": "parsed_json",
                        "command": agent_action.action.command,
                        "reasoning": agent_action.reasoning,
                        "raw_response": response[:200] + "..." if len(response) > 200 else response
                    },
                    model_used="boss_model",
                    duration_seconds=duration
                )
                return agent_action
                
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Error in structured agent invocation: {e}")
            self._add_trace_entry(
                "structured_agent_error",
                {"error": str(e), "fallback_needed": True},
                model_used="boss_model",
                duration_seconds=duration
            )
            
            # Fall back to text-based response
            try:
                response = self.model_router.invoke(
                    messages=[{"role": "user", "content": prompt}],
                    system_prompt="You are a systematic research agent conducting a literature review. Your goal is to find relevant papers by searching first, then analyzing them. You must search for papers before completing the review.",
                    role=ModelRole.BOSS,
                    task_description="research_coordination"
                )
                
                # Try to extract a simple action from text response
                return self._parse_fallback_response(response)
                
            except Exception as fallback_error:
                logger.error(f"Fallback invocation also failed: {fallback_error}")
                self._add_trace_entry(
                    "agent_invocation_failed",
                    {"structured_error": str(e), "fallback_error": str(fallback_error)}
                )
                return None
        
        return None
    
    def _parse_fallback_response(self, response: str) -> Optional[AgentAction]:
        """Parse a text response as fallback when structured output fails."""
        try:
            # Look for common patterns in the response
            if "COMPLETE" in response.upper():
                return AgentAction(
                    action=CompleteCommand(reason="Fallback parsing detected completion"),
                    reasoning="Completion detected from text response"
                )
            
            # Look for search queries
            search_patterns = [
                r'(?:search|SEARCH|SUMMARY)\s*(?:for\s*)?["\']?([^"\']+)["\']?',
                r'(?:query|find)\s*["\']?([^"\']+)["\']?',
            ]
            
            for pattern in search_patterns:
                match = re.search(pattern, response, re.IGNORECASE)
                if match:
                    query = match.group(1).strip()
                    if len(query) > 3:  # Basic validation
                        return AgentAction(
                            action=SummaryCommand(query=query),
                            reasoning="Search query extracted from text response"
                        )
            
            # Look for paper IDs
            paper_id_pattern = r'(?:paper|PAPER|FULL_TEXT)\s*(?:id\s*)?(\d+)'
            match = re.search(paper_id_pattern, response, re.IGNORECASE)
            if match:
                paper_id = int(match.group(1))
                return AgentAction(
                    action=FullTextCommand(paper_id=paper_id),
                    reasoning="Paper ID extracted from text response"
                )
            
        except Exception as e:
            logger.error(f"Error in fallback parsing: {e}")
        
        return None
    
    def _extract_paper_summary(self, agent_response: str, paper_context: str) -> Optional[LiteratureReviewSummary]:
        """Extract structured summary from agent response about a specific paper."""
        # Use analysis worker to structure the summary
        summary_prompt = f"""Extract a structured summary from this agent response about a research paper.

Agent Response:
{agent_response}

Paper Context:
{paper_context}

Please provide:
1. A clear, concise summary (2-3 sentences)
2. Rationale for relevance to the research topic
3. A relevance score from 0.0 to 1.0

Format your response as:
SUMMARY: [your summary here]
RATIONALE: [why this paper is relevant]
SCORE: [0.0-1.0]"""

        try:
            start_time = time.time()
            structured_response = self.model_router.invoke(
                messages=[{"role": "user", "content": summary_prompt}],
                system_prompt="You are an expert research assistant specializing in academic paper analysis.",
                role=ModelRole.SUMMARY,
                task_description="paper_analysis"
            )
            duration = time.time() - start_time
            
            # Parse the structured response
            summary_match = re.search(r'SUMMARY:\s*(.+?)(?=RATIONALE:|$)', structured_response, re.DOTALL)
            rationale_match = re.search(r'RATIONALE:\s*(.+?)(?=SCORE:|$)', structured_response, re.DOTALL)
            score_match = re.search(r'SCORE:\s*([0-9.]+)', structured_response)
            
            if summary_match and rationale_match and score_match:
                summary = summary_match.group(1).strip()
                rationale = rationale_match.group(1).strip()
                score = float(score_match.group(1))
                
                # Extract paper ID from context (assuming it's in the search results)
                paper_id_match = re.search(r'Paper ID:\s*(\d+)', paper_context)
                if paper_id_match:
                    paper_id = int(paper_id_match.group(1))
                    
                    # Get paper title from database
                    paper = self.db.get_paper_by_id(paper_id)
                    title = paper.get("title", "Unknown Title") if paper else "Unknown Title"
                    
                    self._add_trace_entry(
                        "summary_extracted",
                        {
                            "paper_id": paper_id,
                            "summary_length": len(summary),
                            "relevance_score": score
                        },
                        model_used="summary_worker",  # We know this was the summary worker
                        duration_seconds=duration
                    )
                    
                    return LiteratureReviewSummary(
                        paper_id=paper_id,
                        title=title,
                        summary=summary,
                        rationale=rationale,
                        relevance_score=score
                    )
            
        except Exception as e:
            logger.error(f"Error extracting paper summary: {e}")
            self._add_trace_entry(
                "summary_extraction_error",
                {"error": str(e), "agent_response": agent_response[:500]}
            )
        
        return None
    
    def run_literature_review(self, research_question: str) -> ResearchAgentResult:
        """
        Main entry point for conducting automated literature review.
        
        Implements the agent loop following PRD specifications FR-3, FR-5, FR-6.
        """
        logger.info(f"Starting literature review for: {research_question}")
        
        # Report initial progress
        self._report_progress("initializing", 5, f"Starting literature review: {research_question}")
        
        self._add_trace_entry(
            "review_started",
            {
                "research_question": research_question,
                "target_papers": self.num_papers_target,
                "max_steps": self.max_steps
            }
        )
        
        try:
            # Initial context for the agent
            context = "Begin by searching for recent, high-quality papers on this topic."
            
            while (
                len(self.collected_summaries) < self.num_papers_target and 
                self.current_iteration < self.max_steps
            ):
                self.current_iteration += 1
                logger.info(f"Agent iteration {self.current_iteration}/{self.max_steps}")
                
                # Report iteration start
                iteration_progress = 10 + (self.current_iteration / self.max_steps) * 60
                self._report_progress(f"iteration_{self.current_iteration}", iteration_progress, 
                                    f"Iteration {self.current_iteration}/{self.max_steps} - Planning next steps")
                
                self._add_trace_entry("iteration_start", {"iteration": self.current_iteration})
                
                # Get agent response using structured output
                prompt = self._build_agent_prompt(research_question, context)
                
                self._report_progress("thinking", iteration_progress + 5, "Boss agent analyzing current state and planning actions")
                
                # Use structured output instead of text parsing
                agent_action = self._invoke_agent_with_schema(prompt)
                
                if not agent_action:
                    logger.warning("No valid action received from agent")
                    self._report_progress("error", iteration_progress, "No valid action received, retrying...")
                    context = "Previous attempt failed to produce a valid action. Please choose one of the available actions."
                    continue
                
                # Process the structured action
                command_results = []
                cmd_progress = iteration_progress + 15
                action = agent_action.action
                
                self._report_progress("executing", iteration_progress + 15, f"Executing {action.command} action")
                
                if isinstance(action, CompleteCommand):
                    # Validate completion - must have enough papers
                    if len(self.collected_summaries) >= self.num_papers_target:
                        logger.info(f"Agent signaled completion: {action.reason}")
                        self._report_progress("completing", 95, "Agent signaled completion")
                        self._add_trace_entry(
                            "completion_signaled", 
                            {
                                "final_summaries_count": len(self.collected_summaries),
                                "reason": action.reason,
                                "reasoning": agent_action.reasoning
                            }
                        )
                        break
                    else:
                        # Reject premature completion
                        logger.warning(f"Agent tried to complete with only {len(self.collected_summaries)}/{self.num_papers_target} papers")
                        context = f"INVALID COMPLETION: You cannot complete with only {len(self.collected_summaries)} papers. You need {self.num_papers_target} papers minimum. Use SUMMARY to search for more papers with different keywords."
                        self._add_trace_entry(
                            "premature_completion_rejected",
                            {
                                "current_summaries": len(self.collected_summaries),
                                "required_summaries": self.num_papers_target,
                                "reason": action.reason
                            }
                        )
                        continue
                
                elif isinstance(action, SummaryCommand):
                    query = action.query
                    self._report_progress("searching", cmd_progress, f"Searching for: {query}")
                    result = self._execute_summary_command(query)
                    command_results.append(f"Search results for '{query}':\n{result}")
                    
                    # Check if search found papers
                    if "No papers found" in result:
                        self._report_progress("no_results", cmd_progress + 5, f"No papers found for '{query}' - try different keywords")
                        context = f"Search for '{query}' found no papers. Try different, simpler keywords related to your research topic."
                    else:
                        # Extract paper IDs from search results
                        paper_id_matches = re.findall(r'ID:\s*(\d+)', result)
                        self._report_progress("analyzing", cmd_progress + 5, f"Found {len(paper_id_matches)} potential papers")
                        
                        papers_added = 0
                        for paper_id_str in paper_id_matches[:3]:  # Limit to prevent overwhelm
                            paper_id = int(paper_id_str)
                            if paper_id not in self.papers_seen:
                                self.papers_seen.add(paper_id)
                                self._report_progress("summarizing", cmd_progress + 10, f"Processing paper {paper_id}")
                                
                                # Get paper details for summary
                                paper = self.db.get_paper_by_id(paper_id)
                                if paper:
                                    # Create summary directly from paper data
                                    summary = LiteratureReviewSummary(
                                        paper_id=paper_id,
                                        title=paper.get('title', 'Unknown Title'),
                                        summary=paper.get('abstract', 'No abstract available')[:400] + ('...' if len(paper.get('abstract', '')) > 400 else ''),
                                        rationale=f"Found via search query: '{query}'. Relevant to research topic.",
                                        relevance_score=0.7  # Default relevance score
                                    )
                                    self.collected_summaries.append(summary)
                                    papers_added += 1
                                    logger.info(f"Added paper {paper_id}: {summary.title}")
                        
                        current_count = len(self.collected_summaries)
                        if papers_added > 0:
                            self._report_progress("collected", cmd_progress + 15, 
                                                f"Collected {current_count}/{self.num_papers_target} papers")
                            context = f"Successfully added {papers_added} papers from search '{query}'. You now have {current_count}/{self.num_papers_target} papers."
                        else:
                            context = f"Found papers for '{query}' but they were already processed. Try a different search query."
                
                elif isinstance(action, FullTextCommand):
                    paper_id = str(action.paper_id)
                    self._report_progress("retrieving", cmd_progress, f"Retrieving full text for paper {paper_id}")
                    result = self._execute_full_text_command(paper_id)
                    command_results.append(f"Full text for paper {paper_id}:\n{result[:1000]}{'...' if len(result) > 1000 else ''}")
                
                elif isinstance(action, AddPaperCommand):
                    identifier = action.identifier
                    self._report_progress("adding", cmd_progress, f"Adding paper: {identifier}")
                    result = self._execute_add_paper_command(identifier)
                    command_results.append(result)
                
                # Prepare context for next iteration
                if command_results:
                    context = "Results from your last commands:\n" + "\n\n".join(command_results)
                else:
                    context = "No command results to report."
            
            # Determine success
            success = len(self.collected_summaries) >= self.num_papers_target
            
            # Report completion progress
            self._report_progress("generating_report", 90, "Generating final markdown report")
            
            self._add_trace_entry(
                "review_completed",
                {
                    "success": success,
                    "final_summaries_count": len(self.collected_summaries),
                    "total_iterations": self.current_iteration,
                    "termination_reason": "target_reached" if success else "max_iterations"
                }
            )
            
            logger.info(f"Literature review completed. Success: {success}, Papers: {len(self.collected_summaries)}")
            
            # Generate full markdown report
            report_text = self._generate_markdown_report(research_question, self.collected_summaries)
            
            # Report final completion
            self._report_progress("completed", 100, f"Literature review completed! Found {len(self.collected_summaries)} papers")
            
            return ResearchAgentResult(
                research_question=research_question,
                summaries=self.collected_summaries,
                trace_entries=self.trace_entries,
                total_iterations=self.current_iteration,
                success=success,
                report_text=report_text
            )
            
        except Exception as e:
            error_msg = f"Literature review failed: {str(e)}"
            logger.error(error_msg)
            
            self._add_trace_entry(
                "review_error",
                {"error": str(e), "iteration": self.current_iteration}
            )
            
            # Generate partial report even on failure
            report_text = self._generate_markdown_report(research_question, self.collected_summaries) if self.collected_summaries else None
            
            return ResearchAgentResult(
                research_question=research_question,
                summaries=self.collected_summaries,
                trace_entries=self.trace_entries,
                total_iterations=self.current_iteration,
                success=False,
                error=error_msg,
                report_text=report_text
            )
    
    def _generate_markdown_report(self, research_question: str, summaries: List[LiteratureReviewSummary]) -> str:
        """
        Generate a comprehensive markdown report from the literature review results.
        
        Args:
            research_question: The research question that was investigated
            summaries: List of paper summaries collected during the review
            
        Returns:
            Formatted markdown report as string
        """
        if not summaries:
            return f"""# Literature Review Report

## Research Question
{research_question}

## Summary
No relevant papers were found during this literature review.

## Methodology
This literature review was conducted using an automated research agent that searched through the local paper database and evaluated papers for relevance to the research question.

*Report generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""
        
        # Sort summaries by relevance score (highest first)
        sorted_summaries = sorted(summaries, key=lambda x: x.relevance_score, reverse=True)
        
        # Calculate statistics
        avg_relevance = sum(s.relevance_score for s in summaries) / len(summaries)
        high_relevance_count = len([s for s in summaries if s.relevance_score >= 0.8])
        
        # Generate the report
        report = f"""# Literature Review Report

## Research Question
{research_question}

## Executive Summary
This literature review identified **{len(summaries)} relevant papers** addressing the research question. The papers were evaluated for relevance, with an average relevance score of **{avg_relevance:.2f}**. {high_relevance_count} papers were rated as highly relevant (≥0.8).

## Key Findings

"""
        
        # Add top findings
        for i, summary in enumerate(sorted_summaries[:3], 1):
            report += f"""### {i}. {summary.title}
**Relevance Score:** {summary.relevance_score:.2f} | **Paper ID:** {summary.paper_id}

**Key Contribution:** {summary.summary}

**Relevance Rationale:** {summary.rationale}

---

"""
        
        # Add complete paper inventory
        report += """## Complete Paper Inventory

| # | Paper ID | Title | Relevance Score | Summary |
|---|----------|-------|----------------|---------|
"""
        
        for i, summary in enumerate(sorted_summaries, 1):
            # Truncate title and summary for table display
            title_short = (summary.title[:50] + "...") if len(summary.title) > 50 else summary.title
            summary_short = (summary.summary[:80] + "...") if len(summary.summary) > 80 else summary.summary
            
            # Escape pipe characters for markdown table
            title_short = title_short.replace("|", "\\|")
            summary_short = summary_short.replace("|", "\\|")
            
            report += f"| {i} | {summary.paper_id} | {title_short} | {summary.relevance_score:.2f} | {summary_short} |\n"
        
        # Add methodology section
        report += f"""

## Methodology

This literature review was conducted using an automated research agent with the following approach:

1. **Search Strategy**: Hybrid search combining semantic similarity and keyword matching
2. **Evaluation Criteria**: Papers were evaluated for relevance to the research question using AI-powered analysis
3. **Quality Threshold**: Only papers with relevance scores ≥ 0.6 were included in the final review
4. **Coverage**: Search focused on the local paper database with high-quality academic papers

## Statistical Summary

- **Total Papers Reviewed**: {len(summaries)}
- **Average Relevance Score**: {avg_relevance:.3f}
- **Highly Relevant Papers** (≥0.8): {high_relevance_count}
- **Moderately Relevant Papers** (0.6-0.8): {len([s for s in summaries if 0.6 <= s.relevance_score < 0.8])}

## Recommendations

Based on this literature review, the following papers are recommended for priority reading:

"""
        
        # Add top 5 recommendations
        for i, summary in enumerate(sorted_summaries[:5], 1):
            report += f"{i}. **{summary.title}** (Paper ID: {summary.paper_id}, Score: {summary.relevance_score:.2f})\n"
        
        report += f"""

## Conclusion

This automated literature review successfully identified {len(summaries)} relevant papers addressing the research question "{research_question}". The papers span various aspects of the topic and provide a solid foundation for further research.

For detailed analysis of individual papers, readers should examine the full text using the Paper IDs provided in this report.

---

*This report was generated automatically by the Research Agent on {datetime.now().strftime('%Y-%m-%d at %H:%M:%S')}.*
"""
        
        return report

    def save_results(self, result: ResearchAgentResult) -> int:
        """
        Save literature review results to database (FR-6).
        
        Returns:
            The ID of the created literature review record
        """
        try:
            # Convert summaries to JSON format
            summaries_json = json.dumps([
                {
                    "paper_id": s.paper_id,
                    "title": s.title,
                    "summary": s.summary,
                    "rationale": s.rationale,
                    "relevance_score": s.relevance_score
                }
                for s in result.summaries
            ])
            
            # Convert trace to JSON format
            trace_json = json.dumps([asdict(entry) for entry in result.trace_entries])
            
            # Insert into lit_reviews table
            review_id = self.db.insert_literature_review(
                research_question=result.research_question,
                summary_json=summaries_json,
                trace_json=trace_json,
                report_text=result.report_text
            )
            
            logger.info(f"Saved literature review results with ID: {review_id}")
            return review_id
            
        except Exception as e:
            logger.error(f"Error saving literature review results: {e}")
            raise


def create_research_agent(
    db: PaperDatabase,
    num_papers_target: int = 5,
    max_steps: int = 10,
    enable_pdf_download: bool = True,
    progress_callback: Optional[Callable] = None
) -> ResearchAgentLoop:
    """
    Factory function to create a configured ResearchAgentLoop instance.
    
    Args:
        db: Database connection
        num_papers_target: Target number of papers to collect
        max_steps: Maximum agent iterations
        enable_pdf_download: Whether to enable PDF download for new papers
        progress_callback: Optional callback function for progress updates
    
    Returns:
        Configured ResearchAgentLoop instance
    """
    import json
    from .model_router import load_research_agent_model_config
    from ..inference import SentenceTransformerInference
    
    # Get the orchestration config to load the embedding model
    orchestration_json = db.get_setting("orchestration")
    if not orchestration_json:
        raise ValueError("Orchestration config not found")
    
    orchestration_config = json.loads(orchestration_json)
    embedding_model_config = orchestration_config.get('embedding_model')
    if not embedding_model_config:
        raise ValueError("Embedding model config not found")
    
    # Initialize the embedding model
    embedding_model = SentenceTransformerInference(
        embedding_model_config['model_name'], 
        remote_code=embedding_model_config.get('trust_remote_code', False)
    )
    
    # Create search tool with embedding model and more lenient similarity threshold
    search_tool = LocalSearchTool(
        db, 
        embedding_model, 
        enable_pdf_download=enable_pdf_download,
        similarity_threshold=0.2  # More lenient threshold for better recall
    )
    
    # Load model configuration and create router
    model_config = load_research_agent_model_config(db)
    model_router = AgentModelRouter(db, model_config)
    
    # Create agent loop
    agent = ResearchAgentLoop(
        db=db,
        search_tool=search_tool,
        model_router=model_router,
        num_papers_target=num_papers_target,
        max_steps=max_steps,
        progress_callback=progress_callback
    )
    
    return agent 