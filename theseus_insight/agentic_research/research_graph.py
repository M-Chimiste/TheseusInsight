"""LangGraph workflow for the local-first research agent."""

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, AsyncGenerator

from langchain_core.messages import AIMessage, HumanMessage, BaseMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from .graph_configuration import AgentConfiguration
from .graph_state import (
    OverallState,
    QueryGenerationState, 
    ReflectionState,
    WebSearchState,
)
from .graph_prompts import (
    answer_instructions,
    get_current_date,
    query_writer_instructions,
    reflection_instructions,
)
from .graph_schemas import Reflection, SearchQueryList
from .graph_utils import (
    get_research_topic, 
    format_paper_results,
    extract_citations_from_summary,
    generate_research_insights,
    combine_search_results
)
from .unified_model_router import load_unified_router
from .local_search import LocalSearchTool
from .external_search import ExternalSearchTool
from ..data_model.data_handling import PaperDatabase
from ..inference.llm import SentenceTransformerInference


logger = logging.getLogger(__name__)


class ResearchAgent:
    """
    Enhanced LangGraph-based research agent that coordinates local and external search
    to provide comprehensive literature reviews with proper source tracking and citations.
    """
    
    def __init__(
        self,
        db: PaperDatabase,
        embedding_model: SentenceTransformerInference,
        config: AgentConfiguration = None
    ):
        self.db = db
        self.embedding_model = embedding_model
        self.config = config or AgentConfiguration()
        
        # Initialize search tools with enhanced capabilities
        self.local_tool = LocalSearchTool(
            db=db,
            embedding_model=embedding_model,
            semantic_weight=self.config.semantic_weight,
            keyword_weight=self.config.keyword_weight,
            similarity_threshold=self.config.similarity_threshold,
            enable_pdf_download=self.config.enable_pdf_download
        )
        
        self.external_tool = ExternalSearchTool(
            enable_pdf_download=self.config.enable_pdf_download
        )
        
        # Load unified model router
        self.model_router = load_unified_router(db)
        
        # Build the graph
        self.graph = self._build_graph()
        
        # Source tracking
        self._source_counter = 0
        self._url_mapping = {}
    
    def _generate_short_url(self, original_url: str) -> str:
        """Generate a short URL placeholder for citation tracking."""
        self._source_counter += 1
        short_url = f"[source_{self._source_counter}]"
        self._url_mapping[short_url] = original_url
        return short_url
    
    def _build_graph(self) -> StateGraph:
        """Build and compile the enhanced LangGraph workflow."""
        builder = StateGraph(OverallState, config_schema=AgentConfiguration)
        
        # Define the nodes
        builder.add_node("generate_query", self._generate_query)
        builder.add_node("local_research", self._local_research)
        builder.add_node("external_research", self._external_research)
        builder.add_node("reflection", self._reflection)
        builder.add_node("finalize_answer", self._finalize_answer)
        
        # Set the entry point
        builder.add_edge(START, "generate_query")
        
        # Add conditional edges with enhanced routing
        builder.add_conditional_edges(
            "generate_query", 
            self._continue_to_local_research, 
            ["local_research"]
        )
        
        # After local research, reflect on findings
        builder.add_edge("local_research", "reflection")
        builder.add_edge("external_research", "reflection")
        
        # Evaluate if we need more research or can finalize
        builder.add_conditional_edges(
            "reflection", 
            self._evaluate_research, 
            ["external_research", "finalize_answer"]
        )
        
        # End after finalizing
        builder.add_edge("finalize_answer", END)
        
        return builder.compile(name="enhanced-research-agent")
    
    def _generate_query(self, state: OverallState, config: RunnableConfig) -> QueryGenerationState:
        """Generate initial search queries based on the research question."""
        try:
            configurable = AgentConfiguration.from_runnable_config(config)
            
            # Set initial query count if not provided
            if state.get("initial_search_query_count") is None:
                state["initial_search_query_count"] = configurable.number_of_initial_queries
            
            # Get the model for query generation
            llm = self.model_router.get_model("generate_query")
            
            # Format the prompt with conversation context
            current_date = get_current_date()
            research_topic = get_research_topic(state["messages"])
            
            # Handle conversation continuity
            if len(state["messages"]) > 1:
                # Multi-turn conversation - include context
                conversation_context = "\n".join([
                    f"{'User' if msg.type == 'human' else 'Assistant'}: {msg.content}"
                    for msg in state["messages"][:-1]
                ])
                research_topic = f"Context: {conversation_context}\n\nCurrent question: {research_topic}"
            
            formatted_prompt = query_writer_instructions.format(
                current_date=current_date,
                research_topic=research_topic,
                number_queries=state["initial_search_query_count"],
            )
            
            # Generate queries using structured output
            result = llm.invoke([], formatted_prompt, schema=SearchQueryList, node_name="generate_query")
            logger.info(f"Generated {len(result.query)} search queries")
            return {"query_list": result.query}
            
        except Exception as e:
            logger.error(f"Error in query generation: {e}")
            # Fallback to simple query extraction
            research_topic = get_research_topic(state["messages"])
            return {"query_list": [research_topic]}
    
    def _continue_to_local_research(self, state: QueryGenerationState):
        """Spawn a local search node for each generated query with enhanced parallel execution."""
        queries = state["query_list"]
        logger.info(f"Starting local research for {len(queries)} queries")
        
        return [
            Send("local_research", {"search_query": query, "id": int(idx)})
            for idx, query in enumerate(queries)
        ]
    
    def _local_research(self, state: WebSearchState, config: RunnableConfig) -> OverallState:
        """Perform enhanced search over the local paper database with source tracking."""
        try:
            configurable = AgentConfiguration.from_runnable_config(config)
            
            logger.info(f"Local search for query: {state['search_query']}")
            
            # Search local database using the enhanced LocalSearchTool
            result = self.local_tool.find_papers_by_str(
                state["search_query"], 
                limit=configurable.local_search_limit
            )
            
            # Track sources with short URLs for citation management
            sources_gathered = []
            if "papers found" in result.lower():
                # Extract paper information and create source entries
                citations = extract_citations_from_summary(result)
                for citation in citations:
                    short_url = self._generate_short_url(citation.get("url", ""))
                    sources_gathered.append({
                        "short_url": short_url,
                        "value": citation.get("url", ""),
                        "title": citation.get("title", ""),
                        "source_type": "local"
                    })
                    # Replace long URLs in result with short URLs for cleaner presentation
                    if citation.get("url"):
                        result = result.replace(citation["url"], short_url)
            
            logger.info(f"Local search completed with {len(sources_gathered)} sources")
            
            return {
                "sources_gathered": sources_gathered,
                "search_query": [state["search_query"]],
                "web_research_result": [result],
            }
            
        except Exception as e:
            logger.error(f"Error in local research: {e}")
            return {
                "sources_gathered": [],
                "search_query": [state["search_query"]],
                "web_research_result": [f"Local search failed for query: {state['search_query']}"],
            }
    
    def _external_research(self, state: WebSearchState, config: RunnableConfig) -> OverallState:
        """Perform enhanced external search using Semantic Scholar with source tracking."""
        try:
            configurable = AgentConfiguration.from_runnable_config(config)
            
            logger.info(f"External search for query: {state['search_query']}")
            
            # Search using enhanced ExternalSearchTool
            result = self.external_tool.find_papers_by_str(
                state["search_query"], 
                limit=configurable.external_search_limit
            )
            
            # Track sources with short URLs for citation management
            sources_gathered = []
            if "papers found" in result.lower():
                # Extract paper information and create source entries
                citations = extract_citations_from_summary(result)
                for citation in citations:
                    short_url = self._generate_short_url(citation.get("url", ""))
                    sources_gathered.append({
                        "short_url": short_url,
                        "value": citation.get("url", ""),
                        "title": citation.get("title", ""),
                        "source_type": "external"
                    })
                    # Replace long URLs in result with short URLs for cleaner presentation
                    if citation.get("url"):
                        result = result.replace(citation["url"], short_url)
            
            logger.info(f"External search completed with {len(sources_gathered)} sources")
            
            return {
                "sources_gathered": sources_gathered,
                "search_query": [state["search_query"]],
                "web_research_result": [result],
            }
            
        except Exception as e:
            logger.error(f"Error in external research: {e}")
            return {
                "sources_gathered": [],
                "search_query": [state["search_query"]],
                "web_research_result": [f"External search failed for query: {state['search_query']}"],
            }
    
    def _reflection(self, state: OverallState, config: RunnableConfig) -> ReflectionState:
        """Enhanced reflection on research progress with deeper analysis."""
        try:
            configurable = AgentConfiguration.from_runnable_config(config)
            
            # Increment research loop count
            state["research_loop_count"] = state.get("research_loop_count", 0) + 1
            
            # Generate research insights from current findings
            insights = generate_research_insights(state["web_research_result"])
            
            # Combine and analyze search results
            combined_results = combine_search_results(
                state["web_research_result"],
                state["search_query"]
            )
            
            # Format the prompt with enhanced context
            current_date = get_current_date()
            formatted_prompt = reflection_instructions.format(
                current_date=current_date,
                research_topic=get_research_topic(state["messages"]),
                summaries=combined_results,
            )
            
            # Add research insights to prompt
            if insights:
                formatted_prompt += f"\n\nResearch insights so far:\n{insights}"
            
            # Get reflection from model
            llm = self.model_router.get_model("reflection")
            result = llm.invoke([], formatted_prompt, schema=Reflection, node_name="reflection")
            
            logger.info(f"Reflection completed - Research loop {state['research_loop_count']}, "
                       f"Sufficient: {result.is_sufficient}, "
                       f"Follow-up queries: {len(result.follow_up_queries)}")
            
            return {
                "is_sufficient": result.is_sufficient,
                "knowledge_gap": result.knowledge_gap,
                "follow_up_queries": result.follow_up_queries,
                "research_loop_count": state["research_loop_count"],
                "number_of_ran_queries": len(state["search_query"]),
            }
            
        except Exception as e:
            logger.error(f"Error in reflection: {e}")
            # Fallback to stopping research
            return {
                "is_sufficient": True,
                "knowledge_gap": "Reflection failed",
                "follow_up_queries": [],
                "research_loop_count": state.get("research_loop_count", 0) + 1,
                "number_of_ran_queries": len(state.get("search_query", [])),
            }
    
    def _evaluate_research(self, state: ReflectionState, config: RunnableConfig):
        """Enhanced research evaluation with smarter routing decisions."""
        try:
            configurable = AgentConfiguration.from_runnable_config(config)
            
            max_research_loops = (
                state.get("max_research_loops")
                if state.get("max_research_loops") is not None
                else configurable.max_research_loops
            )
            
            # Enhanced decision logic
            should_continue = (
                not state["is_sufficient"] and 
                state["research_loop_count"] < max_research_loops and
                len(state.get("follow_up_queries", [])) > 0
            )
            
            if should_continue:
                logger.info(f"Continuing research with {len(state['follow_up_queries'])} follow-up queries")
                return [
                    Send(
                        "external_research",
                        {
                            "search_query": follow_up_query,
                            "id": state["number_of_ran_queries"] + int(idx),
                        },
                    )
                    for idx, follow_up_query in enumerate(state["follow_up_queries"])
                ]
            else:
                logger.info("Research deemed sufficient, finalizing answer")
                return "finalize_answer"
                
        except Exception as e:
            logger.error(f"Error in research evaluation: {e}")
            return "finalize_answer"
    
    def _finalize_answer(self, state: OverallState, config: RunnableConfig):
        """Generate enhanced final research summary with proper citations and source management."""
        try:
            # Combine all research results
            combined_summaries = combine_search_results(
                state["web_research_result"],
                state["search_query"]
            )
            
            # Format the prompt
            current_date = get_current_date()
            formatted_prompt = answer_instructions.format(
                current_date=current_date,
                research_topic=get_research_topic(state["messages"]),
                summaries=combined_summaries,
            )
            
            # Generate final answer
            llm = self.model_router.get_model("finalize_answer")
            result = llm.invoke([], formatted_prompt, node_name="finalize_answer")
            
            # Enhanced source management - replace short URLs with original URLs
            unique_sources = []
            final_content = result.content
            
            for source in state.get("sources_gathered", []):
                if source["short_url"] in final_content:
                    # Replace short URL with original URL
                    final_content = final_content.replace(
                        source["short_url"], 
                        source["value"]
                    )
                    # Add to unique sources if not already present
                    if source not in unique_sources:
                        unique_sources.append(source)
            
            # Also check our internal URL mapping
            for short_url, original_url in self._url_mapping.items():
                if short_url in final_content:
                    final_content = final_content.replace(short_url, original_url)
            
            logger.info(f"Final answer generated with {len(unique_sources)} unique sources")
            
            return {
                "messages": [AIMessage(content=final_content)],
                "sources_gathered": unique_sources,
            }
            
        except Exception as e:
            logger.error(f"Error in finalizing answer: {e}")
            return {
                "messages": [AIMessage(content="I apologize, but there was an error generating the final research summary.")],
                "sources_gathered": [],
            }
    
    def reset_sources(self):
        """Reset source tracking for new conversations."""
        self._source_counter = 0
        self._url_mapping = {}
    
    async def arun(
        self, 
        research_question: str, 
        config: Dict[str, Any] = None,
        conversation_history: List[BaseMessage] = None
    ) -> Dict[str, Any]:
        """
        Run the enhanced research agent asynchronously with conversation continuity.
        
        Args:
            research_question: The research question to investigate
            config: Configuration options for the research process
            conversation_history: Previous conversation messages for context
            
        Returns:
            Dictionary containing the research results and sources
        """
        try:
            # Reset source tracking for new research session
            if not conversation_history:
                self.reset_sources()
            
            # Build messages list with conversation history
            messages = conversation_history or []
            messages.append(HumanMessage(content=research_question))
            
            # Set up initial state
            initial_state = {
                "messages": messages,
                **(config or {})
            }
            
            # Run the graph
            result = await self.graph.ainvoke(initial_state)
            
            logger.info("Research completed successfully")
            return result
            
        except Exception as e:
            logger.error(f"Error in async research run: {e}")
            return {
                "messages": [AIMessage(content=f"Research failed: {str(e)}")],
                "sources_gathered": [],
            }
    
    def run(
        self, 
        research_question: str, 
        config: Dict[str, Any] = None,
        conversation_history: List[BaseMessage] = None
    ) -> Dict[str, Any]:
        """
        Run the enhanced research agent synchronously with conversation continuity.
        
        Args:
            research_question: The research question to investigate
            config: Configuration options for the research process
            conversation_history: Previous conversation messages for context
            
        Returns:
            Dictionary containing the research results and sources
        """
        try:
            # Reset source tracking for new research session
            if not conversation_history:
                self.reset_sources()
            
            # Build messages list with conversation history
            messages = conversation_history or []
            messages.append(HumanMessage(content=research_question))
            
            # Set up initial state
            initial_state = {
                "messages": messages,
                **(config or {})
            }
            
            # Run the graph
            result = self.graph.invoke(initial_state)
            
            logger.info("Research completed successfully")
            return result
            
        except Exception as e:
            logger.error(f"Error in research run: {e}")
            return {
                "messages": [AIMessage(content=f"Research failed: {str(e)}")],
                "sources_gathered": [],
            }
    
    async def astream(
        self, 
        research_question: str, 
        config: Dict[str, Any] = None,
        conversation_history: List[BaseMessage] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream the research process with real-time updates.
        
        Args:
            research_question: The research question to investigate
            config: Configuration options for the research process
            conversation_history: Previous conversation messages for context
            
        Yields:
            Progress updates and partial results as they become available
        """
        try:
            # Reset source tracking for new research session
            if not conversation_history:
                self.reset_sources()
            
            # Build messages list with conversation history
            messages = conversation_history or []
            messages.append(HumanMessage(content=research_question))
            
            # Set up initial state
            initial_state = {
                "messages": messages,
                **(config or {})
            }
            
            # Stream the graph execution
            async for chunk in self.graph.astream(initial_state):
                yield chunk
                
        except Exception as e:
            logger.error(f"Error in streaming research: {e}")
            yield {
                "error": f"Research streaming failed: {str(e)}"
            }


def create_research_agent(
    db: PaperDatabase,
    embedding_model: SentenceTransformerInference = None,
    config: AgentConfiguration = None
) -> ResearchAgent:
    """
    Create an enhanced research agent instance with proper initialization.
    
    Args:
        db: Database instance for paper storage and retrieval
        embedding_model: Model for generating embeddings (optional)
        config: Configuration for the agent behavior
        
    Returns:
        Configured ResearchAgent instance
    """
    if embedding_model is None:
        embedding_model = SentenceTransformerInference()
    
    return ResearchAgent(
        db=db,
        embedding_model=embedding_model,
        config=config
    ) 