"""LangGraph workflow for the local-first research agent."""

import logging
import tiktoken
from pathlib import Path
from typing import List, Dict, Any, Optional, AsyncGenerator

from langchain_core.messages import AIMessage, HumanMessage, BaseMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from .graph_configuration import AgentConfiguration
from .graph_state import (
    OverallState,
    QueryGenerationState, 
    ReflectionState,
    WebSearchState,
    QueryRefinementState,
    JudgeState,
    OutlineState,
)
from ..prompt.research_agent_prompts import (
    answer_instructions,
    get_current_date,
    query_writer_instructions,
    reflection_instructions,
    query_refinement_instructions,
    relevance_rubric,
    outline_instructions
)
from .graph_schemas import (Reflection,
                            SearchQueryList, 
                            QueryRefinement, 
                            RelevanceRubric,
                            ResearchOutline,
)
from .graph_utils import (
    get_research_topic, 
    format_paper_results,
    extract_citations_from_summary,
    generate_research_insights,
    combine_search_results,
)
from .unified_model_router import load_unified_router, UnifiedModelRouter
from .local_search import LocalSearchTool
from .external_search import ExternalSearchTool
from ..data_model.data_handling import PaperDatabase
from ..inference.llm import SentenceTransformerInference


logger = logging.getLogger(__name__)


