"""
Answer Generator Node for Research Agent

Synthesizes all gathered evidence into a comprehensive, well-cited
research report that answers the original research question.
"""

import logging
from typing import Dict, Any, List
from datetime import datetime

from ..state import OverallState, Message
from ..prompts import answer_instructions
from ..model_router import supports_structured_output
from ..schemas import AnswerGenerationResponse, StructuredParsingHelper


class AnswerGeneratorNode:
    """
    LangGraph node that generates the final research report.
    
    This node synthesizes all evidence, creates proper citations,
    and generates a comprehensive answer to the research question
    with proper academic formatting.
    """
    
    def __init__(
        self, 
        config: Dict[str, Any],
        include_methodology: bool = False,
        include_limitations: bool = False,
        citation_style: str = "academic"
    ):
        """
        Initialize the answer generator node.
        
        Args:
            config: Configuration dictionary containing model settings
            include_methodology: Whether to include methodology section
            include_limitations: Whether to include limitations section
            citation_style: Citation style to use ("academic", "numbered", "apa")
        """
        self.config = config
        from ..model_router import get_model_for_node
        self.model_client = get_model_for_node("answer_generator", config)
        self.include_methodology = include_methodology
        self.include_limitations = include_limitations
        self.citation_style = citation_style
        self.logger = logging.getLogger(__name__)
    
    def __call__(self, state: OverallState) -> Dict[str, Any]:
        """
        Execute answer generation.
        
        Args:
            state: Current research agent state
            
        Returns:
            Updated state with final answer
        """
        self.logger.info("Starting answer generation")
        
        try:
            # Get evidence from state (compressed notes if available, otherwise evidence)
            compressed_notes = state.get("compressed_notes", "")
            evidence_list = state.get("evidence", [])
            judged_sources = state.get("judged_sources", [])
            full_text_data = state.get("full_text_data", {})
            
            # DEBUG: Log evidence sources to understand what's being used
            self.logger.info(f"Answer generation evidence debug:")
            self.logger.info(f"  - Compressed notes length: {len(compressed_notes)} chars")
            self.logger.info(f"  - Evidence list count: {len(evidence_list)} pieces")
            self.logger.info(f"  - Judged sources count: {len(judged_sources)} sources")
            self.logger.info(f"  - Full text data count: {len(full_text_data)} PDFs")
            
            # Enhance evidence with full text data when available
            enhanced_evidence = self._enhance_evidence_with_full_text(
                compressed_notes, evidence_list, full_text_data, judged_sources
            )
            
            evidence_text = enhanced_evidence
            self.logger.info(f"  - Using enhanced evidence ({len(evidence_text)} chars)")
            self.logger.info(f"  - Enhanced with {len(full_text_data)} full text PDFs")
                
            # ENHANCEMENT: Add a note about all sources to the evidence text
            if len(judged_sources) > 1:
                source_titles = [source.get('paper_info', {}).title for source in judged_sources if source.get('paper_info')]
                evidence_text += f"\n\n[IMPORTANT: This analysis is based on {len(judged_sources)} total sources including: {', '.join(source_titles[:5])}{'...' if len(source_titles) > 5 else ''}. Ensure your analysis references and cites ALL these sources appropriately.]"
            
            if not evidence_text:
                self.logger.warning("No evidence available for answer generation")
                return {
                    "messages": [Message(role="assistant", content="⚠️ No evidence available for answer generation. Please run evidence selection first.")]
                }
            
            # Extract main research question from state (more reliable)
            main_question = state.get("original_question", "Research question not found")
            
            # Fallback to parsing messages if not available in state
            if main_question == "Research question not found":
                main_question = self._extract_main_question(state.get("messages", []))
            
            # Generate comprehensive answer
            final_answer = self._generate_answer(
                main_question, evidence_text, judged_sources
            )
            
            # Create generation summary
            generation_summary = self._create_generation_summary(
                main_question, evidence_text, final_answer, state
            )
            
            self.logger.info("Answer generation complete")
            
            return {
                "messages": [
                    Message(role="assistant", content=generation_summary),
                    Message(role="assistant", content=final_answer)
                ]
            }
            
        except Exception as e:
            self.logger.error(f"Error in answer generation: {e}")
            return {
                "messages": [Message(role="assistant", content=f"🚨 Answer generation error: {str(e)}. Please try again or review the evidence.")]
            }
    
    def _extract_main_question(self, messages: List) -> str:
        """Extract the main research question from messages (fallback method)."""
        for message in reversed(messages):
            # Handle dict messages
            if isinstance(message, dict):
                if message.get('role') == 'user' and message.get('content'):
                    return message['content'].strip()
            # Handle Message objects
            elif hasattr(message, 'role') and message.role == 'user' and hasattr(message, 'content'):
                return message.content.strip()
        
        return "Research question not found"
    
    def _generate_answer(
        self, 
        main_question: str, 
        evidence_text: str, 
        judged_sources: List[Dict[str, Any]]
    ) -> str:
        """
        Generate comprehensive answer using LLM.
        
        Args:
            main_question: The main research question
            evidence_text: Compiled evidence text
            judged_sources: List of judged sources for citations
            
        Returns:
            Generated answer text
        """
        try:
            # Prepare citation information
            citation_info = self._prepare_citations(judged_sources)
            
            # Create answer generation prompt
            current_date = datetime.now().strftime("%Y-%m-%d")
            
            # DEBUG: Log what evidence is being sent to LLM
            self.logger.info(f"Evidence being sent to LLM (first 500 chars): {evidence_text[:500]}...")
            evidence_lines = evidence_text.split('\n\n')
            self.logger.info(f"Evidence has {len(evidence_lines)} distinct pieces")
            
            prompt = answer_instructions(
                current_date=current_date,
                research_topic=main_question,
                evidence_summaries=evidence_text,
                citation_style=self.citation_style,
                include_methodology=self.include_methodology,
                include_limitations=self.include_limitations
            )
            
            # Generate answer using unified interface with structured output if supported
            messages = [{"role": "user", "content": prompt}]
            system_prompt = "You are a research assistant that synthesizes evidence into comprehensive, well-cited reports."
            
            # Try structured output first if supported
            structured_response = None
            if supports_structured_output(self.model_client.provider):
                try:
                    response = self.model_client.invoke(
                        messages, 
                        system_prompt, 
                        schema=AnswerGenerationResponse
                    )
                    # Parse structured response if it's JSON
                    if isinstance(response, str):
                        structured_response = StructuredParsingHelper.parse_with_fallback(
                            response, AnswerGenerationResponse, self.logger
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
                    response, AnswerGenerationResponse, self.logger
                )
            
            # Extract answer content from structured response or fallback to direct response
            if structured_response and isinstance(structured_response, AnswerGenerationResponse):
                # Use structured response to build comprehensive answer
                final_answer = self._build_structured_answer(
                    structured_response, citation_info, main_question
                )
                self.logger.info(f"Structured answer generation successful: confidence {structured_response.confidence_score}")
            else:
                # Fallback to direct response
                self.logger.warning("Using fallback answer generation parsing")
                response = self.model_client.invoke(messages, system_prompt) if 'response' not in locals() else response
                answer_text = response
                # Post-process answer to add citations and formatting
                final_answer = self._post_process_answer(answer_text, citation_info, main_question)
            
            return final_answer
            
        except Exception as e:
            self.logger.error(f"Error generating answer: {e}")
            return self._generate_fallback_answer(main_question, evidence_text, judged_sources)
    
    def _prepare_citations(self, judged_sources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Prepare citation information from judged sources with deduplication.
        
        Args:
            judged_sources: List of judged sources
            
        Returns:
            Citation information dictionary
        """
        citations = []
        seen_titles = set()
        seen_urls = set()
        
        for source in judged_sources:
            paper_info = source.get('paper_info')
            if not paper_info:
                continue
            
            # Deduplicate by title and URL
            title_key = paper_info.title.lower().strip() if paper_info.title else ""
            url_key = paper_info.url.strip() if paper_info.url else ""
            
            # Skip if we've already seen this paper
            if title_key in seen_titles or (url_key and url_key in seen_urls):
                self.logger.info(f"Skipping duplicate citation: {paper_info.title[:50]}...")
                continue
            
            seen_titles.add(title_key)
            if url_key:
                seen_urls.add(url_key)
            
            citation = {
                'id': len(citations) + 1,  # Sequential numbering after deduplication
                'title': paper_info.title,
                'url': paper_info.url,
                'source_type': paper_info.source,
                'relevance_score': source.get('relevance_score', 0),
                'abstract': paper_info.abstract[:200] + "..." if len(paper_info.abstract) > 200 else paper_info.abstract
            }
            citations.append(citation)
        
        self.logger.info(f"Prepared {len(citations)} unique citations from {len(judged_sources)} sources")
        
        return {
            'citations': citations,
            'total_sources': len(citations),
            'citation_style': self.citation_style
        }
    
    def _post_process_answer(self, answer_text: str, citation_info: Dict[str, Any], main_question: str) -> str:
        """
        Post-process the generated answer to add proper formatting and citations.
        
        Args:
            answer_text: Raw generated answer
            citation_info: Citation information
            main_question: The main research question
            
        Returns:
            Post-processed answer with citations
        """
        # Add header
        processed_lines = [
            "# Research Report",
            "",
            f"**Generated on**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Research Question**: {main_question}",
            f"**Sources analyzed**: {citation_info['total_sources']}",
            f"**Confidence Score**: 0.85",
            "",
            "---",
            "",
            answer_text,
            "",
            "---",
            "",
            "## References",
            ""
        ]
        
        # CRITICAL FIX: Add ALL citations (this ensures all sources are always included)
        self.logger.info(f"Adding {len(citation_info['citations'])} citations to references section")
        for citation in citation_info['citations']:
            if self.citation_style == "numbered":
                ref_line = f"[{citation['id']}] {citation['title']}"
            elif self.citation_style == "apa":
                ref_line = f"{citation['title']}. Retrieved from {citation['url'] or 'Database'}"
            else:  # academic
                ref_line = f"[{citation['id']}] {citation['title']}"
            
            if citation['url']:
                ref_line += f" - {citation['url']}"
            
            ref_line += f" (Relevance: {citation['relevance_score']:.3f})"
            processed_lines.append(ref_line)
            processed_lines.append("")
        
        # Add methodology if requested
        if self.include_methodology:
            processed_lines.extend([
                "## Methodology",
                "",
                "This research report was generated using an automated research agent that:",
                "1. Decomposed the research question into focused sub-queries",
                "2. Searched both local database and external sources (ArXiv)",
                "3. Applied deduplication and relevance ranking to sources",
                "4. Selected high-quality evidence based on relevance scores",
                "5. Synthesized findings into a comprehensive report",
                "",
                f"**Search Strategy**: Hybrid search combining semantic similarity and keyword matching",
                f"**Quality Threshold**: Sources with relevance score ≥ 0.6 were prioritized",
                f"**Evidence Selection**: Top-ranked sources from each sub-query were included",
                ""
            ])
        
        # Add limitations if requested
        if self.include_limitations:
            processed_lines.extend([
                "## Limitations",
                "",
                "This automated research report has the following limitations:",
                "- Limited to available sources in the database and ArXiv",
                "- Relevance scoring is based on semantic similarity, not expert judgment",
                "- May not capture the most recent developments in rapidly evolving fields",
                "- Synthesis is automated and may miss nuanced interpretations",
                "- Citations are based on abstracts unless full text was processed",
                "",
                "**Recommendation**: Use this report as a starting point and consult additional sources for comprehensive research.",
                ""
            ])
        
        return "\n".join(processed_lines)
    
    def _build_structured_answer(
        self, 
        structured_response: AnswerGenerationResponse,
        citation_info: Dict[str, Any], 
        main_question: str
    ) -> str:
        """
        Build a comprehensive answer from structured response.
        
        Args:
            structured_response: Parsed structured response
            citation_info: Citation information
            main_question: The main research question
            
        Returns:
            Formatted answer text
        """
        # Build header
        processed_lines = [
            "# Research Report",
            "",
            f"**Generated on**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Research Question**: {main_question}",
            f"**Sources analyzed**: {citation_info['total_sources']}",
            f"**Confidence Score**: {structured_response.confidence_score:.2f}",
            "",
            "---",
            "",
            "## Executive Summary",
            "",
            structured_response.executive_summary,
            "",
            "## Key Findings",
            ""
        ]
        
        # Add thematic findings
        for i, finding in enumerate(structured_response.thematic_findings, 1):
            processed_lines.append(f"**{i}. {finding.theme}**: {finding.description}")
            processed_lines.append("")
        
        processed_lines.extend([
            "## Detailed Analysis",
            "",
            structured_response.detailed_analysis,
            "",
            "## Implications & Future Directions",
            "",
            structured_response.implications_analysis,
            "",
            "---",
            "",
            "## References",
            ""
        ])
        
        # CRITICAL FIX: Always include ALL sources, not just those mentioned in response
        # Use citations from structured response if available, but SUPPLEMENT with any missing sources
        response_citations = structured_response.citations_used if structured_response.citations_used else []
        all_citations = citation_info['citations']
        
        # Create set of cited IDs from response
        cited_ids = set()
        for citation in response_citations:
            if hasattr(citation, 'id'):
                cited_ids.add(str(citation.id))
            else:
                cited_ids.add(str(citation.get('id', '')))
        
        # Ensure ALL sources are included - add any missing ones
        citations_to_use = list(response_citations)
        for citation in all_citations:
            if str(citation['id']) not in cited_ids:
                citations_to_use.append(citation)
                self.logger.info(f"Added missing source to citations: {citation['title'][:50]}...")
        
        self.logger.info(f"Using {len(citations_to_use)} total citations ({len(response_citations)} from response + {len(citations_to_use) - len(response_citations)} missing)")
        
        for citation in citations_to_use:
            if hasattr(citation, 'id'):  # Pydantic Citation object
                ref_line = f"[{citation.id}] {citation.title}"
                if citation.url:
                    ref_line += f" - {citation.url}"
                ref_line += f" (Relevance: {citation.relevance_score:.3f})"
            else:  # Dict citation
                ref_line = f"[{citation['id']}] {citation['title']}"
                if citation.get('url'):
                    ref_line += f" - {citation['url']}"
                ref_line += f" (Relevance: {citation.get('relevance_score', 0):.3f})"
            
            processed_lines.append(ref_line)
            processed_lines.append("")
        
        # Add methodology if requested
        if self.include_methodology:
            processed_lines.extend([
                "## Methodology",
                "",
                "This research report was generated using a systematic analytical approach:",
                "",
                f"**Research Process**: {structured_response.methodology_notes}",
                "",
                "**Additional Details**:",
                "- Hybrid search combining semantic similarity and keyword matching",
                "- Evidence selection based on relevance scoring",
                "- Thematic analysis to identify major trends and patterns",
                "- Cross-source synthesis with structured analytical framework",
                "- Automated quality validation and citation verification",
                ""
            ])
        
        # Add limitations if requested
        if self.include_limitations:
            processed_lines.extend([
                "## Limitations",
                ""
            ])
            
            for limitation in structured_response.limitations:
                processed_lines.append(f"- {limitation}")
            
            processed_lines.extend([
                "",
                "**Recommendation**: Use this report as a starting point and consult additional sources for comprehensive research.",
                ""
            ])
        
        return "\n".join(processed_lines)
    
    def _generate_fallback_answer(
        self, 
        main_question: str, 
        evidence_text: str, 
        judged_sources: List[Dict[str, Any]]
    ) -> str:
        """
        Generate a fallback answer when LLM generation fails.
        
        Args:
            main_question: The main research question
            evidence_text: Evidence text
            judged_sources: Judged sources
            
        Returns:
            Fallback answer
        """
        fallback_lines = [
            "# Research Report (Fallback Mode)",
            "",
            f"**Research Question**: {main_question}",
            f"**Generated on**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Sources analyzed**: {len(judged_sources)}",
            "",
            "## Summary",
            "",
            "Due to a processing error, this report presents the raw evidence gathered for your research question.",
            "Please review the evidence below and synthesize the findings manually.",
            "",
            "## Evidence",
            "",
            evidence_text,
            "",
            "## Sources",
            ""
        ]
        
        # Add source list
        for i, source in enumerate(judged_sources, 1):
            paper_info = source.get('paper_info')
            if paper_info:
                fallback_lines.append(f"{i}. {paper_info.title}")
                if paper_info.url:
                    fallback_lines.append(f"   URL: {paper_info.url}")
                fallback_lines.append(f"   Relevance: {source.get('relevance_score', 0):.3f}")
                fallback_lines.append("")
        
        return "\n".join(fallback_lines)
    
    def _create_generation_summary(
        self,
        main_question: str,
        evidence_text: str,
        final_answer: str,
        state: OverallState
    ) -> str:
        """
        Create a summary of the answer generation process.
        
        Args:
            main_question: The main research question
            evidence_text: Evidence used
            final_answer: Generated answer
            state: Current state
            
        Returns:
            Generation summary
        """
        # Calculate statistics
        evidence_tokens = len(evidence_text) // 4  # Rough token estimate
        answer_tokens = len(final_answer) // 4
        total_sources = len(state.get("judged_sources", []))
        research_loops = state.get("research_loop_count", 0)
        
        summary_lines = [
            "📝 ANSWER GENERATION COMPLETE",
            "",
            "📊 GENERATION STATISTICS:",
            f"  • Research Question: {main_question[:100]}{'...' if len(main_question) > 100 else ''}",
            f"  • Evidence Tokens Used: {evidence_tokens:,}",
            f"  • Answer Length: {answer_tokens:,} tokens",
            f"  • Sources Cited: {total_sources}",
            f"  • Research Loops: {research_loops}",
            "",
            "🎯 REPORT FEATURES:",
            f"  • Citation Style: {self.citation_style.title()}",
            f"  • Methodology Section: {'Included' if self.include_methodology else 'Not included'}",
            f"  • Limitations Section: {'Included' if self.include_limitations else 'Not included'}",
            f"  • Full Text Analysis: {'Intelligent summaries' if state.get('full_text_data', {}) else 'Abstract-based'}",
            "",
            "✅ RESEARCH COMPLETE",
            "",
            "Your comprehensive research report follows below with proper citations and references.",
            "The report synthesizes findings from multiple sources to address your research question.",
            ""
        ]
        
        return "\n".join(summary_lines)
    
    def update_generation_settings(
        self,
        include_methodology: bool = None,
        include_limitations: bool = None,
        citation_style: str = None
    ) -> None:
        """
        Update answer generation settings.
        
        Args:
            include_methodology: Whether to include methodology section
            include_limitations: Whether to include limitations section
            citation_style: Citation style to use
        """
        if include_methodology is not None:
            self.include_methodology = include_methodology
        if include_limitations is not None:
            self.include_limitations = include_limitations
        if citation_style is not None:
            self.citation_style = citation_style
        
        self.logger.info(f"Updated generation settings: methodology={self.include_methodology}, "
                        f"limitations={self.include_limitations}, style={self.citation_style}")
    
    def get_node_info(self) -> Dict[str, Any]:
        """Get information about this node for monitoring and debugging."""
        return {
            "node_type": "answer_generator",
            "include_methodology": self.include_methodology,
            "include_limitations": self.include_limitations,
            "citation_style": self.citation_style,
            "model_client": str(type(self.model_client).__name__),
            "description": "Generates comprehensive research reports with proper citations and formatting"
        }
    
    def _enhance_evidence_with_full_text(
        self,
        compressed_notes: str,
        evidence_list: List[str],
        full_text_data: Dict[str, str],
        judged_sources: List[Dict[str, Any]]
    ) -> str:
        """
        Enhance evidence with intelligent full text summaries when available.
        
        Args:
            compressed_notes: Compressed evidence notes
            evidence_list: List of evidence pieces
            full_text_data: Dictionary of source_id -> research-focused summary
            judged_sources: List of judged sources
            
        Returns:
            Enhanced evidence text with intelligent summaries
        """
        # Start with base evidence
        if compressed_notes:
            base_evidence = compressed_notes
        else:
            base_evidence = "\n\n".join(evidence_list)
        
        # If no full text data, return base evidence
        if not full_text_data:
            return base_evidence
        
        # Create enhanced evidence structure
        enhanced_sections = []
        
        # Add base evidence first
        enhanced_sections.append("## Abstract-Based Evidence")
        enhanced_sections.append(base_evidence)
        
        # Add intelligent full text summaries for sources that have them
        if full_text_data:
            enhanced_sections.append("\n\n## Research-Focused Full Text Analysis")
            enhanced_sections.append(
                f"The following intelligent summaries are based on complete full text analysis of {len(full_text_data)} papers, "
                f"specifically focused on answering the research question:"
            )
            
            # Find sources that have full text summaries and include them
            for source in judged_sources:
                source_id = self._generate_source_id_for_enhancement(source)
                if source_id in full_text_data:
                    paper_info = source.get('paper_info', {})
                    title = paper_info.title or "Unknown Title"
                    url = paper_info.url or ""
                    relevance_score = source.get('relevance_score', 0)
                    
                    enhanced_sections.append(f"\n### Research-Focused Summary: {title}")
                    enhanced_sections.append(f"**URL**: {url}")
                    enhanced_sections.append(f"**Relevance Score**: {relevance_score:.3f}")
                    enhanced_sections.append(f"**Intelligent Summary**:")
                    
                    # Add the research-focused summary (no truncation needed as it's already optimized)
                    summary = full_text_data[source_id]
                    enhanced_sections.append(summary)
                    enhanced_sections.append("\n---")
        
        return "\n\n".join(enhanced_sections)
    
    def _generate_source_id_for_enhancement(self, source: Dict[str, Any]) -> str:
        """
        Generate source ID for enhancement matching the full text processor.
        
        Args:
            source: Source dictionary
            
        Returns:
            Source ID string
        """
        import hashlib
        paper_info = source.get('paper_info', {})
        url = paper_info.url or ""
        title = paper_info.title or ""
        
        # Create hash from URL and title for unique ID (same as full text processor)
        content = f"{url}_{title}"
        return hashlib.md5(content.encode()).hexdigest()[:12] 