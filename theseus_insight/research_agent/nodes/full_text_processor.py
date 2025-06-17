"""
Full Text Processor Node for Research Agent

This node extracts full text from PDF sources and creates intelligent,
research-question-focused summaries using FlatMarkdownParser for token management.
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse
import hashlib
import json

from ..state import OverallState, Message
from ..model_router import get_model_for_node
from ...pdf.processing import MarkitdownDocProcessor
from ...pdf.parsers import FlatMarkdownParser


class FullTextProcessorNode:
    """
    LangGraph node that processes full text from top-ranked PDF sources
    and creates intelligent summaries focused on the research question.
    
    Instead of truncating full text, this node:
    1. Extracts complete PDF content
    2. Uses FlatMarkdownParser for token-aware chunking
    3. Creates research-question-focused summaries using an LLM
    4. Provides detailed progress tracking
    """
    
    def __init__(
        self, 
        config: Dict[str, Any],
        top_n: int = 20,
        enable_processing: bool = True,
        max_chunk_tokens: int = 8000,
        summary_target_tokens: int = 1500
    ):
        """
        Initialize the full text processor node.
        
        Args:
            config: Configuration dictionary
            top_n: Number of top sources to process for full text
            enable_processing: Whether to enable full text processing
            max_chunk_tokens: Maximum tokens per chunk for processing
            summary_target_tokens: Target token count for each summary
        """
        self.config = config
        self.top_n = top_n
        self.enable_processing = enable_processing
        self.max_chunk_tokens = max_chunk_tokens
        self.summary_target_tokens = summary_target_tokens
        self.logger = logging.getLogger(__name__)
        self.current_task_id = None  # Will be set by workflow
        
        # Initialize MarkitdownDocProcessor with optimized settings
        self.pdf_processor = MarkitdownDocProcessor(
            export_tables=False,  # Don't need tables for text extraction
            export_figures=False,  # Don't need figures for text extraction
            save_text=False,      # We'll handle the text directly
            verbose=False,        # Reduce logging noise
            remove_md_image_tags=True  # Clean up markdown
        )
        
        # Model for summarization (will be initialized when needed)
        self._summarization_model = None
    
    def _get_summarization_model(self):
        """Get or create the summarization model."""
        if self._summarization_model is None:
            self._summarization_model = get_model_for_node("full_text_summarizer", self.config)
        return self._summarization_model
    
    def _update_progress(self, current: int, total: int, status: str, description: str = None):
        """Send progress updates to WebSocket."""
        if not self.current_task_id:
            return
            
        try:
            # Import here to avoid circular imports
            from ..workflow import ResearchAgentWorkflow
            
            # Update the task progress through the workflow's progress mechanism
            from ...api.routers.research_agent import research_tasks
            
            if self.current_task_id in research_tasks:
                research_tasks[self.current_task_id]["progress"] = {
                    "current_node": "full_text_processor",
                    "status": status,
                    "description": description or f"Processing document {current} of {total}",
                    "document_progress": f"{current}/{total}",
                    "current_document": current,
                    "total_documents": total,
                    "timestamp": datetime.utcnow().isoformat()
                }
        except Exception as e:
            self.logger.warning(f"Could not update document processing progress: {e}")
    
    def __call__(self, state: OverallState) -> Dict[str, Any]:
        """
        Execute full text processing with intelligent summarization.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with summarized full text data
        """
        if not self.enable_processing:
            self.logger.info("Full text processing disabled, skipping")
            return {
                "full_text_data": {},
                "messages": [Message(role="assistant", content="Full text processing disabled")]
            }
        
        self.logger.info("Starting intelligent full text processing with summarization")
        
        try:
            # Get research question for context
            research_question = state.get("original_question", "Research question not available")
            
            # Get judged sources from state
            judged_sources = state.get("judged_sources", [])
            if not judged_sources:
                self.logger.warning("No judged sources available for full text processing")
                return {
                    "full_text_data": {},
                    "messages": [Message(role="assistant", content="⚠️ No judged sources available for full text processing")]
                }
            
            # Sort sources by relevance score and select top N
            sorted_sources = sorted(
                judged_sources, 
                key=lambda x: x.get('relevance_score', 0), 
                reverse=True
            )
            top_sources = sorted_sources[:self.top_n]
            
            # Filter sources that have processable PDF URLs
            processable_sources = self._filter_processable_sources(top_sources)
            
            if not processable_sources:
                self.logger.warning("No processable PDF sources found")
                return {
                    "full_text_data": {},
                    "messages": [Message(role="assistant", content="⚠️ No processable PDF sources found in top results")]
                }
            
            self.logger.info(f"Processing full text for {len(processable_sources)} out of {len(top_sources)} top sources")
            
            # Process full text with progress tracking
            full_text_data = {}
            processing_messages = []
            successfully_processed = 0
            
            # Extract task_id from state if available
            self.current_task_id = state.get("task_id")
            
            for i, source in enumerate(processable_sources, 1):
                try:
                    source_id = self._generate_source_id(source)
                    paper_info = source.get('paper_info', {})
                    pdf_url = paper_info.url
                    title = paper_info.title or "Unknown Paper"
                    
                    # Send real-time progress update to WebSocket
                    self._update_progress(
                        current=i,
                        total=len(processable_sources),
                        status=f"Processing PDF {i}/{len(processable_sources)}",
                        description=f"Processing: {title[:50]}..."
                    )
                    
                    # Progress message for local tracking
                    progress_msg = f"📄 Processing PDF {i} of {len(processable_sources)}: {title[:50]}..."
                    processing_messages.append(Message(role="assistant", content=progress_msg))
                    self.logger.info(progress_msg)
                    
                    if pdf_url:
                        # Extract and summarize full text
                        summarized_text = self._process_pdf_with_summarization(
                            pdf_url, research_question, title
                        )
                        
                        if summarized_text:
                            full_text_data[source_id] = summarized_text
                            successfully_processed += 1
                            success_msg = f"✅ Completed {i}/{len(processable_sources)}: Generated targeted summary for {title[:40]}..."
                            processing_messages.append(Message(role="assistant", content=success_msg))
                            self.logger.info(f"Successfully processed and summarized: {title}")
                            
                            # Send success update to WebSocket
                            self._update_progress(
                                current=i,
                                total=len(processable_sources),
                                status=f"Completed {i}/{len(processable_sources)}",
                                description=f"Successfully processed: {title[:40]}..."
                            )
                        else:
                            error_msg = f"❌ Failed {i}/{len(processable_sources)}: Could not process {title[:40]}..."
                            processing_messages.append(Message(role="assistant", content=error_msg))
                            self.logger.warning(f"Failed to extract/summarize text from {pdf_url}")
                
                except Exception as e:
                    error_msg = f"❌ Error {i}/{len(processable_sources)}: {str(e)[:50]}..."
                    processing_messages.append(Message(role="assistant", content=error_msg))
                    self.logger.error(f"Error processing source {title}: {e}")
                    continue
            
            # Create final processing summary
            final_summary = self._create_processing_summary(
                len(judged_sources), len(top_sources), len(processable_sources), successfully_processed
            )
            processing_messages.append(Message(role="assistant", content=final_summary))
            
            self.logger.info(f"Full text processing complete: {successfully_processed} sources processed and summarized")
            
            return {
                "full_text_data": full_text_data,
                "messages": processing_messages
            }
            
        except Exception as e:
            self.logger.error(f"Error in full text processing: {e}")
            return {
                "full_text_data": {},
                "messages": [Message(role="assistant", content=f"🚨 Full text processing error: {str(e)}")]
            }
    
    def _process_pdf_with_summarization(
        self, 
        pdf_url: str, 
        research_question: str, 
        title: str
    ) -> Optional[str]:
        """
        Extract full text from PDF and create research-focused summary.
        
        Args:
            pdf_url: URL to the PDF
            research_question: The research question for context
            title: Paper title for better summarization
            
        Returns:
            Intelligent summary or None if processing failed
        """
        try:
            # Step 1: Extract full text
            self.logger.info(f"Extracting full text from: {pdf_url}")
            full_text = self._extract_full_text(pdf_url)
            
            if not full_text:
                return None
            
            # Step 2: Parse with FlatMarkdownParser for token management
            self.logger.info(f"Parsing with FlatMarkdownParser (max_tokens={self.max_chunk_tokens})")
            parser = FlatMarkdownParser(
                source=full_text,
                max_tokens=self.max_chunk_tokens,
                remove_tables=True
            )
            
            # Get chunked content
            chunks = parser.get_parsed_data(return_spans=False)
            self.logger.info(f"Parsed into {len(chunks)} chunks")
            
            # Step 3: Create intelligent summary
            summary = self._create_research_focused_summary(
                chunks, research_question, title
            )
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Error processing PDF {pdf_url}: {e}")
            return None
    
    def _create_research_focused_summary(
        self, 
        chunks: List[str], 
        research_question: str, 
        title: str
    ) -> str:
        """
        Create a research-question-focused summary from PDF chunks.
        
        Args:
            chunks: List of text chunks from FlatMarkdownParser
            research_question: The research question for focus
            title: Paper title for context
            
        Returns:
            Intelligent summary focused on the research question
        """
        try:
            model = self._get_summarization_model()
            
            # If only one chunk, summarize directly
            if len(chunks) == 1:
                return self._summarize_chunk(model, chunks[0], research_question, title)
            
            # For multiple chunks, summarize each and then create a meta-summary
            chunk_summaries = []
            for i, chunk in enumerate(chunks):
                self.logger.info(f"Summarizing chunk {i+1}/{len(chunks)}")
                chunk_summary = self._summarize_chunk(model, chunk, research_question, title, is_chunk=True)
                if chunk_summary:
                    chunk_summaries.append(chunk_summary)
            
            # Create final meta-summary
            if chunk_summaries:
                combined_summaries = "\n\n".join(chunk_summaries)
                final_summary = self._create_meta_summary(model, combined_summaries, research_question, title)
                return final_summary
            
            return ""
            
        except Exception as e:
            self.logger.error(f"Error creating research-focused summary: {e}")
            return ""
    
    def _summarize_chunk(
        self, 
        model, 
        content: str, 
        research_question: str, 
        title: str,
        is_chunk: bool = False
    ) -> str:
        """
        Summarize a single chunk of content focused on the research question.
        
        Args:
            model: The summarization model
            content: Text content to summarize
            research_question: Research question for focus
            title: Paper title for context
            is_chunk: Whether this is a chunk summary (affects prompt)
            
        Returns:
            Focused summary
        """
        chunk_type = "section" if is_chunk else "document"
        target_length = "200-300 words" if is_chunk else f"{self.summary_target_tokens//4}-{self.summary_target_tokens//3} words"
        
        prompt = f"""You are analyzing a research paper to answer the question: "{research_question}"

