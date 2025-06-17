"""
Evidence Selector Node for Research Agent

Evaluates gathered sources for quality, relevance, and sufficiency
to determine if the evidence is adequate for generating a comprehensive answer.
"""

import logging
from typing import Dict, Any, List

from ..state import OverallState, Message
from ..prompts import evidence_selector_prompt
from ..model_router import supports_structured_output
from ..schemas import EvidenceSelectionResponse, StructuredParsingHelper


class EvidenceSelectorNode:
    """
    LangGraph node that evaluates evidence quality and sufficiency.
    
    This node analyzes all gathered sources to determine:
    1. Which sources are most relevant and high-quality
    2. Whether the evidence is sufficient to answer the research question
    3. What additional information might be needed
    """
    
    def __init__(
        self, 
        config: Dict[str, Any],
        min_evidence_threshold: int = 2,
        max_evidence_per_query: int = 8,
        quality_threshold: float = 0.3
    ):
        """
        Initialize the evidence selector node.
        
        Args:
            config: Configuration dictionary containing model settings
            min_evidence_threshold: Minimum number of high-quality sources needed
            max_evidence_per_query: Maximum evidence pieces to select per sub-query
            quality_threshold: Minimum quality score for evidence selection
        """
        self.config = config
        from ..model_router import get_model_for_node
        self.model_client = get_model_for_node("evidence_selector", config)
        self.min_evidence_threshold = min_evidence_threshold
        self.max_evidence_per_query = max_evidence_per_query
        self.quality_threshold = quality_threshold
        self.logger = logging.getLogger(__name__)
    
    def __call__(self, state: OverallState) -> Dict[str, Any]:
        """
        Execute evidence selection and evaluation.
        
        Args:
            state: Current research agent state
            
        Returns:
            Updated state with selected evidence and sufficiency assessment
        """
        self.logger.info("Starting evidence selection")
        
        try:
            # Get sources from state
            sources_gathered = state.get("sources_gathered", [])
            if not sources_gathered:
                self.logger.warning("No sources available for evidence selection")
                return {
                    "judged_sources": [],
                    "evidence": [],
                    "is_sufficient": False,
                    "messages": [Message(role="assistant", content="⚠️ No sources available for evidence selection. Please run retrieval first.")]
                }
            
            # Extract the main research question
            main_question = self._extract_main_question(state.get("messages", []))
            
            # Evaluate and select evidence
            selected_evidence, judged_sources, sufficiency_assessment = self._evaluate_evidence(
                main_question, sources_gathered
            )
            
            # Create evidence selection summary
            selection_summary = self._create_selection_summary(
                sources_gathered, selected_evidence, judged_sources, sufficiency_assessment
            )
            
            self.logger.info(
                f"Evidence selection complete: {len(selected_evidence)} evidence pieces selected, "
                f"sufficient: {sufficiency_assessment['is_sufficient']}"
            )
            
            return {
                "judged_sources": judged_sources,
                "evidence": selected_evidence,
                "is_sufficient": sufficiency_assessment['is_sufficient'],
                "messages": [Message(role="assistant", content=selection_summary)]
            }
            
        except Exception as e:
            self.logger.error(f"Error in evidence selection: {e}")
            return {
                "judged_sources": [],
                "evidence": [],
                "is_sufficient": False,
                "messages": [Message(role="assistant", content=f"🚨 Evidence selection error: {str(e)}. Using all sources as fallback.")]
            }
    
    def _extract_main_question(self, messages: List) -> str:
        """Extract the main research question from messages."""
        for message in reversed(messages):
            if hasattr(message, 'role') and message.role == 'user' and hasattr(message, 'content'):
                return message.content.strip()
        
        return "Research question not found"
    
    def _evaluate_evidence(
        self, 
        main_question: str, 
        sources_gathered: List[Dict[str, Any]]
    ) -> tuple:
        """
        Evaluate sources and select the best evidence.
        
        Args:
            main_question: The main research question
            sources_gathered: All gathered sources from retrieval
            
        Returns:
            Tuple of (selected_evidence, judged_sources, sufficiency_assessment)
        """
        # Group sources by sub-query for balanced selection
        sources_by_query = {}
        for source in sources_gathered:
            query_index = source.get('query_index', 0)
            if query_index not in sources_by_query:
                sources_by_query[query_index] = []
            sources_by_query[query_index].append(source)
        
        # Select best sources from each query group
        selected_evidence = []
        judged_sources = []
        
        for query_index, query_sources in sources_by_query.items():
            # Sort by relevance score
            sorted_sources = sorted(
                query_sources, 
                key=lambda x: x.get('relevance_score', 0), 
                reverse=True
            )
            
            # Select top sources - be more permissive with relevance threshold
            query_evidence = []
            for source in sorted_sources[:self.max_evidence_per_query]:
                # Use a very low threshold to include more diverse sources
                relevance = source.get('relevance_score', 0)
                if relevance >= self.quality_threshold or len(query_evidence) < 2:
                    evidence_text = self._extract_evidence_text(source)
                    if evidence_text:
                        query_evidence.append(evidence_text)
                        judged_sources.append(source)
            
            selected_evidence.extend(query_evidence)
        
        # Assess sufficiency using LLM
        sufficiency_assessment = self._assess_sufficiency(
            main_question, selected_evidence, len(sources_gathered)
        )
        
        return selected_evidence, judged_sources, sufficiency_assessment
    
    def _extract_evidence_text(self, source: Dict[str, Any]) -> str:
        """
        Extract evidence text from a source.
        
        Args:
            source: Source dictionary with paper information
            
        Returns:
            Formatted evidence text
        """
        paper_info = source.get('paper_info')
        if not paper_info:
            return ""
        
        # Create evidence text with metadata
        evidence_parts = [
            f"**Source**: {paper_info.title}",
            f"**Relevance Score**: {source.get('relevance_score', 0):.3f}",
            f"**Source Type**: {paper_info.source.upper()}",
        ]
        
        # Add URL if available
        if paper_info.url:
            evidence_parts.append(f"**URL**: {paper_info.url}")
        
        # Add abstract as the main evidence
        if paper_info.abstract:
            evidence_parts.extend([
                "",
                "**Abstract**:",
                paper_info.abstract
            ])
        
        # Add note about full text availability
        has_full_text = bool(paper_info.raw_data.get('text'))
        if has_full_text:
            evidence_parts.append("\n*Note: Full text available for detailed analysis*")
        elif paper_info.url:
            evidence_parts.append(f"\n*Note: Full text can be retrieved from {paper_info.url}*")
        
        return "\n".join(evidence_parts)
    
    def _assess_sufficiency(
        self, 
        main_question: str, 
        evidence_pieces: List[str], 
        total_sources: int
    ) -> Dict[str, Any]:
        """
        Assess whether the evidence is sufficient to answer the research question.
        
        Args:
            main_question: The main research question
            evidence_pieces: Selected evidence pieces
            total_sources: Total number of sources found
            
        Returns:
            Sufficiency assessment dictionary
        """
        try:
            # Use LLM to assess sufficiency with structured output if supported
            prompt = evidence_selector_prompt(main_question, evidence_pieces)
            messages = [{"role": "user", "content": prompt}]
            system_prompt = "You are a research assistant that evaluates evidence quality and sufficiency."
            
            # Try structured output first if supported
            structured_response = None
            if supports_structured_output(self.model_client.provider):
                try:
                    response = self.model_client.invoke(
                        messages, 
                        system_prompt, 
                        schema=EvidenceSelectionResponse
                    )
                    # Parse structured response if it's JSON
                    if isinstance(response, str):
                        structured_response = StructuredParsingHelper.parse_with_fallback(
                            response, EvidenceSelectionResponse, self.logger
                        )
                    else:
                        # Response is already structured
                        structured_response = response
                except Exception as e:
                    self.logger.warning(f"Structured output failed, falling back to text parsing: {e}")
            
            # Fallback to regular response if structured failed
            if structured_response is None:
                response = self.model_client.invoke(messages, system_prompt)
                structured_response = StructuredParsingHelper.parse_with_fallback(
                    response, EvidenceSelectionResponse, self.logger
                )
            
            # Extract sufficiency assessment from structured response or fallback to manual parsing
            llm_sufficient = False
            if structured_response and isinstance(structured_response, EvidenceSelectionResponse):
                llm_sufficient = structured_response.sufficiency_assessment.is_sufficient
                self.logger.info(f"Structured evidence assessment successful: {structured_response.selection_summary}")
            else:
                # Fallback to manual parsing
                self.logger.warning("Using fallback parsing for evidence selection")
                response = self.model_client.invoke(messages, system_prompt) if 'response' not in locals() else response
                llm_sufficient = self._parse_sufficiency_response(response)
            
            # ENHANCED HEURISTIC CHECKS - More conservative approach
            # Basic requirements: minimum sources AND evidence pieces
            basic_requirements = (
                len(evidence_pieces) >= self.min_evidence_threshold and
                total_sources >= self.min_evidence_threshold
            )
            
            # Quality requirements: ensure we have diverse, high-quality sources
            # Make this more lenient for local models to prevent infinite loops
            quality_requirements = (
                len(evidence_pieces) >= max(2, self.min_evidence_threshold - 1) and  # Reduced from 3 to 2
                total_sources >= max(3, self.min_evidence_threshold)  # Reduced from 5 to 3
            )
            
            # Conservative heuristic: only sufficient if both basic and quality requirements met
            heuristic_sufficient = basic_requirements and quality_requirements
            
            # CONSERVATIVE SAFETY MECHANISM - Only for extreme cases
            # Make this more reasonable for local models
            safety_sufficient = (
                len(evidence_pieces) >= 5 and  # Reduced from 7 to 5
                total_sources >= 8  # Reduced from 15 to 8
            )
            
            # PROGRESSIVE LENIENCY: Be more lenient in later research loops to prevent infinite loops
            # Get the current loop count from state if available
            current_loop = 0
            try:
                # Try to infer loop count from evidence patterns or use a simple heuristic
                if len(evidence_pieces) > 0:
                    current_loop = min(len(evidence_pieces) // 2, 3)  # Rough estimate
            except:
                current_loop = 0
            
            # Progressive leniency: reduce requirements in later loops
            if current_loop >= 2:
                # In later loops, be much more lenient to prevent infinite loops
                progressive_sufficient = (
                    len(evidence_pieces) >= 1 and  # Just need 1 evidence piece
                    total_sources >= 2  # Just need 2 sources searched
                )
                self.logger.info(f"Progressive leniency activated (loop ~{current_loop}): {progressive_sufficient}")
            else:
                progressive_sufficient = False
            
            # CONSERVATIVE COMBINATION LOGIC
            # Only mark as sufficient if:
            # 1. LLM says sufficient AND heuristics agree, OR
            # 2. Safety mechanism triggered (for extreme cases), OR  
            # 3. Progressive leniency triggered (to prevent infinite loops)
            conservative_sufficient = (
                (llm_sufficient and heuristic_sufficient) or 
                safety_sufficient or 
                progressive_sufficient
            )
            
            # ADDITIONAL SAFEGUARD: Never mark sufficient with fewer than 1 evidence pieces
            # (Reduced from 2 to 1 to be more reasonable)
            minimum_evidence_safeguard = len(evidence_pieces) >= 1
            
            # Final decision: combine all checks
            final_sufficient = conservative_sufficient and minimum_evidence_safeguard
            
            # Enhanced logging for debugging
            self.logger.info(f"Evidence assessment breakdown:")
            self.logger.info(f"  - Evidence pieces: {len(evidence_pieces)}, Total sources: {total_sources}")
            self.logger.info(f"  - LLM assessment: {llm_sufficient}")
            self.logger.info(f"  - Basic requirements: {basic_requirements}")
            self.logger.info(f"  - Quality requirements: {quality_requirements}")
            self.logger.info(f"  - Heuristic sufficient: {heuristic_sufficient}")
            self.logger.info(f"  - Safety sufficient: {safety_sufficient}")
            self.logger.info(f"  - Progressive sufficient: {progressive_sufficient}")
            self.logger.info(f"  - Min evidence safeguard: {minimum_evidence_safeguard}")
            self.logger.info(f"  - FINAL DECISION: {final_sufficient}")
            
            # Log the decision reasoning
            if final_sufficient:
                if safety_sufficient:
                    self.logger.info(f"Evidence deemed sufficient by safety mechanism: {len(evidence_pieces)} pieces, {total_sources} total sources")
                elif progressive_sufficient:
                    self.logger.info(f"Evidence deemed sufficient by progressive leniency: {len(evidence_pieces)} pieces, {total_sources} total sources")
                else:
                    self.logger.info(f"Evidence deemed sufficient: LLM={llm_sufficient}, heuristic={heuristic_sufficient}")
            else:
                if not minimum_evidence_safeguard:
                    self.logger.info(f"Evidence deemed insufficient: minimum evidence safeguard failed ({len(evidence_pieces)} < 1)")
                elif not llm_sufficient:
                    self.logger.info(f"Evidence deemed insufficient: LLM assessment negative")
                elif not heuristic_sufficient:
                    self.logger.info(f"Evidence deemed insufficient: heuristic requirements not met")
                else:
                    self.logger.info(f"Evidence deemed insufficient: {len(evidence_pieces)} pieces, {total_sources} total sources")
            
            return {
                'is_sufficient': final_sufficient,
                'llm_assessment': llm_sufficient,
                'heuristic_assessment': heuristic_sufficient,
                'safety_assessment': safety_sufficient,
                'evidence_count': len(evidence_pieces),
                'total_sources': total_sources,
                'minimum_evidence_safeguard': minimum_evidence_safeguard,
                'reasoning': response if 'response' in locals() else "Structured response used"
            }
            
        except Exception as e:
            self.logger.error(f"Error in sufficiency assessment: {e}")
            # Fallback to conservative heuristic assessment
            basic_sufficient = len(evidence_pieces) >= max(3, self.min_evidence_threshold)
            minimum_safeguard = len(evidence_pieces) >= 2
            final_sufficient = basic_sufficient and minimum_safeguard
            
            return {
                'is_sufficient': final_sufficient,
                'llm_assessment': None,
                'heuristic_assessment': basic_sufficient,
                'safety_assessment': False,
                'evidence_count': len(evidence_pieces),
                'total_sources': total_sources,
                'minimum_evidence_safeguard': minimum_safeguard,
                'reasoning': f"Fallback assessment due to error: {str(e)}"
            }
    
    def _parse_sufficiency_response(self, response_content: str) -> bool:
        """
        Parse LLM response to determine sufficiency.
        
        Args:
            response_content: Raw LLM response
            
        Returns:
            Boolean indicating sufficiency
        """
        response_lower = response_content.lower()
        
        # Look for explicit sufficiency indicators
        sufficient_indicators = [
            'sufficient', 'adequate', 'enough', 'comprehensive',
            'complete', 'satisfactory', 'yes'
        ]
        
        insufficient_indicators = [
            'insufficient', 'inadequate', 'not enough', 'incomplete',
            'lacking', 'limited', 'no', 'more needed'
        ]
        
        # Count indicators
        sufficient_count = sum(1 for indicator in sufficient_indicators if indicator in response_lower)
        insufficient_count = sum(1 for indicator in insufficient_indicators if indicator in response_lower)
        
        # Determine sufficiency based on indicator balance
        if sufficient_count > insufficient_count:
            return True
        elif insufficient_count > sufficient_count:
            return False
        else:
            # Tie or no clear indicators - default to insufficient for safety
            return False
    
    def _create_selection_summary(
        self,
        sources_gathered: List[Dict[str, Any]],
        selected_evidence: List[str],
        judged_sources: List[Dict[str, Any]],
        sufficiency_assessment: Dict[str, Any]
    ) -> str:
        """
        Create a summary of the evidence selection process.
        
        Args:
            sources_gathered: All sources that were gathered
            selected_evidence: Selected evidence pieces
            judged_sources: Sources that were judged as high quality
            sufficiency_assessment: Sufficiency assessment results
            
        Returns:
            Formatted selection summary
        """
        # Calculate unique sources for more accurate reporting
        unique_sources = set()
        local_count = 0
        external_count = 0
        for source in sources_gathered:
            paper_info = source.get("paper_info")
            if paper_info:
                unique_id = paper_info.title or paper_info.url or str(source)
                unique_sources.add(unique_id)
                if source.get('source_type') == 'local':
                    local_count += 1
                elif source.get('source_type') == 'external':
                    external_count += 1
        
        summary_lines = [
            "🔍 EVIDENCE SELECTION COMPLETE",
            "",
            f"📊 SELECTION STATISTICS:",
            f"  • Unique Sources Evaluated: {len(unique_sources)} ({local_count} local, {external_count} external)",
            f"  • Total Raw Results (with duplicates): {len(sources_gathered)}",
            f"  • High-Quality Sources Selected: {len(judged_sources)}",
            f"  • Evidence Pieces Extracted: {len(selected_evidence)}",
            f"  • Quality Threshold: {self.quality_threshold}",
            "",
        ]
        
        # Add sufficiency assessment
        is_sufficient = sufficiency_assessment.get('is_sufficient', False)
        evidence_count = sufficiency_assessment.get('evidence_count', 0)
        
        # Get detailed assessment info
        llm_assessment = sufficiency_assessment.get('llm_assessment', False)
        heuristic_assessment = sufficiency_assessment.get('heuristic_assessment', False)
        minimum_safeguard = sufficiency_assessment.get('minimum_evidence_safeguard', False)
        progressive_sufficient = "progressive_sufficient" in str(sufficiency_assessment.get('reasoning', ''))
        
        if is_sufficient:
            summary_lines.extend([
                "✅ SUFFICIENCY ASSESSMENT: SUFFICIENT",
                f"Found {evidence_count} high-quality evidence pieces that adequately address the research question.",
                f"Assessment: LLM={llm_assessment}, Heuristic={heuristic_assessment}, MinEvidence={minimum_safeguard}",
                "",
                "🎯 EVIDENCE QUALITY BREAKDOWN:"
            ])
        else:
            insufficient_reason = ""
            if not minimum_safeguard:
                insufficient_reason = " (Need at least 1 evidence piece)"
            elif not llm_assessment:
                insufficient_reason = " (LLM assessment negative)" 
            elif not heuristic_assessment:
                insufficient_reason = " (Quality/quantity requirements not met)"
            
            summary_lines.extend([
                "⚠️ SUFFICIENCY ASSESSMENT: INSUFFICIENT", 
                f"Only {evidence_count} evidence pieces found{insufficient_reason}.",
                f"Assessment: LLM={llm_assessment}, Heuristic={heuristic_assessment}, MinEvidence={minimum_safeguard}",
                "",
                "🎯 EVIDENCE QUALITY BREAKDOWN:"
            ])
        
        # Show quality distribution
        if judged_sources:
            scores = [s.get('relevance_score', 0) for s in judged_sources]
            avg_score = sum(scores) / len(scores)
            max_score = max(scores)
            min_score = min(scores)
            
            summary_lines.extend([
                f"  • Average Relevance Score: {avg_score:.3f}",
                f"  • Score Range: {min_score:.3f} - {max_score:.3f}",
                f"  • Sources Above Threshold ({self.quality_threshold}): {len(judged_sources)}",
                ""
            ])
        
        # Add next steps
        if is_sufficient:
            summary_lines.extend([
                "🚀 NEXT STEPS:",
                "Evidence is sufficient for generating a comprehensive answer.",
                "Proceeding to answer generation with selected evidence.",
                ""
            ])
        else:
            summary_lines.extend([
                "🔄 NEXT STEPS:",
                "Evidence may be insufficient. Consider:",
                "  • Running additional search iterations",
                "  • Broadening search terms",
                "  • Lowering quality thresholds",
                "  • Or proceeding with available evidence",
                ""
            ])
        
        return "\n".join(summary_lines)
    
    def get_node_info(self) -> Dict[str, Any]:
        """Get information about this node for monitoring and debugging."""
        return {
            "node_type": "evidence_selector",
            "min_evidence_threshold": self.min_evidence_threshold,
            "max_evidence_per_query": self.max_evidence_per_query,
            "quality_threshold": self.quality_threshold,
            "model_client": str(type(self.model_client).__name__),
            "description": "Evaluates evidence quality and sufficiency for research questions"
        } 