def count_tokens(text: str, model_name: str = "gpt-3.5-turbo") -> int:
    """Counts the number of tokens in a text string using tiktoken.

    Args:
        text: The text to count tokens for.
        model_name: The name of the model to use for tokenization.
                    This helps in using the correct encoding.

    Returns:
        The number of tokens in the text.
    """
    if not text:
        return 0
    try:
        encoding = tiktoken.encoding_for_model(model_name)
    except KeyError:
        # If the model_name is not found, use a common default encoding
        encoding = tiktoken.get_encoding("cl100k_base")

    num_tokens = len(encoding.encode(text))
    return num_tokens


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
        builder.add_node("judge_all_papers", self._judge_all_papers)  # Combined judging for local + external
        builder.add_node("process_pdfs", self._process_pdfs)
        builder.add_node("compile_outline", self._compile_outline)
        builder.add_node("reflection", self._reflection)
        builder.add_node("follow_up_research", self._follow_up_research)  # Both local + external with new queries
        builder.add_node("finalize_answer", self._finalize_answer)
        
        # Set the entry point to query refinement
        builder.add_edge(START, "query_refinement")
        
        # Add routing from query refinement
        builder.add_conditional_edges(
            "query_refinement",
            self._route_after_refinement,
            {END: END, "generate_query": "generate_query"}
        )
        
        # After query generation, do BOTH local and external research in parallel
        builder.add_edge("generate_query", "local_research")
        builder.add_edge("generate_query", "external_research")
        
        # After both research types complete, judge ALL papers together
        builder.add_edge("local_research", "judge_all_papers")
        builder.add_edge("external_research", "judge_all_papers")
        
        # After judging, process PDFs for relevant papers only
        builder.add_edge("judge_all_papers", "process_pdfs")
        
        # After PDF processing, compile/update the research outline
        builder.add_edge("process_pdfs", "compile_outline")
        
        # After outline compilation, reflect on findings
        builder.add_edge("compile_outline", "reflection")
        
        # After follow-up research, judge new papers and reflect again
        builder.add_edge("follow_up_research", "judge_all_papers")
        
        # Evaluate if we need more research or can finalize
        builder.add_conditional_edges(
            "reflection", 
            self._evaluate_research, 
            ["follow_up_research", "finalize_answer"]
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
                formatted_prompt = query_refinement_instructions(
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
        # Ensure we ALWAYS return a valid state, no matter what happens
        def create_fallback_state(topic: str = "research query") -> QueryGenerationState:
            fallback_result = {"query_list": [{"query": topic, "rationale": "Fallback query due to error in query generation"}]}
            logger.warning(f"EMERGENCY FALLBACK ACTIVATED: Returning {fallback_result}")
            return fallback_result
        
        try:
            logger.debug("=== GENERATE QUERY START ===") # Changed from INFO and simplified
            logger.debug(f"Received state keys: {list(state.keys())}") # Changed from INFO
            
            # Robust configuration handling
            try:
                configurable = AgentConfiguration.from_runnable_config(config)
            except Exception as config_error:
                logger.error(f"Error loading configuration: {config_error}")
                configurable = AgentConfiguration()  # Use defaults
            
            # Set initial query count if not provided
            if state.get("initial_search_query_count") is None:
                state["initial_search_query_count"] = configurable.number_of_initial_queries
            
            logger.debug(f"Query count: {state['initial_search_query_count']}") # Changed from INFO
            
            # Robust research topic extraction
            research_topic_str = "research query" # Default for logging if extraction fails
            try:
                research_topic_str = get_research_topic(state["messages"])
                logger.debug(f"Research topic extracted: {research_topic_str}") # Changed from INFO
            except Exception as topic_error:
                logger.error(f"Error extracting research topic: {topic_error}")
                # Try to get first human message as fallback
                research_topic_str = "research query"
                for msg in state.get("messages", []):
                    if hasattr(msg, 'type') and msg.type == "human":
                        research_topic_str = msg.content
                        break
                logger.info(f"Using fallback research topic: {research_topic_str}") # Keep INFO for fallback
            
            # Get the model for query generation with error handling
            try:
                llm = self.model_router.get_model("generate_query")
                logger.debug(f"LLM model obtained: {type(llm)}") # Changed from INFO
            except Exception as model_error:
                logger.error(f"Error getting LLM model: {model_error}")
                # Return fallback immediately if we can't get a model
                return create_fallback_state(research_topic_str)
            
            # Handle conversation continuity
            enhanced_topic = research_topic_str
            try:
                if len(state.get("messages", [])) > 1:
                    # Multi-turn conversation - include context
                    conversation_context = "\n".join([
                        f"{'User' if getattr(msg, 'type', None) == 'human' else 'Assistant'}: {getattr(msg, 'content', str(msg))}"
                        for msg in state["messages"][:-1]
                    ])
                    enhanced_topic = f"Context: {conversation_context}\n\nCurrent question: {research_topic_str}"
            except Exception as context_error:
                logger.warning(f"Error building conversation context: {context_error}")
                # Continue with basic topic
            
            # Enhanced prompt for broader, more effective search queries
            try:
                current_date = get_current_date()
                formatted_prompt = query_writer_instructions(
                    current_date=current_date,
                    research_topic=enhanced_topic,
                    number_queries=state["initial_search_query_count"],
                )
                
                # Add guidance for effective academic search queries
                enhanced_prompt = formatted_prompt + """

IMPORTANT: Generate search queries that are effective for finding relevant papers in an academic database.
- Use terminology that researchers commonly use in their paper titles and abstracts
- Include synonyms and alternative phrasings for key concepts
- Balance specificity with breadth to capture relevant literature
- Consider different ways researchers might describe the same concepts
- Think about the actual language used in academic publications within this field
"""
                logger.debug(f"About to call LLM with prompt length: {len(enhanced_prompt)}") # Changed from INFO
            except Exception as prompt_error:
                logger.error(f"Error creating prompt: {prompt_error}")
                return create_fallback_state(research_topic_str)
            
            # Generate queries using structured output with comprehensive error handling
            try:
                result = llm.invoke([], enhanced_prompt, schema=SearchQueryList, node_name="generate_query")
                logger.debug(f"LLM call successful, result type: {type(result)}") # Changed from INFO
                logger.debug(f"Result has query attribute: {hasattr(result, 'query') if result else 'Result is None'}") # Changed from INFO
                
                if result and hasattr(result, 'query') and result.query:
                    raw_query_list = result.query
                    
                    # Validate and transform to correct format
                    if isinstance(raw_query_list, list) and len(raw_query_list) > 0:
                        # Transform from List[str] to List[Query] format
                        formatted_query_list = []
                        rationale = getattr(result, 'rationale', 'Generated search query for research')
                        
                        for i, query_str_item in enumerate(raw_query_list): # Iterate over items, which could be str or dict
                            actual_query_str = query_str_item
                            if isinstance(query_str_item, dict) and 'query' in query_str_item: # Check if item is dict with 'query' key
                                 actual_query_str = query_str_item['query']

                            if isinstance(actual_query_str, str) and actual_query_str.strip():
                                formatted_query_list.append({
                                    "query": actual_query_str.strip(),
                                    "rationale": f"{rationale} (Query {i+1})"
                                })
                                logger.debug(f"QUERY DEBUG: Query {i+1}: {actual_query_str.strip()}") # Changed from INFO
                        
                        if formatted_query_list:
                            logger.info(f"Generated {len(formatted_query_list)} search queries for topic: '{research_topic_str}'") # Adjusted INFO
                            return_state = {"query_list": formatted_query_list}
                            logger.debug(f"=== GENERATE QUERY END (SUCCESS) ===") # Changed from INFO and simplified
                            return return_state
                        else:
                            logger.error("No valid queries after formatting")
                            raise ValueError("No valid queries in list")
                    else:
                        logger.error(f"Query list is invalid: {raw_query_list}")
                        raise ValueError("Invalid query list format")
                else:
                    logger.error(f"Result does not have expected query attribute or is empty: {result}")
                    raise ValueError("LLM result missing query list")
                    
            except Exception as llm_error:
                logger.error(f"LLM invocation failed: {llm_error}")
                # Continue to fallback logic
                raise llm_error
            
        except Exception as e:
            logger.error(f"Error in query generation: {e}")
            logger.error(f"Exception type: {type(e)}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            
            # Robust fallback logic
            try:
                # Try to extract research topic again
                fallback_topic_str = get_research_topic(state.get("messages", [])) # Use research_topic_str
                if not fallback_topic_str or fallback_topic_str.strip() == "":
                    # Try getting first human message
                    for msg in state.get("messages", []):
                        if hasattr(msg, 'type') and msg.type == "human" and hasattr(msg, 'content'):
                            fallback_topic_str = msg.content
                            break
                    
                    if not fallback_topic_str:
                        fallback_topic_str = "research query"
                
                fallback_state = create_fallback_state(fallback_topic_str)
                logger.warning(f"=== QUERY GENERATION FAILED - Using fallback query: {fallback_topic_str} ===")
                logger.debug(f"=== GENERATE QUERY END (FALLBACK) ===") # Changed from INFO and simplified
                return fallback_state
                
            except Exception as fallback_error:
                logger.error(f"Even fallback failed: {fallback_error}")
                # Ultimate fallback - guaranteed to work
                ultimate_fallback = create_fallback_state("research query")
                logger.warning(f"=== QUERY GENERATION COMPLETELY FAILED - Using ultimate fallback ===")
                logger.debug(f"=== GENERATE QUERY END (ULTIMATE FALLBACK) ===") # Changed from INFO and simplified
                return ultimate_fallback
        
        # This should NEVER be reached, but adding as absolute final safety net
        logger.critical("CRITICAL ERROR: _generate_query reached end without returning - this should be impossible!")
        emergency_result = create_fallback_state("emergency fallback query")
        logger.critical(f"EMERGENCY RETURN: {emergency_result}")
        return emergency_result
    
    def _judge_all_papers(self, state: OverallState, config: RunnableConfig) -> JudgeState:
        """Judge the relevance of ALL papers (both local and external) before downloading PDFs."""
        try:
            configurable = AgentConfiguration.from_runnable_config(config)
            
            logger.debug(f"=== JUDGE ALL PAPERS START ===") # Changed
            logger.debug(f"Received state keys: {list(state.keys())}") # Changed
            
            sources_gathered = state.get("sources_gathered", [])
            # search_queries = state.get("search_query", []) # Not directly used here
            # web_results = state.get("web_research_result", []) # Not directly used here
            
            logger.debug(f"sources_gathered: type={type(sources_gathered)}, length={len(sources_gathered) if sources_gathered else 0}") # Changed
            
            if sources_gathered:
                logger.debug(f"Found {len(sources_gathered)} total sources to judge:") # Changed
                for i, source in enumerate(sources_gathered[:5]):
                    logger.debug(f"  Source {i+1}: {source.get('title', 'Unknown')[:50]}... (ID: {source.get('paper_id', 'none')}, Type: {source.get('source_type', 'unknown')})") # Changed
                if len(sources_gathered) > 5:
                    logger.debug(f"  ... and {len(sources_gathered) - 5} more sources") # Changed
            else:
                logger.warning("❌ NO SOURCES FOUND in 'sources_gathered' for judging!") # Adjusted
                logger.debug(f"=== JUDGE ALL PAPERS END (NO SOURCES) ===") # Changed
                return {
                    "judged_papers": [],
                    "rejected_papers": [],
                    "judged_sources": []
                }
            
            research_topic = get_research_topic(state["messages"])
            logger.info(f"Judging relevance of {len(sources_gathered)} papers for topic: '{research_topic}'") # Adjusted INFO
            logger.debug(f"=== JUDGE ALL PAPERS END (PRE-PROCESSING) ===") # Changed
            
            # Get the judge model
            llm = self.model_router.get_model("judge_papers")
            
            judged_papers = []
            rejected_papers = []
            
            for source in sources_gathered:
                try:
                    # Create paper context from available metadata
                    paper_context_parts = []
                    
                    if source.get("title"):
                        paper_context_parts.append(f"Title: {source['title']}")
                    
                    if source.get("abstract"):
                        paper_context_parts.append(f"Abstract: {source['abstract']}")
                    
                    if source.get("authors"):
                        authors_str = source["authors"] if isinstance(source["authors"], str) else ", ".join(source["authors"][:3])
                        paper_context_parts.append(f"Authors: {authors_str}")
                    
                    if source.get("year"):
                        paper_context_parts.append(f"Year: {source['year']}")
                    
                    if source.get("venue"):
                        paper_context_parts.append(f"Venue: {source['venue']}")
                    
                    # Add source type for context
                    source_type = source.get("source_type", "unknown")
                    paper_context_parts.append(f"Source: {source_type}")
                    
                    paper_context = "\n\n".join(paper_context_parts)
                    
                    if not paper_context.strip():
                        logger.debug(f"Skipping paper due to insufficient metadata: {source.get('title', 'Unknown')[:50]}...") # DEBUG
                        rejected_papers.append({
                            **source,
                            "judge_reason": "Insufficient metadata for relevance assessment"
                        })
                        continue
                    
                    # Format the relevance rubric prompt
                    formatted_prompt = relevance_rubric(
                        research_topic=research_topic,
                        paper_context=paper_context
                    )
                    
                    # Get relevance judgment using structured output
                    result = llm.invoke([], formatted_prompt, schema=RelevanceRubric, node_name="judge_all_papers")
                    
                    # Add judgment metadata to source
                    judged_source = {
                        **source,
                        "relevance_score": result.score,
                        "relevance_rationale": result.rationale,
                        "is_relevant": result.relevant
                    }
                    
                    # Simplified: Log per-paper details at DEBUG, summary at INFO
                    log_level_detail = logger.debug
                    if result.relevant:
                        judged_papers.append(judged_source)
                        log_level_detail(f"RELEVANT {source_type.upper()} (score: {result.score}): {source.get('title', 'Unknown')[:50]}...")
                    else:
                        rejected_papers.append(judged_source)
                        log_level_detail(f"REJECTED {source_type.upper()} (score: {result.score}): {source.get('title', 'Unknown')[:50]}...")
                
                except Exception as e:
                    logger.error(f"Error judging paper relevance for '{source.get('title', 'Unknown')[:50]}...': {e}")
                    # Include paper anyway but mark the error
                    judged_papers.append({
                        **source,
                        "relevance_score": 5,  # Neutral score
                        "relevance_rationale": f"Judgment failed: {str(e)}",
                        "is_relevant": True  # Default to relevant if judgment fails
                    })
            
            # Log final counts by source type
            # judged_local = [p for p in judged_papers if p.get("source_type") == "local"] # Not strictly needed for summary
            # judged_external = [p for p in judged_papers if p.get("source_type") == "external"] # Not strictly needed for summary
            # rejected_local = [p for p in rejected_papers if p.get("source_type") == "local"] # Not strictly needed for summary
            # rejected_external = [p for p in rejected_papers if p.get("source_type") == "external"] # Not strictly needed for summary
            
            logger.info(f"Paper judging complete: {len(judged_papers)} relevant, {len(rejected_papers)} rejected from {len(sources_gathered)} sources.") # INFO summary
            
            return {
                "judged_papers": judged_papers, # This key might be redundant if judged_sources is the primary one used downstream
                "rejected_papers": rejected_papers,
                "judged_sources": judged_papers  # Update the overall state with relevant papers only
            }
            
        except Exception as e:
            logger.error(f"Error in paper judging: {e}")
            # Fallback: include all papers
            sources_gathered = state.get("sources_gathered", [])
            return {
                "judged_papers": sources_gathered,
                "rejected_papers": [],
                "judged_sources": sources_gathered
            }
    
    def _process_pdfs(self, state: OverallState, config: RunnableConfig) -> OverallState:
        """Process PDFs for judged relevant papers only with detailed progress updates."""
        try:
            configurable = AgentConfiguration.from_runnable_config(config)
            
            # Get the judged sources (only relevant papers)
            judged_sources = state.get("judged_sources", [])
            logger.info(f"Starting PDF processing for {len(judged_sources)} relevant papers")
            
            if not judged_sources:
                logger.warning("No judged sources available for PDF processing")
                return state
            
            # Check if PDF downloads are disabled globally
            if not configurable.enable_pdf_download:
                logger.info("📄 PDF downloads disabled in configuration - using abstracts only")
                return {**state, "judged_sources": judged_sources}
            
            # Count papers that need PDF processing
            papers_needing_pdfs = []
            for source in judged_sources:
                if (not source.get("has_full_text") and 
                    (source.get("paper_id") or source.get("pdf_url"))):
                    papers_needing_pdfs.append(source)
            
            if not papers_needing_pdfs:
                logger.info("📄 No papers require PDF processing - all already have full text or PDFs unavailable")
                return {**state, "judged_sources": judged_sources}
            
            logger.info(f"📄 Starting PDF downloads for {len(papers_needing_pdfs)} papers...")
            
            # Process PDFs for relevant papers only
            enhanced_sources = []
            download_count = 0
            success_count = 0
            log_level_detail = logger.debug if len(papers_needing_pdfs) > 5 else logger.info

            for i, source in enumerate(judged_sources): # Iterate original to preserve order and all papers
                enhanced_source = dict(source)
                if not source.get("has_full_text") and source in papers_needing_pdfs: # Only process if it needs and is in the list
                    paper_title = source.get('title', 'Unknown')[:50]
                    if source.get("paper_id") and source.get("source_type") == "local":
                        download_count += 1
                        log_level_detail(f"📥 Downloading PDF {download_count}/{len(papers_needing_pdfs)} (Local DB): {paper_title}...")
                        try:
                            # logger.debug(f"Processing PDF for relevant paper {source['paper_id']}: {paper_title}...") # Redundant with above
                            full_text_result = self.local_tool.retrieve_full_text(str(source['paper_id']))
                            enhanced_source["full_text_attempted"] = True
                            if "FULL TEXT RETRIEVED" in full_text_result:
                                updated_paper = self.db.get_paper_by_id(source['paper_id'])
                                if updated_paper and updated_paper.get('text'):
                                    enhanced_source["has_full_text"] = True
                                    enhanced_source["full_text_length"] = len(updated_paper['text'])
                                    success_count += 1
                                    log_level_detail(f"✅ PDF {download_count}/{len(papers_needing_pdfs)} downloaded: {paper_title} ({len(updated_paper['text'])} chars)")
                                else:
                                    logger.warning(f"❌ PDF download for {source['paper_id']} ({paper_title}) reported success but no text retrieved.")
                                    enhanced_source["pdf_download_failed"] = True
                            else:
                                logger.warning(f"❌ PDF download failed for {source['paper_id']} ({paper_title}) - using abstract only.")
                                enhanced_source["pdf_download_failed"] = True
                        except Exception as e:
                            logger.error(f"❌ Error during PDF processing for {source.get('paper_id')}: {e}")
                            enhanced_source["full_text_attempted"] = True
                            enhanced_source["pdf_download_failed"] = True
                    elif source.get("pdf_url") and source.get("source_type") == "external":
                        download_count += 1
                        pdf_url = source.get("pdf_url")
                        log_level_detail(f"📥 Downloading external PDF {download_count}/{len(papers_needing_pdfs)}: {paper_title} from {pdf_url}...")
                        try:
                            # This part is simplified as _download_and_process_pdf_from_url handles actual download and processing
                            # For now, we assume if it has a pdf_url, it will be attempted.
                            # The actual text processing and DB update happens in _finalize_answer or if _process_pdfs is enhanced to do it.
                            # For this node, we're mainly updating flags.
                            # To truly process here, we'd call a helper like self._download_and_process_pdf_from_url(pdf_url, enhanced_source, research_topic)
                            # and update enhanced_source based on its return.
                            log_level_detail(f"🔄 External PDF {paper_title} marked for potential processing. Abstract will be used if full text not processed later.")
                            enhanced_source["full_text_attempted"] = True # Signifies an attempt will be made if not already done
                            # enhanced_source["pdf_download_failed"] = True # Placeholder, actual status depends on later processing
                        except Exception as e:
                            logger.error(f"❌ Error marking external PDF for processing {pdf_url}: {e}")
                            enhanced_source["full_text_attempted"] = True
                            enhanced_source["pdf_download_failed"] = True
                            # Continue processing - this is not a fatal error
                
                enhanced_sources.append(enhanced_source)
            
            if download_count > 0:
                failed_count = download_count - success_count
                logger.info(f"📄 PDF processing attempt summary: {success_count}/{download_count} successful local DB retrievals, {failed_count} might require fallback to abstract or direct PDF processing if available.") # Adjusted INFO
            else:
                logger.info(f"📄 PDF processing: No new PDFs required processing in this step.") # Adjusted INFO
            
            # Update the state with enhanced sources
            return {
                **state,
                "judged_sources": enhanced_sources
            }
            
        except Exception as e:
            logger.error(f"Error in PDF processing node: {e}") # Node-specific error
            logger.warning("Continuing research, may use abstracts only due to PDF processing node error.") # Adjusted
            return state
    
    def _compile_outline(self, state: OverallState, config: RunnableConfig) -> OutlineState:
        """Compile and update the research outline based on current findings."""
        try:
            configurable = AgentConfiguration.from_runnable_config(config)
            
            # Get research topic and current sources
            research_topic = get_research_topic(state["messages"])
            judged_sources = state.get("judged_sources", [])
            existing_outline = state.get("current_outline", "")
            
            logger.info(f"Compiling research outline with {len(judged_sources)} sources for topic: '{research_topic}'") # Added topic
            
            # Get the outline model (fallback to reasoning model)
            llm = self.model_router.get_model("outline")
            
            # Create paper contexts for outline generation
            paper_contexts = []
            historical_contexts = []
            
            for source in judged_sources:
                # Build paper context
                context_parts = []
                if source.get("title"):
                    context_parts.append(f"Title: {source['title']}")
                if source.get("abstract"):
                    context_parts.append(f"Abstract: {source['abstract']}")
                if source.get("authors"):
                    authors_str = source["authors"] if isinstance(source["authors"], str) else ", ".join(source["authors"][:3])
                    context_parts.append(f"Authors: {authors_str}")
                if source.get("year"):
                    context_parts.append(f"Year: {source['year']}")
                if source.get("relevance_rationale"):
                    context_parts.append(f"Relevance: {source['relevance_rationale']}")
                
                paper_context = "\n".join(context_parts)
                if paper_context.strip():
                    paper_contexts.append(paper_context)
                    
                    # Also add to historical context if it's a significant paper
                    if source.get("relevance_score", 0) >= 8:
                        historical_contexts.append(f"{source.get('year', 'Unknown')} - {source.get('title', 'Unknown')}")
            
            # Combine paper contexts for outline generation
            combined_paper_context = "\n\n---\n\n".join(paper_contexts[:10])  # Limit to avoid token overflow
            historical_context = "; ".join(historical_contexts[:5])  # Key papers only
            
            if not combined_paper_context.strip():
                logger.warning("No sufficient paper context for outline generation")
                # Return minimal outline
                return {
                    "outline": f"# Research Outline: {research_topic}\n\nI. Introduction\nII. Current Findings\nIII. Conclusions",
                    "paper_contexts": [],
                    "current_outline": existing_outline  # Keep existing outline
                }
            
            # Format the outline instructions prompt
            formatted_prompt = outline_instructions(
                research_topic=research_topic,
                paper_context=combined_paper_context,
                historical_context=historical_context or "Limited historical context available",
                existing_outline=existing_outline
            )
            
            # Generate outline using structured output
            result = llm.invoke([], formatted_prompt, schema=ResearchOutline, node_name="compile_outline")
            
            logger.info(f"Research outline compiled successfully ({len(result.outline)} chars)")
            
            return {
                "outline": result.outline,
                "paper_contexts": paper_contexts,
                "current_outline": result.outline  # Update the state with new outline
            }
            
        except Exception as e:
            logger.error(f"Error in outline compilation: {e}")
            # Fallback: keep existing outline or create minimal one
            existing_outline = state.get("current_outline", "")
            if not existing_outline:
                research_topic = get_research_topic(state["messages"])
                existing_outline = f"# Research Outline: {research_topic}\n\nI. Introduction\nII. Literature Review\nIII. Methodology\nIV. Conclusions"
            
            return {
                "outline": existing_outline,
                "paper_contexts": [],
                "current_outline": existing_outline
            }
    

    
    def _local_research(self, state: OverallState, config: RunnableConfig) -> OverallState:
        """Perform enhanced sequential search over the local paper database with source tracking."""
        try:
            configurable = AgentConfiguration.from_runnable_config(config)
            
            # Get the list of queries to search
            query_list = state.get("query_list", [])
            logger.info(f"Starting local search for {len(query_list)} queries.") # INFO summary
            
            all_sources_gathered = []
            all_search_queries = []
            all_web_results = []
            
            # Process each query sequentially
            for i, query_item in enumerate(query_list): # Use query_item to avoid clash if query is a var
                # Extract query string if it's a dict, otherwise use as-is
                query_str = query_item.get("query", query_item) if isinstance(query_item, dict) else query_item
                logger.debug(f"📚 Local search {i+1}/{len(query_list)}: '{query_str}'") # DEBUG for per-query
                
                # Get raw results first for better source extraction
                raw_papers = self.local_tool.search_local_only(
                    query_str,
                    limit=configurable.local_search_limit
                )
                
                # Log when no results are found but continue with the workflow
                if not raw_papers:
                    logger.debug(f"❌ No local papers found for query: '{query_str}'") # DEBUG
                else:
                    logger.debug(f"✅ Found {len(raw_papers)} local papers for query: '{query_str}'") # DEBUG
                
                # Generate formatted result for LLM consumption
                result = self.local_tool.find_papers_by_str(
                    query_str, 
                    limit=configurable.local_search_limit
                )
                
                # Enhanced source tracking with complete metadata
                query_sources = []
                for paper in raw_papers:
                    # Create short URL for citation tracking
                    paper_url = paper.get('url', '') or f"paper_id_{paper.get('id', 'unknown')}"
                    short_url = self._generate_short_url(paper_url)
                    
                    # Do NOT attempt PDF processing here - save that for after judging
                    paper_full_text = paper.get('text', '')
                    
                    # Store comprehensive source metadata for judging (based on title/abstract only)
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
                        "full_text_attempted": False,  # No PDF processing at this stage
                        "relevance_score": paper.get('hybrid_score', 0)
                    }
                    query_sources.append(source_entry)
                    
                    # Replace URLs in result text with short URLs for cleaner presentation
                    if paper_url and paper_url in result:
                        result = result.replace(paper_url, short_url)
                
                # Add this query's results to the aggregated results
                all_sources_gathered.extend(query_sources)
                all_search_queries.append(query_str)
                all_web_results.append(result)
                
                logger.debug(f"📊 Local query {i+1} completed: {len(query_sources)} papers added") # DEBUG
            
            logger.info(f"Local search completed. Found {len(all_sources_gathered)} total papers.") # INFO summary
            
            # Debug logging for aggregated results
            if all_sources_gathered: # Check if there are any sources before trying to log them
                logger.debug(f"LOCAL SEARCH RESULT (first 5):") # DEBUG
                for i, source in enumerate(all_sources_gathered[:5]):  # Show first 5
                    logger.debug(f"  Source {i+1}: {source.get('title', 'Unknown')[:50]}... (ID: {source.get('paper_id', 'none')})") # DEBUG
                if len(all_sources_gathered) > 5:
                    logger.debug(f"LOCAL SEARCH RESULT: ... and {len(all_sources_gathered) - 5} more sources") # DEBUG
            
            return_state = {
                "sources_gathered": all_sources_gathered,
                "search_query": all_search_queries, # Should this be appended or replaced? Assuming append for now.
                "web_research_result": all_web_results, # Same as above.
            }
            
            logger.debug(f"Local research returning state with {len(all_sources_gathered)} sources_gathered") # DEBUG
            
            return return_state
            
        except Exception as e:
            logger.error(f"Error in local research: {e}") # Changed from sequential
            return {
                "sources_gathered": [],
                "search_query": [],
                "web_research_result": [f"Sequential local search failed: {str(e)}"],
            }
    
    def _external_research(self, state: OverallState, config: RunnableConfig) -> OverallState:
        """Perform enhanced external search using ArXiv with source tracking."""
        try:
            configurable = AgentConfiguration.from_runnable_config(config)
            
            # Get the list of queries to search (same as local research)
            query_list = state.get("query_list", [])
            logger.info(f"Starting external ArXiv search for {len(query_list)} queries.") # INFO summary
            
            all_sources_gathered = []
            all_search_queries = []
            all_web_results = []
            
            # Process each query sequentially
            for i, query_item in enumerate(query_list): # Use query_item
                # Extract query string if it's a dict, otherwise use as-is
                query_str = query_item.get("query", query_item) if isinstance(query_item, dict) else query_item
                logger.debug(f"📡 External search {i+1}/{len(query_list)}: '{query_str}'") # DEBUG for per-query
                
                # Get raw results first for better source extraction (using ArXiv)
                raw_papers = self.external_tool.search_and_rank(
                    query_str,
                    limit=configurable.external_search_limit,
                    provider="arxiv"
                )
                
                # Log when no results are found but continue with the workflow
                if not raw_papers:
                    logger.debug(f"❌ No external papers found for query: '{query_str}'") # DEBUG
                else:
                    logger.debug(f"✅ Found {len(raw_papers)} external papers for query: '{query_str}'") # DEBUG
                
                # Generate formatted result for LLM consumption
                result = self.external_tool.find_papers_by_str(
                    query_str, 
                    limit=configurable.external_search_limit,
                    provider="arxiv"
                )
                
                # Enhanced source tracking with complete metadata (ArXiv-optimized)
                query_sources = []
                for paper in raw_papers:
                    # For ArXiv papers, use the direct PDF URL
                    paper_url = paper.get('url', '') or paper.get('pdf_url', '')
                    if not paper_url:
                        continue  # Skip papers without accessible URLs
                    
                    # Create short URL for citation tracking
                    short_url = self._generate_short_url(paper_url)
                    
                    # Clean up authors for display (ArXiv format)
                    authors = paper.get('authors_str', '')
                    if not authors and paper.get('authors'):
                        if isinstance(paper['authors'], list):
                            authors = ', '.join(paper['authors'][:3])  # Limit to first 3 authors
                            if len(paper['authors']) > 3:
                                authors += ' et al.'
                        else:
                            authors = str(paper['authors'])
                    
                    # Extract year from ArXiv published date
                    paper_year = paper.get('year')
                    if not paper_year and paper.get('published'):
                        try:
                            paper_year = int(paper.get('published', '1900')[:4])
                        except (ValueError, TypeError):
                            paper_year = None
                    
                    # Store comprehensive source metadata (ArXiv-specific)
                    source_entry = {
                        "short_url": short_url,
                        "value": paper_url,
                        "title": paper.get('title', 'Unknown Title').strip(),
                        "source_type": "external",
                        "source_provider": "arxiv",
                        "authors": authors,
                        "year": paper_year,
                        "published_date": paper.get('published'),
                        "abstract": paper.get('abstract', ''),
                        "venue": "arXiv preprint",  # ArXiv papers are preprints
                        "is_open_access": True,  # All ArXiv papers are open access
                        "pdf_url": paper_url,  # ArXiv URLs are direct PDF links
                        "external_ranking_score": paper.get('external_ranking_score', 0)
                    }
                    query_sources.append(source_entry)
                    
                    # Replace URLs in result text with short URLs for cleaner presentation
                    if paper_url in result:
                        result = result.replace(paper_url, short_url)
                    if paper.get('pdf_url') and paper['pdf_url'] in result:
                        result = result.replace(paper['pdf_url'], short_url)
                
                # Add this query's results to the aggregated results
                all_sources_gathered.extend(query_sources)
                all_search_queries.append(query_str)
                all_web_results.append(result)
                
                logger.debug(f"📊 External query {i+1} completed: {len(query_sources)} papers added") # DEBUG
            
            logger.info(f"External ArXiv search completed. Found {len(all_sources_gathered)} total papers.") # INFO summary
            
            # Debug logging for aggregated results
            if all_sources_gathered: # Check if there are any sources
                logger.debug(f"EXTERNAL SEARCH RESULT (first 5):") # DEBUG
                for i, source in enumerate(all_sources_gathered[:5]):  # Show first 5
                    logger.debug(f"  Source {i+1}: {source.get('title', 'Unknown')[:50]}... (Provider: {source.get('source_provider', 'none')})") # DEBUG
                if len(all_sources_gathered) > 5:
                    logger.debug(f"EXTERNAL SEARCH RESULT: ... and {len(all_sources_gathered) - 5} more sources") # DEBUG
            
            return_state = {
                "sources_gathered": all_sources_gathered, # This should likely append to existing state.sources_gathered if in parallel
                "search_query": all_search_queries, # Same as above
                "web_research_result": all_web_results, # Same as above
            }
            
            logger.debug(f"External research returning state with {len(all_sources_gathered)} sources_gathered") # DEBUG
            
            return return_state
            
        except Exception as e:
            logger.error(f"❌ Error in external research: {e}")
            query_list = state.get("query_list", [])
            return {
                "sources_gathered": [],
                "search_query": [str(query) for query in query_list],
                "web_research_result": [f"External search failed for queries: {query_list}"],
            }
    
    def _reflection(self, state: OverallState, config: RunnableConfig) -> ReflectionState:
        """Enhanced reflection on research progress with deeper analysis."""
        try:
            configurable = AgentConfiguration.from_runnable_config(config)
            
            # Increment research loop count
            state["research_loop_count"] = state.get("research_loop_count", 0) + 1
            current_loop = state["research_loop_count"]
            
            logger.info(f"🤔 Starting reflection analysis (Research Loop {current_loop})...")
            
            # Generate research insights from current findings
            web_results = state["web_research_result"]
            search_queries = state["search_query"]
            judged_sources = state.get("judged_sources", [])
            
            logger.info(f"📊 Analyzing {len(judged_sources)} relevant papers from {len(search_queries)} queries...")
            
            insights = generate_research_insights(web_results)
            
            # Combine and analyze search results
            combined_results = combine_search_results(
                web_results,
                search_queries
            )
            
            # Format the prompt with enhanced context
            current_date = get_current_date()
            
            # Include current outline in reflection
            current_outline = state.get("current_outline", "")
            outline_context = f"\n\nCurrent Research Outline:\n{current_outline}" if current_outline else ""
            
            formatted_prompt = reflection_instructions(
                current_date=current_date,
                research_topic=get_research_topic(state["messages"]),
                summaries=combined_results + outline_context,
            )
            
            # Add research insights to prompt
            if insights:
                formatted_prompt += f"\n\nResearch insights so far:\n{insights}"
            
            logger.debug(f"🧠 Running LLM reflection analysis...") # Changed to DEBUG
            
            # Get reflection from model
            llm = self.model_router.get_model("reflection")
            result = llm.invoke([], formatted_prompt, schema=Reflection, node_name="reflection")
            
            # Log reflection results
            gap_info = f" - Gap: {result.knowledge_gap[:100]}..." if result.knowledge_gap else ""
            follow_up_info = f" - {len(result.follow_up_queries)} follow-up queries generated" if result.follow_up_queries else " - No follow-up queries needed"
            
            logger.info(f"🤔 Reflection completed (Loop {current_loop}): Research {'sufficient' if result.is_sufficient else 'needs expansion'}{gap_info}{follow_up_info}")
            
            # Log follow-up queries if any
            if result.follow_up_queries:
                logger.info(f"Generated {len(result.follow_up_queries)} follow-up queries.") # New summary INFO
                for i, query_item in enumerate(result.follow_up_queries[:3]):  # Log first 3
                    actual_query = query_item.get("query") if isinstance(query_item, dict) else query_item # Handle query being dict or str
                    logger.debug(f"  📝 Follow-up query {i+1}: {actual_query}") # Changed to DEBUG
                if len(result.follow_up_queries) > 3:
                    logger.debug(f"  📝 ... and {len(result.follow_up_queries) - 3} more follow-up queries") # Changed to DEBUG
            
            return {
                "is_sufficient": result.is_sufficient,
                "knowledge_gap": result.knowledge_gap,
                "follow_up_queries": result.follow_up_queries,
                "research_loop_count": current_loop,
                "number_of_ran_queries": len(search_queries),
            }
            
        except Exception as e:
            logger.error(f"❌ Error in reflection: {e}")
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
                # Route to follow_up_research instead of non-existent sequential_external_research
                return "follow_up_research"
            else:
                logger.info("Research deemed sufficient, finalizing answer")
                return "finalize_answer"
                
        except Exception as e:
            logger.error(f"Error in research evaluation: {e}")
            return "finalize_answer"
    
    def _follow_up_research(self, state: OverallState, config: RunnableConfig) -> OverallState:
        """Perform follow-up research using BOTH local and external sources based on reflection feedback."""
        try:
            configurable = AgentConfiguration.from_runnable_config(config)
            
            # Get follow-up queries from reflection state
            follow_up_queries_raw = state.get("follow_up_queries", [])

            # Ensure follow_up_queries are strings if they are dicts from SearchQueryList
            follow_up_queries = []
            for item in follow_up_queries_raw:
                if isinstance(item, dict) and "query" in item:
                    follow_up_queries.append(item["query"])
                elif isinstance(item, str):
                    follow_up_queries.append(item)

            logger.debug(f"Processed follow-up queries: {follow_up_queries}") # Changed from INFO
            
            if not follow_up_queries:
                logger.warning("No valid follow-up queries found for follow-up research.") # Adjusted warning
                return state # Return current state, possibly with no new sources
            
            logger.info(f"Starting follow-up research for {len(follow_up_queries)} new queries.") # Adjusted INFO
            
            # Collect all results from both local and external searches for this round
            current_round_sources_gathered = []
            current_round_search_results = []
            current_round_search_queries = []
            
            # Process each query against BOTH local and external sources
            for idx, query_str in enumerate(follow_up_queries):
                logger.debug(f"Follow-up search {idx + 1}/{len(follow_up_queries)} for query: {query_str}") # Changed to DEBUG
                
                # === LOCAL SEARCH ===
                logger.debug(f"  → Local search for follow-up query: '{query_str}'") # Changed to DEBUG
                local_query_sources, local_result_text = [], f"No local results for '{query_str}'." # Default
                try:
                    # Search local database
                    local_raw_papers = self.local_tool.search_local_only(
                        query_str,
                        limit=configurable.local_search_limit
                    )
                    local_result_text = self.local_tool.find_papers_by_str( # Renamed variable
                        query_str,
                        limit=configurable.local_search_limit
                    )
                    
                    # Process local papers
                    local_query_sources = [] # Renamed variable
                    for paper in local_raw_papers:
                        paper_url = paper.get('url', '') or f"paper_id_{paper.get('id', 'unknown')}"
                        short_url = self._generate_short_url(paper_url)
                        paper_full_text = paper.get('text', '')
                        
                        source_entry = { # Using more descriptive name
                            "short_url": short_url, "value": paper_url,
                            "title": paper.get('title', 'Unknown Title').strip(),
                            "source_type": "local", "paper_id": paper.get('id'),
                            "authors": paper.get('authors', []), "year": paper.get('year'),
                            "abstract": paper.get('abstract', ''),
                            "has_full_text": bool(paper_full_text),
                            "full_text_length": len(paper_full_text) if paper_full_text else 0,
                            "full_text_attempted": False, "relevance_score": paper.get('hybrid_score', 0)
                        }
                        local_query_sources.append(source_entry)
                        
                        # Replace URLs in result text with short URLs
                        if paper_url and paper_url in local_result_text:
                            local_result_text = local_result_text.replace(paper_url, short_url)
                    
                    logger.debug(f"  → Local search found {len(local_query_sources)} papers for '{query_str}'.") # Changed to DEBUG
                    
                except Exception as e:
                    logger.error(f"Error in local follow-up search for '{query_str}': {e}")
                    local_query_sources = [] # Ensure it's defined in case of error
                    local_result_text = f"Local search failed for query: {query_str} - {str(e)}"
                
                # === EXTERNAL SEARCH ===
                logger.debug(f"  → External search for follow-up query: '{query_str}'") # Changed to DEBUG
                external_query_sources, external_result_text = [], f"No external results for '{query_str}'." # Default
                try:
                    # Add delay to be respectful to external APIs
                    if idx > 0 or (idx == 0 and len(state.get("search_query",[])) > 0) : # Add delay if not the very first search overall
                        import time
                        time.sleep(configurable.external_search_delay)
                    
                    # Search external sources (ArXiv)
                    external_raw_papers = self.external_tool.search_and_rank(
                        query_str,
                        limit=configurable.external_search_limit,
                        provider="arxiv"
                    )
                    external_result_text = self.external_tool.find_papers_by_str( # Renamed variable
                        query_str,
                        limit=configurable.external_search_limit,
                        provider="arxiv"
                    )
                    
                    # Process external papers
                    external_query_sources = [] # Renamed variable
                    for paper in external_raw_papers:
                        paper_url = paper.get('url', '') or paper.get('pdf_url', '')
                        if not paper_url:
                            continue
                        
                        short_url = self._generate_short_url(paper_url)
                        
                        # Clean up authors for display (ArXiv format)
                        authors = paper.get('authors_str', '')
                        if not authors and paper.get('authors'):
                            if isinstance(paper['authors'], list):
                                authors = ', '.join(paper['authors'][:3])
                                if len(paper['authors']) > 3:
                                    authors += ' et al.'
                            else:
                                authors = str(paper['authors'])
                        
                        # Extract year from ArXiv published date
                        paper_year = paper.get('year')
                        if not paper_year and paper.get('published'):
                            try:
                                paper_year = int(paper.get('published', '1900')[:4])
                            except (ValueError, TypeError):
                                paper_year = None
                        
                        source_entry = { # Using more descriptive name
                            "short_url": short_url, "value": paper_url,
                            "title": paper.get('title', 'Unknown Title').strip(),
                            "source_type": "external", "source_provider": "arxiv",
                            "authors": authors, "year": paper_year,
                            "published_date": paper.get('published'), "abstract": paper.get('abstract', ''),
                            "venue": "arXiv preprint", "is_open_access": True, "pdf_url": paper_url,
                            "external_ranking_score": paper.get('external_ranking_score', 0)
                        }
                        external_query_sources.append(source_entry)
                        
                        # Replace URLs in result text with short URLs
                        if paper_url in external_result_text:
                            external_result_text = external_result_text.replace(paper_url, short_url)
                        if paper.get('pdf_url') and paper['pdf_url'] in external_result_text:
                            external_result_text = external_result_text.replace(paper['pdf_url'], short_url)
                    
                    logger.debug(f"  → External search found {len(external_query_sources)} papers for '{query_str}'.") # Changed to DEBUG
                    
                except Exception as e:
                    logger.error(f"Error in external follow-up search for '{query_str}': {e}")
                    external_query_sources = [] # Ensure it's defined
                    external_result_text = f"External search failed for query: {query_str} - {str(e)}"
                
                # Combine results for this specific query
                combined_query_sources = local_query_sources + external_query_sources
                combined_query_result_text = f"### Follow-up Query: {query_str}\n\n"
                if local_query_sources or "No local results" not in local_result_text : combined_query_result_text += f"**Local Database Results:**\n{local_result_text}\n\n" # Check if there's actual content
                if external_query_sources or "No external results" not in external_result_text : combined_query_result_text += f"**External Search Results:**\n{external_result_text}\n\n" # Check if there's actual content
                
                logger.info(f"Follow-up research for query '{query_str}': {len(local_query_sources)} local, {len(external_query_sources)} external papers found.") # New INFO summary

                current_round_sources_gathered.extend(combined_query_sources)
                current_round_search_results.append(combined_query_result_text)
                current_round_search_queries.append(query_str)
                
                # logger.debug(f"Follow-up search {idx + 1} completed: {len(local_query_sources)} local + {len(external_query_sources)} external = {len(combined_query_sources)} total papers") # Changed from INFO
            
            logger.info(f"Follow-up research round completed. Found {len(current_round_sources_gathered)} total new sources.") # Adjusted INFO summary
            
            # Append new results to existing state
            # Note: LangGraph's operator.add on Annotated lists handles this accumulation if state is structured that way
            # If judged_sources is being replaced entirely each time, this manual append is correct for OverallState.
            return {
                **state,
                "sources_gathered": state.get("sources_gathered", []) + current_round_sources_gathered,
                "web_research_result": state.get("web_research_result", []) + current_round_search_results,
                "search_query": state.get("search_query", []) + current_round_search_queries,
                # judged_sources will be updated in the _judge_all_papers node after this
            }

        except Exception as e:
            logger.error(f"Error in follow-up research node: {e}") # Node-specific error
            return {
                **state,
                "sources_gathered": state.get("sources_gathered", []) + all_sources_gathered,
                "web_research_result": state.get("web_research_result", []) + all_search_results,
                "search_query": state.get("search_query", []) + all_search_queries,
            }
            
        except Exception as e:
            logger.error(f"Error in follow-up research: {e}")
            return {
                **state,
                "web_research_result": state.get("web_research_result", []) + [f"Follow-up research failed: {str(e)}"],
            }
    
    def _finalize_answer(self, state: OverallState, config: RunnableConfig):
        """Generate final comprehensive research summary with enhanced paper analysis."""
        try:
            configurable = AgentConfiguration.from_runnable_config(config)
            
            # Get research topic and sources
            research_topic_str = get_research_topic(state["messages"])
            
            # Retrieve configuration for token limits
            configurable = AgentConfiguration.from_runnable_config(config)
            max_tokens_for_context = configurable.max_research_context_tokens
            logger.debug(f"Max tokens for context set to: {max_tokens_for_context}") # DEBUG

            # Get judged sources (these should have been processed by _process_pdfs if applicable)
            judged_sources = state.get("judged_sources", [])
            if not judged_sources:
                logger.warning("No judged_sources found in state for final answer generation.")
                # Fallback to sources_gathered if judged_sources is empty
                judged_sources = state.get("sources_gathered", [])
                if not judged_sources:
                    logger.error("CRITICAL: No sources available at all in _finalize_answer. Returning error message.")
                    ai_message = AIMessage(content="I apologize, but I was unable to gather any research sources for your query.")
                    return {**state, "messages": [*state["messages"], ai_message]}

            # Sort sources by relevance score (descending)
            try:
                sorted_judged_sources = sorted(
                    judged_sources,
                    key=lambda x: float(x.get('relevance_score', 0) or 0),
                    reverse=True
                )
            except ValueError:
                logger.warning("Could not sort judged_sources by relevance_score due to invalid score type. Using original order.")
                sorted_judged_sources = judged_sources
            
            logger.debug(f"Processing {len(sorted_judged_sources)} sources for final context, sorted by relevance.") # DEBUG

            selected_papers_content_list = []
            current_context_tokens = 0
            included_paper_count = 0

            initial_full_text_count = 0
            initial_abstract_only_count = 0
            for source_check in judged_sources:
                has_text_flag = False # Corrected variable name
                if source_check.get("has_full_text"):
                    if source_check.get("source_type") == "local" and source_check.get("paper_id"):
                        paper_db_entry_check = self.db.get_paper_by_id(source_check["paper_id"])
                        if paper_db_entry_check and paper_db_entry_check.get('text'):
                            initial_full_text_count += 1
                            has_text_flag = True # Corrected variable name
                    elif source_check.get("source_type") == "external" and source_check.get("full_text_content_from_pdf"): # Assuming populated by _process_pdfs
                        initial_full_text_count += 1
                        has_text_flag = True # Corrected variable name
                if not has_text_flag: initial_abstract_only_count += 1 # Corrected variable name

            logger.info(f"Initial content availability for summarization context: {initial_full_text_count} full-text, {initial_abstract_only_count} abstract-only papers.")

            final_selection_full_text_count = 0

            for source in sorted_judged_sources:
                paper_text_content, content_type_included = None, "none"
                if source.get("has_full_text"):
                    if source.get("source_type") == "local" and source.get("paper_id"):
                        paper_db_entry = self.db.get_paper_by_id(source["paper_id"])
                        if paper_db_entry and paper_db_entry.get('text'):
                            paper_text_content, content_type_included = paper_db_entry.get('text'), "full_text_local_db"
                    elif source.get("source_type") == "external" and source.get("full_text_content_from_pdf"):
                         paper_text_content, content_type_included = source.get("full_text_content_from_pdf"), "full_text_external_processed"

                if paper_text_content is None and source.get("abstract"):
                    paper_text_content, content_type_included = source.get("abstract"), "abstract"

                if paper_text_content:
                    num_tokens = count_tokens(paper_text_content)
                    if current_context_tokens + num_tokens <= max_tokens_for_context:
                        authors = source.get('authors', 'N/A')
                        authors_str = ", ".join(authors) if isinstance(authors, list) else str(authors or 'N/A')
                        formatted_paper_entry = (f"Title: {source.get('title', 'N/A')}\n"
                                                 f"Authors: {authors_str}\n"
                                                 f"Year: {source.get('year', 'N/A')}\n"
                                                 f"Relevance Score: {source.get('relevance_score', 'N/A')}\n"
                                                 f"Source Type: {source.get('source_type', 'N/A')}\n"
                                                 f"Content Type Included: {content_type_included}\n"
                                                 f"Content:\n{paper_text_content}\n\n---\n")
                        selected_papers_content_list.append(formatted_paper_entry)
                        current_context_tokens += num_tokens
                        included_paper_count +=1
                        if content_type_included.startswith("full_text"): final_selection_full_text_count +=1
                        logger.debug(f"Included paper '{source.get('title', 'N/A')}' ({content_type_included}, {num_tokens} tokens). Total tokens: {current_context_tokens}/{max_tokens_for_context}") # DEBUG
                    else:
                        logger.debug(f"Skipping paper '{source.get('title', 'N/A')}' due to token limit. Needed: {num_tokens}, Available: {max_tokens_for_context - current_context_tokens}") # DEBUG
                        break
                else: logger.debug(f"Paper '{source.get('title', 'N/A')}' has no usable content.") # DEBUG

            final_selected_research_context_str = "\n".join(selected_papers_content_list)
            logger.info(f"Selected {included_paper_count} papers for LLM context ({current_context_tokens}/{max_tokens_for_context} tokens).") # New INFO log
            
            paper_access_note = ""
            if initial_full_text_count > 0 or initial_abstract_only_count > 0:
                paper_access_note = f"\n\nNote: The research found {initial_full_text_count} potentially full-text paper(s) and {initial_abstract_only_count} abstract-only paper(s)."
                if included_paper_count > 0:
                    paper_access_note += f" From these, {included_paper_count} paper(s) were selected for the context, including {final_selection_full_text_count} full-text(s), respecting a token limit of {max_tokens_for_context}."
                else:
                    paper_access_note += " However, no papers could be included in the final context due to token limits or lack of content."
            else:
                paper_access_note = "\n\nNote: No research papers were found or processed for this query."

            # Include final outline in answer generation
            current_outline = state.get("current_outline", "")
            outline_context = f"\n\n## Research Outline\n{current_outline}" if current_outline else ""
            
            # Enhanced answer instructions with paper access context
            summaries_for_llm = final_selected_research_context_str + paper_access_note + outline_context # Corrected: research_insights removed

            enhanced_instructions = answer_instructions(
                current_date=get_current_date(),
                research_topic=research_topic_str,
                summaries=summaries_for_llm
            )
            
            # Generate final answer using sources_gathered for citation mapping
            # Ensure sources_gathered reflects the papers that might be cited, ideally judged_sources
            sources_for_citation = judged_sources # Use the most refined list of sources for citation
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
                "sources_gathered": sources_for_citation, # Ensure this reflects what was available for citation
                "search_results": state.get("web_research_result", []),
                "full_text_papers": initial_full_text_count,
                "abstract_only_papers": initial_abstract_only_count,
                "included_in_context_papers": included_paper_count,
                "context_tokens": current_context_tokens
            }
            
            logger.info(f"Final research summary generated. Context: {included_paper_count} papers, {current_context_tokens} tokens.") # Adjusted INFO
            return final_state
            
        except Exception as e:
            logger.error(f"Error in finalize_answer: {e}")
            error_message = AIMessage(content=f"Error generating research summary: {str(e)}")
            return {
                **state,
                "messages": [*state["messages"], error_message],
                "sources_gathered": state.get("sources_gathered", [])
            }
    
    def _download_and_process_pdf_from_url(
        self, 
        pdf_url: str, 
        source: Dict[str, Any],
        research_query: str
    ) -> str:
        """
        Download PDF from URL and process it using robust PDF processing with multiple fallbacks.
        
        Args:
            pdf_url: URL to the PDF file
            source: Source metadata dictionary
            research_query: The research question for context
            
        Returns:
            Processed and summarized content from the PDF
        """
        import tempfile
        import os
        import requests
        
        temp_pdf_path = None
        try:
            from ..pdf.processing import SpacyLayoutDocProcessor
            from ..pdf.parsers import FlatMarkdownParser
            
            # Create temporary file for PDF download
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
                temp_pdf_path = temp_file.name
                logger.debug(f"Downloading PDF from {pdf_url} to {temp_pdf_path}...") # DEBUG
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                    'Accept': 'application/pdf,*/*',
                    'Accept-Language': 'en-US,en;q=0.9'
                }
                response = requests.get(pdf_url, timeout=60, headers=headers, stream=True)
                response.raise_for_status()
                
                # Check content type
                content_type = response.headers.get('content-type', '').lower()
                if 'pdf' not in content_type and 'application/octet-stream' not in content_type:
                    logger.warning(f"URL may not be a PDF (Content-Type: {content_type})")
                
                # Write PDF content
                for chunk in response.iter_content(chunk_size=8192):
                    temp_file.write(chunk)
            
            # Validate the downloaded file is actually a PDF
            try:
                with open(temp_pdf_path, 'rb') as f:
                    header = f.read(8)
                    if not header.startswith(b'%PDF'):
                        logger.warning(f"Downloaded file may not be a valid PDF (header: {header[:20]})")
                        return f"**{source.get('title', 'Unknown')}** - Downloaded file is not a valid PDF"
            except Exception as e:
                logger.warning(f"Could not validate PDF header: {e}")
            
            # Use existing SpacyLayoutDocProcessor (disable figures to avoid Docling issues)
            logger.debug(f"Processing PDF content using SpacyLayoutDocProcessor for {pdf_url}...") # DEBUG
            
            # Suppress torch warnings during PDF processing
            import warnings
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=UserWarning, module="torch")
                
                pdf_processor = SpacyLayoutDocProcessor(
                    language="en",
                    save_text=False,
                    export_tables=False,
                    export_figures=False,  # Disable figures to avoid Docling issues
                    remove_md_image_tags=True
                )
                
                # Process the PDF
                result = pdf_processor.process_document(temp_pdf_path)
                markdown_text = result.get('processed_data', '')
            
            if not markdown_text or len(markdown_text.strip()) < 200: return f"**{source.get('title', 'Unknown')}** - Failed to extract sufficient text from PDF (length: {len(markdown_text) if markdown_text else 0})"
            logger.debug(f"Successfully extracted {len(markdown_text)} chars of markdown from PDF {pdf_url}") # DEBUG
            
            # Use FlatMarkdownParser to chunk the content intelligently
            parser = FlatMarkdownParser(
                markdown_text, 
                max_tokens=8000,  # Reasonable chunk size for analysis
                remove_tables=True
            )
            
            chunks = parser.get_parsed_data()
            
            if not chunks: return f"**{source.get('title', 'Unknown')}** - Failed to parse extracted text into chunks"
            
            # Find most relevant chunks based on research query
            relevant_chunks = self._find_relevant_chunks(chunks, research_query)
            
            # Create enhanced summary with PDF source indication
            summary_parts = [
                f"**Paper: {source.get('title', 'Unknown Title')} [PDF PROCESSED]**",
                f"**Authors: {source.get('authors', 'Unknown')}**" if source.get('authors') else "",
                f"**Year: {source.get('year', 'Unknown')}**" if source.get('year') else "",
                f"**Source: {pdf_url}**",
                "",
                f"**Full Text Analysis from PDF (Query: {research_query})**",
                f"*Processed {len(chunks)} content chunks, showing {len(relevant_chunks[:3])} most relevant*",
                "",
                *relevant_chunks[:3]  # Top 3 most relevant chunks
            ]
            
            processed_summary = '\n'.join(filter(None, summary_parts))
            
            # If this is a local paper, update the database with the full text
            if source.get("paper_id") and source.get("source_type") == "local":
                try:
                    full_text = '\n'.join(chunks)  # Store all chunks as full text
                    self.db.update_paper_text(source["paper_id"], full_text)
                    logger.info(f"Updated database with full text for paper {source['paper_id']}") # Keep INFO
                except Exception as e:
                    logger.warning(f"Failed to update database with full text for {source['paper_id']}: {e}")
            
            logger.debug(f"Generated enhanced PDF summary ({len(processed_summary)} chars) from {len(chunks)} chunks for {pdf_url}") # DEBUG
            return processed_summary
                    
        except requests.RequestException as e:
            logger.error(f"Failed to download PDF from {pdf_url}: {e}") # Keep ERROR
            return f"**{source.get('title', 'Unknown')}** - PDF download failed: {str(e)}"
        except Exception as e:
            logger.error(f"Error processing PDF from {pdf_url}: {e}")
            return f"**{source.get('title', 'Unknown')}** - PDF processing error: {str(e)}"
        finally:
            # Clean up temporary file
            if temp_pdf_path and os.path.exists(temp_pdf_path):
                try:
                    os.unlink(temp_pdf_path)
                    logger.debug(f"Cleaned up temporary PDF file: {temp_pdf_path}") # DEBUG
                except Exception as e:
                    logger.warning(f"Could not clean up temporary file {temp_pdf_path}: {e}")
    
    def _process_full_text_with_existing_tools(
        self, 
        paper: Dict[str, Any], 
        research_query: str
    ) -> str:
        """
        Process a full text paper using existing SpacyLayoutDocProcessor and FlatMarkdownParser.
        
        Args:
            paper: Paper dictionary with full text content
            research_query: The research question for context
            
        Returns:
            Processed and summarized content
        """
        try:
            from ..pdf.parsers import FlatMarkdownParser
            
            full_text = paper.get('text', '')
            if not full_text or len(full_text) < 500: return f"**{paper.get('title', 'Unknown')}** - Limited content available"
            logger.debug(f"Processing full text for: {paper.get('title', 'Unknown')[:50]}... ({len(full_text)} chars)") # DEBUG
            
            # Use existing FlatMarkdownParser to intelligently chunk the content
            parser = FlatMarkdownParser(
                full_text, 
                max_tokens=8000,  # Smaller chunks for focused analysis
                remove_tables=True
            )
            
            # Get parsed chunks
            chunks = parser.get_parsed_data()
            
            if not chunks:
                return f"**{paper.get('title', 'Unknown')}** - Processing failed"
            
            # Find most relevant chunks based on research query
            relevant_chunks = self._find_relevant_chunks(chunks, research_query)
            
            # Create enhanced summary
            summary_parts = [
                f"**Paper: {paper.get('title', 'Unknown Title')}**",
                f"**Authors: {paper.get('authors', 'Unknown')}**" if paper.get('authors') else "",
                f"**Year: {paper.get('year', 'Unknown')}**" if paper.get('year') else "", "",
                f"**Full Text Analysis (Query: {research_query})**", "", *relevant_chunks[:3]]
            result = '\n'.join(filter(None, summary_parts))
            logger.debug(f"Generated enhanced summary ({len(result)} chars) from {len(chunks)} chunks for paper ID {paper.get('id')}") # DEBUG
            return result
            
        except Exception as e:
            logger.error(f"Error processing full text for paper {paper.get('id')}: {e}") # Keep ERROR
            return f"**{paper.get('title', 'Unknown')}** - Processing error: {str(e)}"
    
    def _find_relevant_chunks(self, chunks: List[str], research_query: str) -> List[str]:
        """
        Find the most relevant chunks based on keyword matching and content analysis.
        
        Args:
            chunks: List of text chunks from FlatMarkdownParser
            research_query: The research question
            
        Returns:
            List of relevant chunks, scored and sorted by relevance
        """
        try:
            # Extract key terms from research query
            query_terms = set(research_query.lower().split())
            query_terms.update([
                'abstract', 'conclusion', 'results', 'findings', 
                'methodology', 'approach', 'analysis', 'discussion'
            ])
            
            scored_chunks = []
            
            for chunk_idx, chunk in enumerate(chunks): # Add index for logging
                if len(chunk.strip()) < 100:  # Skip very short chunks
                    continue
                    
                chunk_lower = chunk.lower()
                
                # Score based on keyword matches
                score = 0
                for term in query_terms:
                    if term in chunk_lower:
                        score += chunk_lower.count(term)
                
                # Boost score for important sections
                if any(section in chunk_lower for section in ['abstract', 'conclusion', 'summary']):
                    score += 10
                elif any(section in chunk_lower for section in ['results', 'findings', 'analysis']):
                    score += 7
                elif any(section in chunk_lower for section in ['methodology', 'methods', 'approach']):
                    score += 5
                
                # Boost score for chunks with research-relevant terms
                research_terms = ['research', 'study', 'experiment', 'data', 'analysis', 'significant']
                for term in research_terms:
                    if term in chunk_lower:
                        score += 2
                
                if score > 0:
                    scored_chunks.append((chunk, score, chunk_idx)) # Store index too
            
            # Sort by score and return top chunks
            scored_chunks.sort(key=lambda x: x[1], reverse=True)
            relevant_chunks = [chunk for chunk, _, _ in scored_chunks[:5]] # Top 5 chunks
            
            logger.debug(f"Selected {len(relevant_chunks)} relevant chunks (indices: {[idx for _, _, idx in scored_chunks[:5]]}) from {len(chunks)} total.") # DEBUG
            return relevant_chunks
            
        except Exception as e:
            logger.error(f"Error finding relevant chunks: {e}") # Keep ERROR
            return chunks[:3]  # Fallback to first 3 chunks
    
    def _create_abstract_fallback(self, source: Dict[str, Any], research_query: str) -> str:
        """
        Create a fallback content analysis using only the abstract when PDF processing fails.
        
        Args:
            source: Source metadata dictionary
            research_query: The research question for context
            
        Returns:
            Abstract-based analysis content
        """
        try:
            title = source.get('title', 'Unknown Title')
            abstract = source.get('abstract', '')
            authors = source.get('authors', 'Unknown')
            year = source.get('year', 'Unknown')
            
            if not abstract or len(abstract.strip()) < 50:
                return None  # Don't create fallback if we don't have sufficient abstract
            
            # Create abstract-only analysis
            summary_parts = [
                f"**Paper: {title} [ABSTRACT ONLY]**",
                f"**Authors: {authors}**" if authors != 'Unknown' else "",
                f"**Year: {year}**" if year != 'Unknown' else "",
                "",
                f"**Abstract Analysis (Query: {research_query})**",
                f"*PDF processing failed or disabled - analysis based on abstract only*",
                "",
                f"**Abstract:** {abstract}",
                "",
                f"**Relevance to '{research_query}':** This paper appears relevant based on its abstract, " +
                f"which discusses concepts related to the research query. Full text analysis would provide " +
                f"more detailed insights into methodologies, results, and conclusions."
            ]
            
            result = '\n'.join(filter(None, summary_parts))
            logger.debug(f"Generated abstract-only fallback for: {title[:50]}... ({len(abstract)} char abstract)") # DEBUG
            return result
            
        except Exception as e:
            logger.error(f"Error creating abstract fallback for {source.get('title', 'N/A')}: {e}") # Keep ERROR
            return None
    
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
        
        # Filter out sources that don't have a short_url, or where it's None/empty
        valid_sources_for_mapping = [s for s in sources_gathered if s.get("short_url")]

        for source in valid_sources_for_mapping:
            short_url = source["short_url"] # Already checked it exists
            # Check if this short_url has already been processed to avoid duplicate reference numbers for same short_url
            if short_url not in source_mapping:
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
        
        # Use a function for replacement to handle cases where a short_url might not be in mapping
        def replace_func(match):
            short_url_found = match.group(0)
            if short_url_found in source_mapping:
                source_info = source_mapping[short_url_found]
                number = source_info["number"]
                url = source_info["url"]
                if url:
                    return f"[{number}]({url})"
                else:
                    return f"**[{number}]**" # Bold if no URL
            return short_url_found # Return original if not found in mapping (should not happen ideally)

        enhanced_content = re.sub(short_url_pattern, replace_func, content)
        
        # Build or enhance the References section
        if not source_mapping: return enhanced_content # No sources to reference

        references_lines = ["\n\n## References\n"] # Added extra newline for spacing
        
        # Sort sources by their assigned reference number
        # Ensure all items in source_mapping have a 'number' key before sorting
        valid_mapped_sources = [s_info for s_info in source_mapping.values() if "number" in s_info]
        sorted_sources = sorted(valid_mapped_sources, key=lambda x: x["number"])
        
        for source_info in sorted_sources:
            number = source_info["number"] # Keep for clarity
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
            reference_line = f"{s_info['number']}. {''.join(reference_parts)}" # Use s_info directly
            references_lines.append(reference_line)
        
        # Remove old references section if it exists, then append new one
        if "## References" in enhanced_content:
            lines = enhanced_content.split('\n')
            filtered_lines = []
            in_old_refs = False # Renamed for clarity
            for line in lines:
                if line.strip() == "## References":
                    in_old_refs = True
                    # Add our new header immediately, ensuring it's only added once
                    if not any(l.strip() == "## References" for l in filtered_lines):
                         filtered_lines.extend(references_lines)
                    continue
                elif in_old_refs and (line.startswith('## ') or line.startswith('# ')): # Check for any new H2 or H1
                    in_old_refs = False
                if not in_old_refs:
                    filtered_lines.append(line)
            enhanced_content = '\n'.join(filtered_lines)
            # If "## References" was not found, but we have references, append them.
            # This case handles if the original content didn't have "## References" but we want to add it.
            if not any(line.strip() == "## References" for line in enhanced_content.split('\n')) and len(sorted_sources) > 0:
                 enhanced_content += '\n'.join(references_lines)

        elif len(sorted_sources) > 0: # No existing "## References", but we have references to add
            enhanced_content += '\n'.join(references_lines)

        
        logger.debug(f"Enhanced content with {len(sorted_sources)} numbered reference links.") # DEBUG
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
            
            # Set up initial state with additive effort configuration
            effort_config = config or {}
            
            # Load database configuration to get the actual configured values
            from .unified_model_router import UnifiedModelRouter
            router = UnifiedModelRouter(self.db)
            db_config = router.get_configuration()
            
            # Apply additive effort bonuses to base configuration if provided
            from .graph_configuration import AgentConfiguration
            base_config = AgentConfiguration()
            
            # Start with database configuration values, not hardcoded defaults
            effort_config["initial_search_query_count"] = db_config.get("initial_search_query_count", base_config.number_of_initial_queries)
            effort_config["max_research_loops"] = db_config.get("max_research_loops", base_config.max_research_loops)
            effort_config["local_search_limit"] = db_config.get("local_search_limit", base_config.local_search_limit)
            effort_config["external_search_limit"] = db_config.get("external_search_limit", base_config.external_search_limit)
            
            if effort_config.get("loops_bonus"):
                effort_config["max_research_loops"] = effort_config["max_research_loops"] + effort_config["loops_bonus"]
            
            if effort_config.get("papers_bonus"):
                # Add bonus papers to both local and external search limits
                bonus_papers = effort_config["papers_bonus"]
                local_bonus = max(1, bonus_papers * 2 // 3)  # 67% to local search
                external_bonus = max(1, bonus_papers // 3)   # 33% to external search
                
                effort_config["local_search_limit"] = effort_config["local_search_limit"] + local_bonus
                effort_config["external_search_limit"] = effort_config["external_search_limit"] + external_bonus
            
            initial_state = {
                "messages": messages,
                **effort_config
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
            
            # Set up initial state with additive effort configuration
            effort_config = config or {}
            
            # Load database configuration to get the actual configured values
            router = UnifiedModelRouter(self.db)
            db_config = router.get_configuration()
            
            # Apply additive effort bonuses to base configuration if provided
            from .graph_configuration import AgentConfiguration
            base_config = AgentConfiguration()
            
            # Start with database configuration values, not hardcoded defaults
            effort_config["initial_search_query_count"] = db_config.get("initial_search_query_count", base_config.number_of_initial_queries)
            effort_config["max_research_loops"] = db_config.get("max_research_loops", base_config.max_research_loops)
            effort_config["local_search_limit"] = db_config.get("local_search_limit", base_config.local_search_limit)
            effort_config["external_search_limit"] = db_config.get("external_search_limit", base_config.external_search_limit)
            
            if effort_config.get("loops_bonus"):
                effort_config["max_research_loops"] = effort_config["max_research_loops"] + effort_config["loops_bonus"]
            
            if effort_config.get("papers_bonus"):
                # Add bonus papers to both local and external search limits
                bonus_papers = effort_config["papers_bonus"]
                local_bonus = max(1, bonus_papers * 2 // 3)  # 67% to local search
                external_bonus = max(1, bonus_papers // 3)   # 33% to external search
                
                effort_config["local_search_limit"] = effort_config["local_search_limit"] + local_bonus
                effort_config["external_search_limit"] = effort_config["external_search_limit"] + external_bonus
            
            initial_state = {
                "messages": messages,
                **effort_config
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
            
            # Set up initial state with additive effort configuration
            effort_config = config or {}
            
            # Load database configuration to get the actual configured values
            router = UnifiedModelRouter(self.db)
            db_config = router.get_configuration()
            
            # Apply additive effort bonuses to base configuration if provided
            from .graph_configuration import AgentConfiguration
            base_config = AgentConfiguration()
            
            # Start with database configuration values, not hardcoded defaults
            effort_config["initial_search_query_count"] = db_config.get("initial_search_query_count", base_config.number_of_initial_queries)
            effort_config["max_research_loops"] = db_config.get("max_research_loops", base_config.max_research_loops)
            effort_config["local_search_limit"] = db_config.get("local_search_limit", base_config.local_search_limit)
            effort_config["external_search_limit"] = db_config.get("external_search_limit", base_config.external_search_limit)
            
            if effort_config.get("loops_bonus"):
                effort_config["max_research_loops"] = effort_config["max_research_loops"] + effort_config["loops_bonus"]
            
            if effort_config.get("papers_bonus"):
                # Add bonus papers to both local and external search limits
                bonus_papers = effort_config["papers_bonus"]
                local_bonus = max(1, bonus_papers * 2 // 3)  # 67% to local search
                external_bonus = max(1, bonus_papers // 3)   # 33% to external search
                
                effort_config["local_search_limit"] = effort_config["local_search_limit"] + local_bonus
                effort_config["external_search_limit"] = effort_config["external_search_limit"] + external_bonus
            
            initial_state = {
                "messages": messages,
                **effort_config
            }
            
            # Stream the graph execution
            async for chunk in self.graph.astream(initial_state):
                yield chunk
                
        except Exception as e:
            logger.error(f"Error in streaming research: {e}")
            yield {
                "error": f"Research streaming failed: {str(e)}"
            }
    

    
    def _are_sources_duplicate(self, source1: Dict[str, Any], source2: Dict[str, Any]) -> bool:
        """Check if two sources represent the same paper using multiple criteria."""
        # Check by URL/value
        if (source1.get("value") and source2.get("value") and 
            source1["value"] == source2["value"]):
            return True
        
        # Check by title similarity (exact match after normalization)
        title1 = source1.get("title", "").lower().strip()
        title2 = source2.get("title", "").lower().strip()
        if title1 and title2 and title1 == title2:
            return True
        
        # Check for ArXiv papers by extracting ArXiv ID
        def extract_arxiv_id(url_or_title):
            if not url_or_title:
                return None
            # Look for ArXiv ID pattern (e.g., 2301.12345)
            import re
            match = re.search(r'(\d{4}\.\d{4,5})', str(url_or_title))
            return match.group(1) if match else None
        
        arxiv_id1 = extract_arxiv_id(source1.get("value")) or extract_arxiv_id(source1.get("title"))
        arxiv_id2 = extract_arxiv_id(source2.get("value")) or extract_arxiv_id(source2.get("title"))
        
        if arxiv_id1 and arxiv_id2 and arxiv_id1 == arxiv_id2:
            return True
        
        return False




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