Paper Title: {title}

Please create a focused summary of this {chunk_type} that specifically addresses aspects relevant to the research question. 

Key Requirements:
1. Focus ONLY on content relevant to the research question
2. Extract specific findings, methodologies, results, and conclusions
3. Include concrete data, metrics, or evidence when available
4. Ignore irrelevant sections like references, acknowledgments, or unrelated content
5. Target length: {target_length}
6. Use clear, academic language
7. Structure: Key findings first, then methods/evidence, then implications

Content to analyze:
{content}

Research-focused summary:"""

        try:
            messages = [{"role": "user", "content": prompt}]
            summary = model.invoke(messages)
            return summary.strip()
        except Exception as e:
            self.logger.error(f"Error in chunk summarization: {e}")
            return ""
    
    def _create_meta_summary(
        self, 
        model, 
        chunk_summaries: str, 
        research_question: str, 
        title: str
    ) -> str:
        """
        Create a final meta-summary from chunk summaries.
        
        Args:
            model: The summarization model
            chunk_summaries: Combined chunk summaries
            research_question: Research question for focus
            title: Paper title for context
            
        Returns:
            Final comprehensive summary
        """
        prompt = f"""You are creating a final comprehensive summary from multiple section summaries of a research paper.

Research Question: "{research_question}"
Paper Title: {title}

