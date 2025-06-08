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
    QueryRefinementState,
)
from .graph_prompts import (
    answer_instructions,
    get_current_date,
    query_writer_instructions,
    reflection_instructions,
    query_refinement_instructions,
)
from .graph_schemas import Reflection, SearchQueryList, QueryRefinement
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
        builder.add_node("query_refinement", self._query_refinement)
        builder.add_node("generate_query", self._generate_query)
        builder.add_node("local_research", self._local_research)
        builder.add_node("external_research", self._external_research)
        builder.add_node("sequential_external_research", self._sequential_external_research)
        builder.add_node("reflection", self._reflection)
        builder.add_node("finalize_answer", self._finalize_answer)
        
        # Set the entry point to query refinement
        builder.add_edge(START, "query_refinement")
        
        # Add routing from query refinement
        builder.add_conditional_edges(
            "query_refinement",
            self._route_after_refinement,
            {END: END, "generate_query": "generate_query"}
        )
        
        # Add conditional edges with enhanced routing
        builder.add_conditional_edges(
            "generate_query", 
            self._continue_to_local_research, 
            ["local_research"]
        )
        
        # After local research, reflect on findings
        builder.add_edge("local_research", "reflection")
        builder.add_edge("external_research", "reflection")
        
        # After sequential external research, reflect on findings
        builder.add_edge("sequential_external_research", "reflection")
        
        # Evaluate if we need more research or can finalize
        builder.add_conditional_edges(
            "reflection", 
            self._evaluate_research, 
            ["sequential_external_research", "finalize_answer"]
        )
        
        # End after finalizing
        builder.add_edge("finalize_answer", END)
        
        return builder.compile(name="enhanced-research-agent")
    
    def _query_refinement(self, state: OverallState, config: RunnableConfig) -> QueryRefinementState:
        """Analyze the research question and determine if clarification is needed."""
        try:
            # Check if we've already asked for clarification by looking for AI clarification messages
            has_asked_clarification = False
            for message in state["messages"]:
                if (message.type == "ai" and 
                    "I'd like to better understand your research needs" in message.content):
                    has_asked_clarification = True
                    break
            
            # If we've already asked clarification and user has responded, proceed
            if has_asked_clarification and len(state["messages"]) >= 2:
                # User has responded to clarification, use the full conversation context
                research_question = get_research_topic(state["messages"])
                return {
                    "needs_clarification": False,
                    "clarifying_questions": [],
                    "refined_query": research_question,
                    "original_query": research_question
                }
            
            # For the initial query only, analyze if clarification is needed
            if not has_asked_clarification:
                # Get the initial research question from the first user message
                initial_question = ""
                for message in state["messages"]:
                    if message.type == "human":
                        initial_question = message.content
                        break
                
                # Get the model for query refinement
                llm = self.model_router.get_model("query_refinement")
                
                # Format the prompt
                current_date = get_current_date()
                formatted_prompt = query_refinement_instructions.format(
                    current_date=current_date,
                    research_question=initial_question
                )
                
                # Generate refinement analysis using structured output
                result = llm.invoke([], formatted_prompt, schema=QueryRefinement, node_name="query_refinement")
                
                logger.info(f"Query refinement analysis: needs_clarification={result.needs_clarification}")
                
                if result.needs_clarification:
                    # Add clarifying questions as an AI message for the user to respond to
                    questions_text = "\n".join([f"{i+1}. {q}" for i, q in enumerate(result.clarifying_questions)])
                    clarification_msg = f"""I'd like to better understand your research needs to provide more focused results. Could you help clarify:

{questions_text}

Please respond with any additional details that would help me conduct more targeted research for you."""
                    
                    # Add the clarification message to the conversation
                    state["messages"].append(AIMessage(content=clarification_msg))
                    
                    return {
                        "needs_clarification": True,
                        "clarifying_questions": result.clarifying_questions,
                        "refined_query": "",
                        "original_query": initial_question
                    }
                else:
                    # Query is clear, continue with the refined version
                    return {
                        "needs_clarification": False,
                        "clarifying_questions": [],
                        "refined_query": result.refined_query,
                        "original_query": initial_question
                    }
            
            # Fallback: proceed without refinement
            research_question = get_research_topic(state["messages"])
            return {
                "needs_clarification": False,
                "clarifying_questions": [],
                "refined_query": research_question,
                "original_query": research_question
            }
                
        except Exception as e:
            logger.error(f"Error in query refinement: {e}")
            # Fallback: proceed without refinement
            research_question = get_research_topic(state["messages"])
            return {
                "needs_clarification": False,
                "clarifying_questions": [],
                "refined_query": research_question,
                "original_query": research_question
            }
    
    def _route_after_refinement(self, state: QueryRefinementState) -> str:
        """Route based on whether clarification is needed."""
        if state.get("needs_clarification", False):
            # Needs clarification - this will cause the workflow to pause and wait for user input
            # The task manager will handle restarting the workflow when user responds
            return END
        else:
            # Proceed to query generation
            return "generate_query"
    
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
            
            # Get raw results first for better source extraction
            raw_papers = self.local_tool.search_local_only(
                state["search_query"],
                limit=configurable.local_search_limit
            )
            
            # Generate formatted result for LLM consumption
            result = self.local_tool.find_papers_by_str(
                state["search_query"], 
                limit=configurable.local_search_limit
            )
            
            # Enhanced source tracking with complete metadata and automatic full text processing
            sources_gathered = []
            for paper in raw_papers:
                # Create short URL for citation tracking
                paper_url = paper.get('url', '') or f"paper_id_{paper.get('id', 'unknown')}"
                short_url = self._generate_short_url(paper_url)
                
                # Attempt to get full text if enabled and not already available
                paper_full_text = paper.get('text', '')
                full_text_attempted = False
                
                if (configurable.enable_pdf_download and 
                    not paper_full_text and 
                    paper.get('url') and 
                    paper.get('id')):
                    
                    try:
                        logger.info(f"Attempting full text retrieval for paper {paper['id']}: {paper.get('title', 'Unknown')[:50]}...")
                        full_text_result = self.local_tool.retrieve_full_text(str(paper['id']))
                        full_text_attempted = True
                        
                        # Check if we successfully got full text
                        if "FULL TEXT RETRIEVED" in full_text_result:
                            # Re-fetch the paper to get updated text
                            updated_paper = self.db.get_paper_by_id(paper['id'])
                            if updated_paper and updated_paper.get('text'):
                                paper_full_text = updated_paper['text']
                                logger.info(f"Successfully retrieved full text for paper {paper['id']} ({len(paper_full_text)} chars)")
                        else:
                            logger.warning(f"Full text retrieval failed for paper {paper['id']}")
                    except Exception as e:
                        logger.error(f"Error during full text retrieval for paper {paper['id']}: {e}")
                
                # Store comprehensive source metadata
                source_entry = {
                    "short_url": short_url,
                    "value": paper_url,
                    "title": paper.get('title', 'Unknown Title').strip(),
                    "source_type": "local",
                    "paper_id": paper.get('id'),
                    "authors": paper.get('authors', []),
                    "year": paper.get('year'),
                    "abstract": paper.get('abstract', ''),
                    "has_full_text": bool(paper_full_text),
                    "full_text_length": len(paper_full_text) if paper_full_text else 0,
                    "full_text_attempted": full_text_attempted,
                    "relevance_score": paper.get('hybrid_score', 0)
                }
                sources_gathered.append(source_entry)
                
                # Replace URLs in result text with short URLs for cleaner presentation
                if paper_url and paper_url in result:
                    result = result.replace(paper_url, short_url)
            
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
            
            # Get raw results first for better source extraction
            raw_papers = self.external_tool.search_and_rank(
                state["search_query"],
                limit=configurable.external_search_limit
            )
            
            # Generate formatted result for LLM consumption
            result = self.external_tool.find_papers_by_str(
                state["search_query"], 
                limit=configurable.external_search_limit
            )
            
            # Enhanced source tracking with complete metadata
            sources_gathered = []
            for paper in raw_papers:
                # Prioritize Semantic Scholar URL, fallback to PDF URL
                paper_url = paper.get('url', '') or paper.get('pdf_url', '')
                if not paper_url:
                    continue  # Skip papers without accessible URLs
                
                # Create short URL for citation tracking
                short_url = self._generate_short_url(paper_url)
                
                # Clean up authors for display
                authors = paper.get('authors_str', '') or ', '.join([
                    author.get('name', '') for author in paper.get('authors', [])
                    if isinstance(author, dict) and author.get('name')
                ][:3])  # Limit to first 3 authors
                
                # Store comprehensive source metadata
                source_entry = {
                    "short_url": short_url,
                    "value": paper_url,
                    "title": paper.get('title', 'Unknown Title').strip(),
                    "source_type": "external",
                    "authors": authors,
                    "year": paper.get('year'),
                    "abstract": paper.get('abstract', ''),
                    "venue": paper.get('venue'),
                    "citation_count": paper.get('citationCount'),
                    "is_open_access": paper.get('isOpenAccess', False),
                    "pdf_url": paper.get('pdf_url'),
                    "external_ranking_score": paper.get('external_ranking_score', 0)
                }
                sources_gathered.append(source_entry)
                
                # Replace URLs in result text with short URLs for cleaner presentation
                if paper_url in result:
                    result = result.replace(paper_url, short_url)
                if paper.get('pdf_url') and paper['pdf_url'] in result:
                    result = result.replace(paper['pdf_url'], short_url)
            
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
                # Route to sequential external research instead of parallel
                return "sequential_external_research"
            else:
                logger.info("Research deemed sufficient, finalizing answer")
                return "finalize_answer"
                
        except Exception as e:
            logger.error(f"Error in research evaluation: {e}")
            return "finalize_answer"
    
    def _sequential_external_research(self, state: OverallState, config: RunnableConfig) -> OverallState:
        """Perform sequential external searches to avoid overwhelming APIs."""
        try:
            configurable = AgentConfiguration.from_runnable_config(config)
            
            # Get follow-up queries from reflection state
            follow_up_queries = state.get("follow_up_queries", [])
            logger.info(f"DEBUG: Sequential external research received state keys: {list(state.keys())}")
            logger.info(f"DEBUG: Follow-up queries found: {follow_up_queries}")
            
            if not follow_up_queries:
                logger.warning("No follow-up queries found for sequential external research")
                # Check if we have original queries to fall back to for external search
                search_queries = state.get("search_query", [])
                if search_queries:
                    logger.info(f"DEBUG: Using original search queries for external search: {search_queries}")
                    follow_up_queries = search_queries
                else:
                    logger.warning("No search queries available at all")
                    return state
            
            logger.info(f"Starting sequential external research for {len(follow_up_queries)} queries")
            
            # Collect all results from sequential searches
            all_sources_gathered = []
            all_search_results = []
            all_search_queries = []
            
            # Process each query sequentially with delay
            for idx, query in enumerate(follow_up_queries):
                logger.info(f"External search {idx + 1}/{len(follow_up_queries)} for query: {query}")
                
                # Add a configurable delay between requests to be respectful to APIs
                if idx > 0:
                    import time
                    time.sleep(configurable.external_search_delay)
                
                try:
                    # Get raw results first for better source extraction
                    raw_papers = self.external_tool.search_and_rank(
                        query,
                        limit=configurable.external_search_limit
                    )
                    
                    # Generate formatted result for LLM consumption
                    result = self.external_tool.find_papers_by_str(
                        query, 
                        limit=configurable.external_search_limit
                    )
                    
                    # Enhanced source tracking with complete metadata
                    sources_gathered = []
                    for paper in raw_papers:
                        # Prioritize Semantic Scholar URL, fallback to PDF URL
                        paper_url = paper.get('url', '') or paper.get('pdf_url', '')
                        if not paper_url:
                            continue  # Skip papers without accessible URLs
                        
                        # Create short URL for citation tracking
                        short_url = self._generate_short_url(paper_url)
                        
                        # Clean up authors for display
                        authors = paper.get('authors_str', '') or ', '.join([
                            author.get('name', '') for author in paper.get('authors', [])
                            if isinstance(author, dict) and author.get('name')
                        ][:3])  # Limit to first 3 authors
                        
                        # Attempt to get full text if PDF download is enabled and we have a PDF URL
                        has_full_text = False
                        full_text_attempted = False
                        pdf_url = paper.get('pdf_url', '')
                        
                        if (configurable.enable_pdf_download and 
                            pdf_url and 
                            pdf_url.endswith('.pdf')):
                            
                            try:
                                logger.info(f"Attempting full text retrieval for external paper: {paper.get('title', 'Unknown')[:50]}...")
                                full_text_result = self.external_tool.retrieve_full_text(pdf_url)
                                full_text_attempted = True
                                
                                # Check if we successfully got full text
                                if "EXTERNAL PDF CONTENT RETRIEVED" in full_text_result:
                                    has_full_text = True
                                    logger.info(f"Successfully retrieved external full text from {pdf_url}")
                                else:
                                    logger.warning(f"External full text retrieval failed for {pdf_url}")
                            except Exception as e:
                                logger.error(f"Error during external full text retrieval: {e}")
                        
                        # Store comprehensive source metadata
                        source_entry = {
                            "short_url": short_url,
                            "value": paper_url,
                            "title": paper.get('title', 'Unknown Title').strip(),
                            "source_type": "external",
                            "authors": authors,
                            "year": paper.get('year'),
                            "abstract": paper.get('abstract', ''),
                            "venue": paper.get('venue'),
                            "citation_count": paper.get('citationCount'),
                            "is_open_access": paper.get('isOpenAccess', False),
                            "pdf_url": pdf_url,
                            "has_full_text": has_full_text,
                            "full_text_attempted": full_text_attempted,
                            "external_ranking_score": paper.get('external_ranking_score', 0)
                        }
                        sources_gathered.append(source_entry)
                        
                        # Replace URLs in result text with short URLs for cleaner presentation
                        if paper_url in result:
                            result = result.replace(paper_url, short_url)
                        if paper.get('pdf_url') and paper['pdf_url'] in result:
                            result = result.replace(paper['pdf_url'], short_url)
                    
                    # Collect results
                    all_sources_gathered.extend(sources_gathered)
                    all_search_results.append(result)
                    all_search_queries.append(query)
                    
                    logger.info(f"External search {idx + 1} completed with {len(sources_gathered)} sources")
                    
                except Exception as e:
                    logger.error(f"Error in external search {idx + 1} for query '{query}': {e}")
                    all_search_results.append(f"External search failed for query: {query} - {str(e)}")
                    all_search_queries.append(query)
            
            logger.info(f"Sequential external research completed with {len(all_sources_gathered)} total sources")
            
            # Return updated state with all collected results
            return {
                **state,
                "sources_gathered": state.get("sources_gathered", []) + all_sources_gathered,
                "web_research_result": state.get("web_research_result", []) + all_search_results,
                "search_query": state.get("search_query", []) + all_search_queries,
            }
            
        except Exception as e:
            logger.error(f"Error in sequential external research: {e}")
            return {
                **state,
                "web_research_result": state.get("web_research_result", []) + [f"Sequential external search failed: {str(e)}"],
            }
    
    def _finalize_answer(self, state: OverallState, config: RunnableConfig):
        """Generate final comprehensive research summary with enhanced paper analysis."""
        try:
            configurable = AgentConfiguration.from_runnable_config(config)
            
            # Get research topic and sources
            research_topic = get_research_topic(state["messages"])
            research_insights = ""
            
            # Process gathered sources to extract insights with enhanced full text processing
            sources_gathered = state.get("sources_gathered", [])
            search_results = state.get("web_research_result", [])
            
            if search_results:
                # Get search queries for the combine function
                search_queries = state.get("search_query", [])
                combined_results = combine_search_results(search_results, search_queries)
                research_insights = generate_research_insights([combined_results])
            else:
                research_insights = ""
            
            # Check if we have access to full text papers - this is key for quality
            full_text_count = 0
            abstract_only_count = 0
            
            # Analyze what type of paper content we have access to
            for source in sources_gathered:
                if source.get("source_type") == "local":
                    # For local papers, check if full text is available
                    try:
                        paper_id = source.get("paper_id") or source.get("id")
                        if paper_id:
                            # Try to get full text - this will tell us if it's available
                            full_text_result = self.local_tool.retrieve_full_text(str(paper_id))
                            if "FULL TEXT RETRIEVED" in full_text_result:
                                full_text_count += 1
                                logger.info(f"Full text available for local paper {paper_id}: {source.get('title', 'Unknown')}")
                            else:
                                abstract_only_count += 1
                                logger.warning(f"Only abstract available for paper {paper_id}: {source.get('title', 'Unknown')}")
                    except Exception as e:
                        logger.error(f"Error checking full text availability: {e}")
                        abstract_only_count += 1
                else:
                    # For external papers, they typically only have abstracts unless explicitly downloaded
                    abstract_only_count += 1
            
            logger.info(f"Research content analysis: {full_text_count} full-text papers, {abstract_only_count} abstract-only papers")
            
            # Update the answer instructions with paper access information
            paper_access_note = ""
            if full_text_count > 0:
                paper_access_note = f"\n\nNote: This analysis includes {full_text_count} full-text papers and {abstract_only_count} abstract-only papers."
            elif abstract_only_count > 0:
                paper_access_note = f"\n\nNote: This analysis is based on {abstract_only_count} paper abstracts. For more detailed analysis, full-text access would be beneficial."
            
            # Enhanced answer instructions with paper access context
            enhanced_instructions = answer_instructions.format(
                current_date=get_current_date(),
                research_topic=research_topic,
                summaries=research_insights + paper_access_note
            )
            
            # Generate final answer
            llm = self.model_router.get_model("finalize_answer")
            
            # Convert LangChain messages to the format expected by the model router
            formatted_messages = []
            for msg in state["messages"]:
                if hasattr(msg, 'type') and hasattr(msg, 'content'):
                    # LangChain message format
                    role = "user" if msg.type == "human" else "assistant"
                    formatted_messages.append({"role": role, "content": msg.content})
                elif isinstance(msg, dict) and "role" in msg and "content" in msg:
                    # Already in correct format
                    formatted_messages.append(msg)
                else:
                    # Fallback - try to extract content
                    content = getattr(msg, 'content', str(msg))
                    formatted_messages.append({"role": "user", "content": content})
            
            response = llm.invoke(formatted_messages, enhanced_instructions, node_name="finalize_answer")
            
            # Convert response to proper LangChain AIMessage
            if hasattr(response, 'content'):
                content = response.content
            else:
                # Fallback for string responses
                content = str(response)
            
            # POST-PROCESS: Convert short URL placeholders to clickable markdown links
            enhanced_content = self._convert_short_urls_to_markdown_links(content, sources_gathered)
            
            ai_message = AIMessage(content=enhanced_content)
            
            final_state = {
                **state,
                "messages": [*state["messages"], ai_message],
                "sources_gathered": sources_gathered,
                "search_results": search_results,
                "full_text_papers": full_text_count,
                "abstract_only_papers": abstract_only_count
            }
            
            logger.info("Final research summary generated successfully")
            return final_state
            
        except Exception as e:
            logger.error(f"Error in finalize_answer: {e}")
            error_message = AIMessage(content=f"Error generating research summary: {str(e)}")
            return {
                **state,
                "messages": [*state["messages"], error_message],
                "sources_gathered": state.get("sources_gathered", [])
            }
    
    def _convert_short_urls_to_markdown_links(self, content: str, sources_gathered: List[Dict]) -> str:
        """
        Convert short URL placeholders to numbered hyperlinks with proper references section.
        
        Args:
            content: The research summary content with short URL placeholders
            sources_gathered: List of source dictionaries with metadata
            
        Returns:
            Enhanced content with numbered hyperlinks and full references section
        """
        import re
        
        # Create a mapping from short URLs to full source information
        source_mapping = {}
        reference_counter = 0
        
        for source in sources_gathered:
            short_url = source.get("short_url", "")
            if short_url:
                reference_counter += 1
                
                # Clean up title for display
                title = source.get("title", "").strip()
                if not title or title == "Unknown" or title == "Unknown Title":
                    title = f"Research Source {reference_counter}"
                
                # Truncate very long titles
                if len(title) > 80:
                    title = title[:77] + "..."
                
                url = source.get("value", "").strip()
                source_type = source.get("source_type", "unknown")
                
                # Get additional metadata for reference formatting
                authors = source.get("authors", "")
                year = source.get("year", "")
                venue = source.get("venue", "")
                
                source_mapping[short_url] = {
                    "number": reference_counter,
                    "title": title,
                    "url": url,
                    "type": source_type,
                    "authors": authors,
                    "year": year,
                    "venue": venue
                }
        
        # Find all short URL placeholders in the content
        short_url_pattern = r'\[source_\d+\]'
        short_urls = re.findall(short_url_pattern, content)
        
        enhanced_content = content
        
        # Replace each short URL with a numbered hyperlink
        for short_url in short_urls:
            if short_url in source_mapping:
                source_info = source_mapping[short_url]
                number = source_info["number"]
                url = source_info["url"]
                
                if url:
                    # Create numbered hyperlink
                    numbered_link = f"[{number}]({url})"
                    enhanced_content = enhanced_content.replace(short_url, numbered_link)
                else:
                    # If no URL available, just show the number in bold
                    enhanced_content = enhanced_content.replace(short_url, f"**[{number}]**")
        
        # Build or enhance the References section
        references_lines = ["\n## References\n"]
        
        # Sort sources by their reference number
        sorted_sources = sorted(source_mapping.values(), key=lambda x: x["number"])
        
        for source_info in sorted_sources:
            number = source_info["number"]
            title = source_info["title"]
            url = source_info["url"]
            source_type = source_info["type"]
            authors = source_info["authors"]
            year = source_info["year"]
            venue = source_info["venue"]
            
            # Build reference entry
            reference_parts = []
            
            # Add title (as hyperlink if URL available)
            if url:
                reference_parts.append(f"[{title}]({url})")
            else:
                reference_parts.append(f"**{title}**")
            
            # Add authors and year if available
            citation_parts = []
            if authors:
                # Clean up authors for citation format
                if isinstance(authors, list):
                    author_str = ", ".join(authors[:3])  # Limit to first 3 authors
                    if len(authors) > 3:
                        author_str += " et al."
                else:
                    author_str = str(authors)
                    if "," in author_str:
                        # Truncate to first 3 authors if comma-separated
                        author_list = [a.strip() for a in author_str.split(",")]
                        if len(author_list) > 3:
                            author_str = ", ".join(author_list[:3]) + " et al."
                
                citation_parts.append(author_str)
            
            if year:
                citation_parts.append(f"({year})")
            
            if citation_parts:
                reference_parts.append(" - " + " ".join(citation_parts))
            
            # Add venue and source type metadata
            metadata_parts = []
            if venue:
                venue_display = venue[:40] + "..." if len(venue) > 40 else venue
                metadata_parts.append(f"*{venue_display}*")
            
            if source_type != "unknown":
                metadata_parts.append(f"{source_type.title()} Source")
            
            if metadata_parts:
                reference_parts.append(f" | {' | '.join(metadata_parts)}")
            
            # Format the complete reference
            reference_line = f"{number}. {''.join(reference_parts)}"
            references_lines.append(reference_line)
        
        # Remove any existing References section and add our new one
        if "## References" in enhanced_content:
            # Find and remove existing references section
            lines = enhanced_content.split('\n')
            filtered_lines = []
            in_references = False
            
            for line in lines:
                if line.strip() == "## References":
                    in_references = True
                    continue
                elif in_references and line.startswith('##'):
                    # Found next section, stop filtering
                    in_references = False
                    filtered_lines.append(line)
                elif not in_references:
                    filtered_lines.append(line)
                # Skip lines that are in references section
            
            enhanced_content = '\n'.join(filtered_lines)
        
        # Add our new references section
        enhanced_content += '\n'.join(references_lines)
        
        logger.info(f"Enhanced content with {len(sorted_sources)} numbered reference links")
        return enhanced_content

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