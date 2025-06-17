"""
Query Planner Node for Research Agent

This node decomposes complex research questions into focused sub-queries
that can be effectively searched across different sources.
"""

import logging
from typing import Dict, Any, List

from ..state import OverallState, Message
from ..prompts import planner_prompt
from ..model_router import get_model_for_node, supports_structured_output
from ..schemas import QueryPlanningResponse, StructuredParsingHelper

logger = logging.getLogger(__name__)


class QueryPlannerNode:
    """
    Node responsible for decomposing research questions into searchable sub-queries.
    
    Takes the main research question and breaks it down into 5 focused sub-queries
    that can be effectively searched across local and external sources.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the Query Planner Node.
        
        Args:
            config: Configuration dictionary containing model settings
        """
        self.config = config
        self.max_sub_queries = config.get('max_sub_queries', 5)
        self.fallback_queries = config.get('enable_fallback_queries', True)
        
    def __call__(self, state: OverallState) -> Dict[str, Any]:
        """
        Execute query planning to break down the research question.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with sub_queries populated
        """
        try:
            # Increment loop counter if this is a continuing research loop
            # (indicated by having existing evidence or judged_sources)
            current_loop_count = state.get("research_loop_count", 0)
            if state.get("evidence", []) or state.get("judged_sources", []):
                current_loop_count += 1
                logger.info(f"Continuing research - incremented to loop {current_loop_count}")
            
            # Return the updated loop count in the state update
            loop_update = {"research_loop_count": current_loop_count}
            
            # Extract the research question from messages
            research_question = self._extract_research_question(state)
            
            if not research_question:
                logger.error("No research question found in state")
                result = {
                    "sub_queries": self._generate_fallback_queries("general research"),
                    "messages": [Message(role="assistant", content="Using fallback queries due to missing research question")]
                }
                result.update(loop_update)
                return result
            
            logger.info(f"Planning queries for: {research_question}")
            
            # Get the model for query planning
            model = get_model_for_node("query_planner", self.config)
            
            # Generate the planning prompt
            prompt = planner_prompt(research_question, self.max_sub_queries)
            
            # Get LLM response using unified interface with structured output if supported
            messages = [{"role": "user", "content": prompt}]
            system_prompt = "You are a research assistant that breaks down complex questions into focused sub-queries."
            
            # Try structured output first if supported
            structured_response = None
            if supports_structured_output(model.provider):
                try:
                    response = model.invoke(
                        messages, 
                        system_prompt, 
                        schema=QueryPlanningResponse
                    )
                    # Parse structured response if it's JSON
                    if isinstance(response, str):
                        structured_response = StructuredParsingHelper.parse_with_fallback(
                            response, QueryPlanningResponse, logger
                        )
                    else:
                        # Response is already structured
                        structured_response = response
                except Exception as e:
                    logger.warning(f"Structured output failed, falling back to text parsing: {e}")
            
            # Fallback to regular response if structured failed
            if structured_response is None:
                response = model.invoke(messages, system_prompt)
                structured_response = StructuredParsingHelper.parse_with_fallback(
                    response, QueryPlanningResponse, logger
                )
            
            # Extract sub-queries from structured response or fallback to manual parsing
            if structured_response and isinstance(structured_response, QueryPlanningResponse):
                sub_queries = structured_response.sub_queries
                planning_rationale = structured_response.planning_rationale
                logger.info(f"Structured query planning successful: {planning_rationale}")
            else:
                # Fallback to manual parsing
                logger.warning("Using fallback parsing for query planning")
                response = model.invoke(messages, system_prompt) if 'response' not in locals() else response
                sub_queries = self._parse_sub_queries(response, research_question)
                planning_rationale = "Fallback query generation"
            
            # Validate and ensure we have enough queries
            if len(sub_queries) < 3:
                logger.warning(f"Only got {len(sub_queries)} sub-queries, adding fallbacks")
                sub_queries.extend(self._generate_fallback_queries(research_question))
                sub_queries = sub_queries[:self.max_sub_queries]
            
            logger.info(f"Generated {len(sub_queries)} sub-queries")
            
            # Create planning summary
            planning_summary = self._create_planning_summary(research_question, sub_queries, planning_rationale)
            
            result = {
                "sub_queries": sub_queries,
                "messages": [Message(role="assistant", content=f"Query planning complete: {planning_summary}")]
            }
            result.update(loop_update)
            return result
            
        except Exception as e:
            logger.error(f"Error in query planning: {str(e)}")
            
            # Fallback to basic queries
            research_question = self._extract_research_question(state) or "research topic"
            fallback_queries = self._generate_fallback_queries(research_question)
            
            result = {
                "sub_queries": fallback_queries,
                "messages": [Message(role="assistant", content=f"Query planning failed, using fallback queries: {str(e)}")]
            }
            # Ensure loop_update exists for error case
            current_loop_count = state.get("research_loop_count", 0)
            if state.get("evidence", []) or state.get("judged_sources", []):
                current_loop_count += 1
            result.update({"research_loop_count": current_loop_count})
            return result
    
    def _extract_research_question(self, state: OverallState) -> str:
        """
        Extract the research question from the state messages.
        
        Args:
            state: Current workflow state
            
        Returns:
            The research question string
        """
        messages = state.get("messages", [])
        if not messages:
            return ""
        
        # Get the first user message as the research question
        for message in messages:
            if isinstance(message, dict) and message.get("content", "").strip():
                return message["content"].strip()
            elif hasattr(message, 'content') and message.content.strip():
                return message.content.strip()
        
        return ""
    
    def _parse_sub_queries(self, response_content: str, original_question: str) -> List[str]:
        """
        Parse sub-queries from LLM response with intelligent fallbacks.
        
        Args:
            response_content: Raw LLM response
            original_question: Original research question for fallback
            
        Returns:
            List of parsed sub-queries
        """
        sub_queries = []
        
        try:
            # Split by lines and clean up
            lines = [line.strip() for line in response_content.split('\n') if line.strip()]
            
            for line in lines:
                # Remove numbering and bullet points
                cleaned_line = line
                
                # Remove common prefixes
                prefixes_to_remove = [
                    r'^\d+\.\s*',  # "1. "
                    r'^\d+\)\s*',  # "1) "
                    r'^[-*•]\s*',  # "- ", "* ", "• "
                    r'^Query\s*\d*:\s*',  # "Query 1: "
                    r'^Sub-query\s*\d*:\s*',  # "Sub-query 1: "
                ]
                
                import re
                for prefix in prefixes_to_remove:
                    cleaned_line = re.sub(prefix, '', cleaned_line, flags=re.IGNORECASE)
                
                cleaned_line = cleaned_line.strip()
                
                # Skip empty lines or very short queries
                if len(cleaned_line) > 10 and cleaned_line.endswith('?'):
                    sub_queries.append(cleaned_line)
                elif len(cleaned_line) > 15:  # Accept non-question format if substantial
                    # Convert to question format if needed
                    if not cleaned_line.endswith('?'):
                        cleaned_line = f"What {cleaned_line.lower()}?"
                    sub_queries.append(cleaned_line)
            
            # If we didn't get enough queries, try a different parsing approach
            if len(sub_queries) < 3:
                # Try splitting by question marks
                question_parts = response_content.split('?')
                for part in question_parts[:-1]:  # Exclude last empty part
                    cleaned_part = part.strip()
                    if len(cleaned_part) > 10:
                        # Clean up and add question mark back
                        import re
                        cleaned_part = re.sub(r'^\d+\.\s*', '', cleaned_part)
                        cleaned_part = re.sub(r'^[-*•]\s*', '', cleaned_part)
                        sub_queries.append(f"{cleaned_part.strip()}?")
            
        except Exception as e:
            logger.warning(f"Error parsing sub-queries: {str(e)}")
        
        # Remove duplicates while preserving order
        seen = set()
        unique_queries = []
        for query in sub_queries:
            if query.lower() not in seen:
                seen.add(query.lower())
                unique_queries.append(query)
        
        return unique_queries[:self.max_sub_queries]
    
    def _generate_fallback_queries(self, research_question: str) -> List[str]:
        """
        Generate simple, broad fallback queries when LLM parsing fails.
        
        Args:
            research_question: Original research question
            
        Returns:
            List of simple fallback sub-queries
        """
        # Extract key terms from the research question
        import re
        
        # Remove common question words and get key terms
        key_terms = re.findall(r'\b[A-Za-z]{3,}\b', research_question.lower())
        key_terms = [term for term in key_terms if term not in {
            'what', 'how', 'why', 'when', 'where', 'who', 'which', 'does', 'can', 'will',
            'the', 'and', 'for', 'are', 'with', 'this', 'that', 'from', 'they', 'have'
        }]
        
        # Take first few key terms
        main_terms = key_terms[:3] if key_terms else ['research', 'analysis']
        
        # Generate simpler, broader queries (no question format)
        fallback_queries = [
            f"{main_terms[0]}" if main_terms else "research",
            f"{main_terms[0]} {main_terms[1]}" if len(main_terms) >= 2 else f"{main_terms[0]} systems" if main_terms else "research systems",
            f"{main_terms[0]} applications" if main_terms else "research applications",
            f"{main_terms[0]} trends" if main_terms else "research trends",
            f"{' '.join(main_terms[:2])}" if len(main_terms) >= 2 else f"{main_terms[0]} methods" if main_terms else "research methods"
        ]
        
        return fallback_queries
    
    def _create_planning_summary(self, research_question: str, sub_queries: List[str], planning_rationale: str = "") -> str:
        """
        Create a summary of the query planning process.
        
        Args:
            research_question: Original research question
            sub_queries: Generated sub-queries
            
        Returns:
            Planning summary string
        """
        summary = f"Decomposed research question into {len(sub_queries)} focused sub-queries:\n"
        for i, query in enumerate(sub_queries, 1):
            summary += f"{i}. {query}\n"
        
        return summary.strip()

    def get_node_info(self) -> Dict[str, Any]:
        """Get information about this node for monitoring and debugging."""
        return {
            "node_type": "query_planner",
            "max_sub_queries": self.max_sub_queries,
            "config_keys": list(self.config.keys()) if self.config else [],
            "description": "Decomposes research questions into focused sub-queries for comprehensive search"
        }


def create_query_planner_node(config: Dict[str, Any]) -> QueryPlannerNode:
    """
    Factory function to create a QueryPlannerNode instance.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Configured QueryPlannerNode instance
    """
    return QueryPlannerNode(config) 