Below are summaries from different sections of the paper. Please synthesize these into a single, coherent summary that:

1. Directly addresses the research question
2. Combines key findings from all sections
3. Highlights the paper's main contributions relevant to the research question
4. Includes specific methodologies, results, and conclusions
5. Maintains logical flow and coherence
6. Target length: {self.summary_target_tokens//3}-{self.summary_target_tokens//2} words

Section Summaries:
{chunk_summaries}

Comprehensive Research-Focused Summary:"""

        try:
            messages = [{"role": "user", "content": prompt}]
            summary = model.invoke(messages)
            return summary.strip()
        except Exception as e:
            self.logger.error(f"Error in meta-summary creation: {e}")
            return ""
    
    def _filter_processable_sources(self, sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter sources that have processable PDF URLs.
        
        Args:
            sources: List of source dictionaries
            
        Returns:
            List of sources with valid PDF URLs
        """
        processable = []
        
        for source in sources:
            paper_info = source.get('paper_info')
            if not paper_info:
                continue
            
            url = paper_info.url
            if not url:
                continue
            
            # Check if URL is likely a PDF or ArXiv URL
            if self._is_processable_url(url):
                processable.append(source)
        
        return processable
    
    def _is_processable_url(self, url: str) -> bool:
        """
        Check if a URL is processable for PDF extraction.
        
        Args:
            url: The URL to check
            
        Returns:
            True if the URL can be processed
        """
        if not url:
            return False
        
        url_lower = url.lower()
        
        # ArXiv URLs are always processable
        if 'arxiv.org' in url_lower:
            return True
        
        # Direct PDF URLs
        if url_lower.endswith('.pdf'):
            return True
        
        # Other known academic repositories
        processable_domains = [
            'arxiv.org',
            'biorxiv.org',
            'medrxiv.org',
            'psyarxiv.com'
        ]
        
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()
        
        return any(processable_domain in domain for processable_domain in processable_domains)
    
    def _generate_source_id(self, source: Dict[str, Any]) -> str:
        """
        Generate a unique source ID for tracking.
        
        Args:
            source: Source dictionary
            
        Returns:
            Unique source identifier
        """
        paper_info = source.get('paper_info', {})
        url = paper_info.url or ""
        title = paper_info.title or ""
        
        # Create hash from URL and title for unique ID
        content = f"{url}_{title}"
        return hashlib.md5(content.encode()).hexdigest()[:12]
    
    def _extract_full_text(self, pdf_url: str) -> str:
        """
        Extract full text from a PDF URL using MarkitdownDocProcessor.
        
        Args:
            pdf_url: URL to the PDF
            
        Returns:
            Extracted markdown text or empty string if failed
        """
        try:
            # Use MarkitdownDocProcessor to process the PDF directly from URL
            result = self.pdf_processor.process_document(pdf_url)
            
            # Extract the processed markdown
            full_text = result.get('processed_data', '')
            
            if full_text:
                # Clean up the text - remove excessive newlines
                full_text = self._clean_full_text(full_text)
                return full_text
            
            return ""
            
        except Exception as e:
            self.logger.error(f"Error extracting text from {pdf_url}: {e}")
            return ""
    
    def _clean_full_text(self, text: str) -> str:
        """
        Clean and normalize the extracted full text.
        
        Args:
            text: Raw extracted text
            
        Returns:
            Cleaned text
        """
        if not text:
            return ""
        
        # Remove excessive whitespace and normalize line breaks
        import re
        
        # Replace multiple spaces with single space
        text = re.sub(r' +', ' ', text)
        
        # Replace multiple newlines with double newline (paragraph break)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Remove leading/trailing whitespace
        text = text.strip()
        
        return text
    
    def _create_processing_summary(
        self,
        total_sources: int,
        top_sources: int,
        processable_sources: int,
        successfully_processed: int
    ) -> str:
        """
        Create a summary of the full text processing.
        
        Args:
            total_sources: Total number of judged sources
            top_sources: Number of top sources considered
            processable_sources: Number of sources with processable URLs
            successfully_processed: Number of sources successfully processed
            
        Returns:
            Processing summary string
        """
        return (
            f"🎯 Intelligent PDF processing complete: "
            f"Selected top {top_sources} from {total_sources} sources, "
            f"found {processable_sources} processable PDFs, "
            f"successfully created research-focused summaries for {successfully_processed} papers. "
            f"Full text summaries will significantly enhance analysis quality with targeted content."
        )
    
    def get_node_info(self) -> Dict[str, Any]:
        """Get information about this node for monitoring and debugging."""
        return {
            "node_type": "intelligent_full_text_processor",
            "top_n": self.top_n,
            "enable_processing": self.enable_processing,
            "max_chunk_tokens": self.max_chunk_tokens,
            "summary_target_tokens": self.summary_target_tokens,
            "description": "Extracts full text from PDFs and creates research-question-focused summaries"
        }


def create_full_text_processor_node(config: Dict[str, Any], **kwargs) -> FullTextProcessorNode:
    """
    Factory function to create a FullTextProcessorNode instance.
    
    Args:
        config: Configuration dictionary
        **kwargs: Additional arguments for node configuration
        
    Returns:
        Configured FullTextProcessorNode instance
    """
    return FullTextProcessorNode(config, **kwargs) 