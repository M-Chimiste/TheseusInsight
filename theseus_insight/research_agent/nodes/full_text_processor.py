"""
Full Text Processor Node for Research Agent

This node extracts full text from PDF sources using SpacyLayoutDocProcessor
for the top-ranked sources to enhance the evidence base with complete content.
"""

import logging
from typing import Dict, Any, List
from urllib.parse import urlparse
import hashlib

from ..state import OverallState, Message
from ...pdf.processing import SpacyLayoutDocProcessor


class FullTextProcessorNode:
    """
    LangGraph node that processes full text from top-ranked PDF sources.
    
    This node takes the judged sources, identifies the top N papers with 
    accessible PDF URLs, and extracts full text using SpacyLayoutDocProcessor.
    """
    
    def __init__(
        self, 
        config: Dict[str, Any],
        top_n: int = 20,
        enable_processing: bool = True
    ):
        """
        Initialize the full text processor node.
        
        Args:
            config: Configuration dictionary
            top_n: Number of top sources to process for full text
            enable_processing: Whether to enable full text processing
        """
        self.config = config
        self.top_n = top_n
        self.enable_processing = enable_processing
        self.logger = logging.getLogger(__name__)
        
        # Initialize SpacyLayoutDocProcessor with optimized settings
        self.pdf_processor = SpacyLayoutDocProcessor(
            export_tables=False,  # Don't need tables for text extraction
            export_figures=False,  # Don't need figures for text extraction
            save_text=False,      # We'll handle the text directly
            verbose=False,        # Reduce logging noise
            remove_md_image_tags=True  # Clean up markdown
        )
    
    def __call__(self, state: OverallState) -> Dict[str, Any]:
        """
        Execute full text processing for top sources.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with full text data
        """
        if not self.enable_processing:
            self.logger.info("Full text processing disabled, skipping")
            return {
                "full_text_data": {},
                "messages": [Message(role="assistant", content="Full text processing disabled")]
            }
        
        self.logger.info("Starting full text processing")
        
        try:
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
            
            self.logger.info(f"Processing full text for {len(processable_sources)} out of {len(top_sources)} top sources")
            
            # Process full text for each source
            full_text_data = {}
            successfully_processed = 0
            
            for source in processable_sources:
                try:
                    source_id = self._generate_source_id(source)
                    pdf_url = source.get('paper_info', {}).url
                    
                    if pdf_url:
                        self.logger.info(f"Processing PDF: {pdf_url}")
                        full_text = self._extract_full_text(pdf_url)
                        
                        if full_text:
                            full_text_data[source_id] = full_text
                            successfully_processed += 1
                            self.logger.info(f"Successfully processed {source.get('paper_info', {}).title[:50]}...")
                        else:
                            self.logger.warning(f"Failed to extract text from {pdf_url}")
                
                except Exception as e:
                    self.logger.error(f"Error processing source {source.get('paper_info', {}).title}: {e}")
                    continue
            
            # Create processing summary
            processing_summary = self._create_processing_summary(
                len(judged_sources), len(top_sources), len(processable_sources), successfully_processed
            )
            
            self.logger.info(f"Full text processing complete: {successfully_processed} sources processed")
            
            return {
                "full_text_data": full_text_data,
                "messages": [Message(role="assistant", content=processing_summary)]
            }
            
        except Exception as e:
            self.logger.error(f"Error in full text processing: {e}")
            return {
                "full_text_data": {},
                "messages": [Message(role="assistant", content=f"🚨 Full text processing error: {str(e)}")]
            }
    
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
        Extract full text from a PDF URL using SpacyLayoutDocProcessor.
        
        Args:
            pdf_url: URL to the PDF
            
        Returns:
            Extracted markdown text or empty string if failed
        """
        try:
            # Use SpacyLayoutDocProcessor to process the PDF directly from URL
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
            f"📄 Full text processing complete: "
            f"Selected top {top_sources} from {total_sources} sources, "
            f"found {processable_sources} processable PDFs, "
            f"successfully extracted full text from {successfully_processed} papers. "
            f"Full text data will enhance the analysis quality."
        )
    
    def get_node_info(self) -> Dict[str, Any]:
        """Get information about this node for monitoring and debugging."""
        return {
            "node_type": "full_text_processor",
            "top_n": self.top_n,
            "enable_processing": self.enable_processing,
            "description": "Extracts full text from top-ranked PDF sources for enhanced analysis"
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