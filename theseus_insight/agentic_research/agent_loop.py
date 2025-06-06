import json
import re
import time
import logging
from typing import Dict, List, Optional, Tuple, Any, callable
from dataclasses import dataclass, asdict
from datetime import datetime

from ..data_model.data_handling import PaperDatabase
from .local_search import LocalSearchTool
from .model_router import AgentModelRouter, ModelRole
from ..constants import TASK_TYPE_RESEARCH_AGENT

logger = logging.getLogger(__name__)

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
        progress_callback: Optional[callable] = None
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
        
        Expected formats:
        ```SUMMARY <search_query>```
        ```FULL_TEXT <paper_id>```
        ```ADD_PAPER <paper_id_or_url>```
        ```COMPLETE```
        
        Returns:
            List of (command, argument) tuples
        """
        commands = []
        
        # Match fenced code blocks with commands
        pattern = r'```(\w+)(?:\s+(.+?))?```'
        matches = re.findall(pattern, agent_response, re.DOTALL | re.MULTILINE)
        
        for command, arg in matches:
            command = command.upper().strip()
            arg = arg.strip() if arg else ""
            
            if command in ['SUMMARY', 'FULL_TEXT', 'ADD_PAPER', 'COMPLETE']:
                commands.append((command, arg))
                
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
                top_k=10  # Get more than target to allow for selection
            )
            
            duration = time.time() - start_time
            self._add_trace_entry(
                "search_execution",
                {
                    "query": search_query,
                    "results_count": len(search_results.split('\n')) - 1,  # Rough count
                    "search_results": search_results
                },
                duration_seconds=duration
            )
            
            return search_results
            
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
        
        prompt = f"""System: You are a diligent PhD candidate conducting a literature review.

User:
Research topic: "{research_question}"
Phase: "research_gathering" (step {self.current_iteration + 1})
Target papers: {self.num_papers_target} (currently have {len(self.collected_summaries)})

Known summaries so far:
{summaries_block}

{context}

Instructions:
- If you need more papers, respond with ```SUMMARY <search query>``` to search for relevant papers.
- To inspect full text of a paper you've seen, respond with ```FULL_TEXT <paper_id>``` to get the complete text.
- To add a specific paper by ID or URL, respond with ```ADD_PAPER <paper_id_or_url>```.
- Once you have found {self.num_papers_target} high-quality papers and their summaries, respond with ```COMPLETE``` followed by a final analysis.
- Focus on recent, high-impact papers that directly address the research topic.

Remember: Be systematic and thorough. Quality over quantity."""

        return prompt
    
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
                
                # Get agent response using boss model
                prompt = self._build_agent_prompt(research_question, context)
                
                self._report_progress("thinking", iteration_progress + 5, "Boss agent analyzing current state and planning actions")
                
                start_time = time.time()
                agent_response = self.model_router.invoke(
                    messages=[{"role": "user", "content": prompt}],
                    system_prompt="You are a diligent PhD candidate conducting a literature review.",
                    role=ModelRole.BOSS,
                    task_description="research_coordination"
                )
                duration = time.time() - start_time
                
                self._add_trace_entry(
                    "agent_response",
                    {
                        "prompt_length": len(prompt),
                        "response_length": len(agent_response),
                        "response_preview": agent_response[:200] + "..." if len(agent_response) > 200 else agent_response
                    },
                    model_used="boss_model",  # We know this was the boss model
                    duration_seconds=duration
                )
                
                # Parse and execute commands
                self._report_progress("parsing", iteration_progress + 10, "Parsing agent commands")
                commands = self._parse_agent_commands(agent_response)
                
                if not commands:
                    logger.warning("No valid commands found in agent response")
                    self._report_progress("error", iteration_progress, "No valid commands found, retrying...")
                    context = "No valid commands detected. Please use the specified command format: ```COMMAND argument```"
                    continue
                
                # Process each command
                command_results = []
                self._report_progress("executing", iteration_progress + 15, f"Executing {len(commands)} command(s)")
                
                for i, (command, arg) in enumerate(commands):
                    cmd_progress = iteration_progress + 15 + (i / len(commands)) * 25
                    
                    if command == "COMPLETE":
                        logger.info("Agent signaled completion")
                        self._report_progress("completing", 95, "Agent signaled completion")
                        self._add_trace_entry("completion_signaled", {"final_summaries_count": len(self.collected_summaries)})
                        break
                    
                    elif command == "SUMMARY":
                        self._report_progress("searching", cmd_progress, f"Searching for: {arg}")
                        result = self._execute_summary_command(arg)
                        command_results.append(f"Search results for '{arg}':\n{result}")
                        
                        # Try to extract summaries from any papers mentioned
                        paper_id_matches = re.findall(r'Paper ID:\s*(\d+)', result)
                        self._report_progress("analyzing", cmd_progress + 5, f"Found {len(paper_id_matches)} potential papers")
                        
                        for paper_id_str in paper_id_matches[:3]:  # Limit to prevent overwhelm
                            paper_id = int(paper_id_str)
                            if paper_id not in self.papers_seen:
                                self.papers_seen.add(paper_id)
                                self._report_progress("summarizing", cmd_progress + 10, f"Extracting summary for paper {paper_id}")
                                summary = self._extract_paper_summary(agent_response, result)
                                if summary and summary.relevance_score >= 0.6:  # Quality threshold
                                    self.collected_summaries.append(summary)
                                    logger.info(f"Added summary for paper {paper_id}: {summary.title}")
                                    current_count = len(self.collected_summaries)
                                    self._report_progress("collected", cmd_progress + 15, 
                                                        f"Collected {current_count}/{self.num_papers_target} papers")
                    
                    elif command == "FULL_TEXT":
                        self._report_progress("retrieving", cmd_progress, f"Retrieving full text for paper {arg}")
                        result = self._execute_full_text_command(arg)
                        command_results.append(f"Full text for paper {arg}:\n{result[:1000]}{'...' if len(result) > 1000 else ''}")
                    
                    elif command == "ADD_PAPER":
                        self._report_progress("adding", cmd_progress, f"Adding paper: {arg}")
                        result = self._execute_add_paper_command(arg)
                        command_results.append(result)
                
                # Check if we found COMPLETE command
                if any(cmd[0] == "COMPLETE" for cmd in commands):
                    break
                
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
    progress_callback: Optional[callable] = None
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
    from .model_router import load_research_agent_model_config
    
    # Create search tool
    search_tool = LocalSearchTool(db, enable_pdf_download=enable_pdf_download)
    
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