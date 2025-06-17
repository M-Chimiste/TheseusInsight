import json
import os
import tempfile
import requests
from pathlib import Path
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod

from ...data_model.data_handling import PaperDatabase
from ...inference import SentenceTransformerInference
from ...pdf.processing import MarkitdownDocProcessor
from ...pdf.parsers import FlatMarkdownParser


class BaseSearchTool(ABC):
    """Abstract base class for search tools following the PRD interface."""
    
    @abstractmethod
    def find_papers_by_str(self, query: str, limit: int = 10) -> str:
        """Find papers by search string and return formatted results."""
        pass
    
    @abstractmethod
    def retrieve_full_text(self, paper_id: str) -> str:
        """Retrieve full text of a paper by ID."""
        pass


class LocalSearchTool(BaseSearchTool):
    """
    Enhanced local-first search tool with hybrid search and PDF processing.
    
    Features:
    - Hybrid search combining BM25 (keyword) + vector similarity
    - Lazy embedding computation and caching
    - Automatic PDF download and processing
    - Full text extraction and storage for papers
    - Configurable search parameters
    - Enhanced result formatting for LangGraph integration
    - Batch processing for improved performance
    """
    
    def __init__(
        self,
        db: PaperDatabase,
        embedding_model: SentenceTransformerInference,
        semantic_weight: float = 0.5,
        keyword_weight: float = 0.5,
        similarity_threshold: float = 0.3,
        enable_pdf_download: bool = True
    ):
        """
        Initialize LocalSearchTool.
        
        Args:
            db: PaperDatabase instance for data access
            embedding_model: SentenceTransformerInference instance for embeddings
            semantic_weight: Weight for semantic similarity (default 0.5)
            keyword_weight: Weight for keyword/BM25 similarity (default 0.5)
            similarity_threshold: Minimum similarity threshold (default 0.3)
            enable_pdf_download: Enable automatic PDF download and processing (default True)
        """
        self.db = db
        self.embedding_model = embedding_model
        self.semantic_weight = semantic_weight
        self.keyword_weight = keyword_weight
        self.similarity_threshold = similarity_threshold
        self.enable_pdf_download = enable_pdf_download
        
        # Initialize PDF processor if available
        self.pdf_processor = None
        self._init_pdf_processor()
    
    def _init_pdf_processor(self):
        """Initialize PDF processor if dependencies are available."""
        try:
            from ...pdf.processing import MarkitdownDocProcessor
            self.pdf_processor = MarkitdownDocProcessor(
                save_text=False,
                export_tables=False,
                export_figures=False,
                remove_md_image_tags=True
            )
        except ImportError:
            print("Warning: PDF processing dependencies not available. PDF download will be disabled.")
            self.enable_pdf_download = False
    
    def find_papers_by_str(self, query: str, limit: int = 10) -> str:
        """
        Find papers by search query using hybrid search.
        
        Args:
            query: Search query string
            limit: Maximum number of results to return
            
        Returns:
            Formatted string with paper results optimized for LangGraph agent consumption
        """
        try:
            # Ensure embeddings are computed for better search results
            self._ensure_recent_embeddings()
            
            # Use the existing hybrid search from data_handling
            results = self.db.hybrid_search_papers(
                query_text=query,
                embedding_model=self.embedding_model,
                page=1,
                page_size=limit,
                semantic_weight=self.semantic_weight,
                keyword_weight=self.keyword_weight,
                similarity_threshold=self.similarity_threshold
            )
            
            papers = results.get('items', [])
            if not papers:
                return f"No papers found for query: '{query}' in local database."
            
            # Enhanced formatting for agent consumption
            formatted_papers = []
            for i, paper in enumerate(papers, 1):
                # Enhanced paper information with better structure
                paper_info = [
                    f"PAPER {i}:",
                    f"  ID: {paper['id']}",
                    f"  Title: {paper['title']}",
                    f"  Date: {paper['date']}",
                    f"  Relevance: {paper.get('hybrid_score', 0):.3f}",
                    f"    (Semantic: {paper.get('semantic_score', 0):.3f}, Keyword: {paper.get('keyword_score', 0):.3f})"
                ]
                
                # Add URL if available
                if paper.get('url'):
                    paper_info.append(f"  URL: {paper['url']}")
                
                # Add abstract with smart truncation
                abstract = paper.get('abstract', '')
                if abstract:
                    if len(abstract) > 250:
                        # Find a good break point near 250 characters
                        truncated = abstract[:250]
                        last_sentence = truncated.rfind('.')
                        if last_sentence > 200:  # If we found a sentence end reasonably close
                            abstract_preview = abstract[:last_sentence + 1] + "..."
                        else:
                            abstract_preview = truncated + "..."
                    else:
                        abstract_preview = abstract
                    
                    paper_info.append(f"  Abstract: {abstract_preview}")
                
                # Add availability status with enhanced logging
                has_full_text = bool(paper.get('text'))
                has_url = bool(paper.get('url'))
                availability = []
                
                if has_full_text:
                    availability.append("full-text")
                    print(f"DEBUG: Paper {paper['id']} has full text ({len(paper.get('text', ''))} chars)")
                else:
                    print(f"DEBUG: Paper {paper['id']} has NO full text, only abstract ({len(paper.get('abstract', ''))} chars)")
                    
                if has_url:
                    availability.append("PDF-available" if self.enable_pdf_download else "URL-only")
                    
                if availability:
                    paper_info.append(f"  Content: {', '.join(availability)}")
                    
                # Add a note about how to access full text for this paper
                if not has_full_text and has_url and self.enable_pdf_download:
                    paper_info.append(f"  Note: Use retrieve_full_text({paper['id']}) to download and process PDF")
                
                formatted_papers.append('\n'.join(paper_info))
            
            # Create comprehensive result summary
            result_lines = [
                f"LOCAL SEARCH RESULTS for '{query}':",
                f"Found {len(papers)} relevant papers (showing top {limit}):",
                "",
                *formatted_papers,
                "",
                f"Search completed with {self.semantic_weight:.1f} semantic + {self.keyword_weight:.1f} keyword weighting",
                f"Minimum relevance threshold: {self.similarity_threshold}"
            ]
            
            return '\n'.join(result_lines)
            
        except Exception as e:
            return f"Error searching local papers for '{query}': {str(e)}"
    
    def retrieve_full_text(self, paper_id: str) -> str:
        """
        Retrieve full text content of a paper by ID with enhanced processing.
        
        Args:
            paper_id: String representation of paper ID
            
        Returns:
            Full text content or error message
        """
        try:
            # Convert string ID to integer
            paper_id_int = int(paper_id)
            
            # Get paper details
            paper = self.db.get_paper_by_id(paper_id_int)
            if not paper:
                return f"Paper with ID {paper_id} not found in local database."
            
            # Check if full text is already available
            full_text = paper.get('text')
            if full_text:
                return self._format_full_text_response(paper, full_text, "cached")
            
            # If no full text and PDF download is enabled, try to download and process
            if self.enable_pdf_download and paper.get('url') and self.pdf_processor:
                return self._download_and_process_pdf(paper_id_int, paper)
            else:
                return self._format_unavailable_response(paper)
                
        except ValueError:
            return f"Invalid paper ID format: '{paper_id}'. Expected integer."
        except Exception as e:
            return f"Error retrieving paper {paper_id}: {str(e)}"
    
    def _format_full_text_response(self, paper: Dict[str, Any], full_text: str, source: str) -> str:
        """Format a full text response with metadata."""
        return (
            f"FULL TEXT RETRIEVED (Paper ID: {paper['id']}, Source: {source}):\n"
            f"Title: {paper['title']}\n"
            f"Date: {paper['date']}\n"
            f"URL: {paper.get('url', 'N/A')}\n"
            f"Content length: {len(full_text)} characters\n"
            f"{'-' * 50}\n\n"
            f"{full_text}"
        )
    
    def _format_unavailable_response(self, paper: Dict[str, Any]) -> str:
        """Format response when full text is not available."""
        reasons = []
        if not self.enable_pdf_download:
            reasons.append("PDF download disabled")
        if not paper.get('url'):
            reasons.append("no URL available")
        if not self.pdf_processor:
            reasons.append("PDF processor unavailable")
        
        reason_text = " (" + ", ".join(reasons) + ")" if reasons else ""
        
        return (
            f"FULL TEXT NOT AVAILABLE for Paper ID {paper['id']}{reason_text}:\n"
            f"Title: {paper['title']}\n"
            f"Date: {paper['date']}\n"
            f"URL: {paper.get('url', 'N/A')}\n"
            f"Abstract: {paper.get('abstract', 'N/A')}\n\n"
            f"Note: Only abstract and metadata are available for this paper."
        )
    
    def get_papers_without_embeddings(self) -> List[Dict[str, Any]]:
        """Get papers that don't have embeddings computed yet."""
        return self.db.get_papers_without_embeddings()
    
    def compute_and_cache_embedding(self, paper_id: int, text: str) -> None:
        """
        Compute and cache embedding for a paper.
        
        Args:
            paper_id: ID of the paper
            text: Text to embed (usually abstract)
        """
        try:
            embedding = self.embedding_model.invoke(text)
            self.db.update_paper_embedding(paper_id, embedding.tolist())
        except Exception as e:
            print(f"Warning: Error computing embedding for paper {paper_id}: {e}")
    
    def ensure_embeddings_computed(self) -> None:
        """Ensure all papers have embeddings computed (lazy caching)."""
        papers_without_embeddings = self.get_papers_without_embeddings()
        
        if not papers_without_embeddings:
            return
        
        print(f"Computing embeddings for {len(papers_without_embeddings)} papers...")
        
        for paper in papers_without_embeddings:
            # Use abstract for embedding if no full text available
            text_to_embed = paper.get('text') or paper.get('abstract', '')
            if text_to_embed:
                self.compute_and_cache_embedding(paper['id'], text_to_embed)
    
    def _ensure_recent_embeddings(self) -> None:
        """Ensure embeddings are computed for papers without them (limited batch)."""
        papers_without_embeddings = self.get_papers_without_embeddings()
        
        # Process a limited batch to avoid long delays
        batch_size = min(10, len(papers_without_embeddings))
        if batch_size > 0:
            print(f"Computing embeddings for {batch_size} papers...")
            for paper in papers_without_embeddings[:batch_size]:
                text_to_embed = paper.get('text') or paper.get('abstract', '')
                if text_to_embed:
                    self.compute_and_cache_embedding(paper['id'], text_to_embed)
    
    def search_local_only(
        self, 
        query: str, 
        limit: int = 10,
        min_similarity: float = None
    ) -> List[Dict[str, Any]]:
        """
        Search only in local database, returning raw results.
        
        Args:
            query: Search query
            limit: Max results
            min_similarity: Override similarity threshold
            
        Returns:
            List of paper dictionaries
        """
        threshold = min_similarity or self.similarity_threshold
        
        results = self.db.hybrid_search_papers(
            query_text=query,
            embedding_model=self.embedding_model,
            page=1,
            page_size=limit,
            semantic_weight=self.semantic_weight,
            keyword_weight=self.keyword_weight,
            similarity_threshold=threshold
        )
        
        return results.get('items', [])
    
    def _download_and_process_pdf(self, paper_id: int, paper: Dict[str, Any]) -> str:
        """
        Download and process a PDF from the paper's URL with enhanced error handling.
        
        Args:
            paper_id: ID of the paper
            paper: Paper dictionary with metadata
            
        Returns:
            Full text content or error message
        """
        url = paper['url']
        
        try:
            # Create a temporary file for the PDF
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
                temp_pdf_path = temp_file.name
                
                # Download the PDF with progress indication
                print(f"Downloading PDF for paper {paper_id} from {url}...")
                response = requests.get(url, timeout=60, stream=True)
                response.raise_for_status()
                
                # Write content in chunks
                for chunk in response.iter_content(chunk_size=8192):
                    temp_file.write(chunk)
            
            try:
                # Process the PDF using MarkitdownDocProcessor
                print(f"Processing PDF content for paper {paper_id}...")
                
                # Suppress torch warnings during PDF processing
                import warnings
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", category=UserWarning, module="torch")
                    result = self.pdf_processor.process_document(temp_pdf_path)
                    
                markdown_text = result.get('processed_data', '')
                
                if not markdown_text:
                    return (
                        f"FAILED TO EXTRACT TEXT from PDF for Paper ID {paper_id}:\n"
                        f"Title: {paper['title']}\n"
                        f"URL: {url}\n"
                        f"Error: PDF processing returned empty content\n\n"
                        f"Available metadata:\n"
                        f"Abstract: {paper.get('abstract', 'N/A')}"
                    )
                
                # Parse the markdown using FlatMarkdownParser
                try:
                    from ...pdf.parsers import FlatMarkdownParser
                    parser = FlatMarkdownParser(markdown_text, max_tokens=60000)
                    parsed_chunks = parser.get_parsed_data()
                    full_text = '\n'.join(parsed_chunks)
                except ImportError:
                    # Fallback to raw markdown if parser not available
                    full_text = markdown_text
                
                # Store the full text in the database
                self.db.update_paper_text(paper_id, full_text)
                
                return self._format_full_text_response(paper, full_text, "downloaded")
                
            finally:
                # Clean up the temporary file
                if os.path.exists(temp_pdf_path):
                    os.unlink(temp_pdf_path)
                    
        except requests.RequestException as e:
            return (
                f"FAILED TO DOWNLOAD PDF for Paper ID {paper_id}:\n"
                f"Title: {paper['title']}\n"
                f"URL: {url}\n"
                f"Network Error: {str(e)}\n\n"
                f"Available metadata:\n"
                f"Abstract: {paper.get('abstract', 'N/A')}"
            )
        except Exception as e:
            return (
                f"ERROR PROCESSING PDF for Paper ID {paper_id}:\n"
                f"Title: {paper['title']}\n"
                f"URL: {url}\n"
                f"Processing Error: {str(e)}\n\n"
                f"Available metadata:\n"
                f"Abstract: {paper.get('abstract', 'N/A')}"
            )
    
    def add_paper_from_url(self, url: str, paper_metadata: Dict[str, Any] = None) -> str:
        """
        Add a new paper from a URL by downloading and processing the PDF.
        
        Args:
            url: URL to the PDF
            paper_metadata: Optional metadata dictionary with title, abstract, etc.
            
        Returns:
            Status message about the operation
        """
        try:
            # Check if paper already exists
            existing_paper = self.db.get_paper_by_url(url)
            if existing_paper:
                return f"Paper already exists with ID {existing_paper['id']}: {existing_paper['title']}"
            
            # If no metadata provided, we need at least basic info
            if not paper_metadata:
                return f"Cannot add paper without metadata. URL: {url}"
            
            if not self.pdf_processor:
                return f"Cannot add paper: PDF processing not available. URL: {url}"
            
            # Create a temporary file for the PDF
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
                temp_pdf_path = temp_file.name
                
                # Download the PDF
                print(f"Downloading PDF from {url}...")
                response = requests.get(url, timeout=60)
                response.raise_for_status()
                
                temp_file.write(response.content)
            
            try:
                # Process the PDF
                print(f"Processing PDF from {url}...")
                result = self.pdf_processor.process_document(temp_pdf_path)
                markdown_text = result.get('processed_data', '')
                
                # Parse the markdown
                full_text = None
                if markdown_text:
                    try:
                        from ...pdf.parsers import FlatMarkdownParser
                        parser = FlatMarkdownParser(markdown_text, max_tokens=60000)
                        parsed_chunks = parser.get_parsed_data()
                        full_text = '\n'.join(parsed_chunks)
                    except ImportError:
                        full_text = markdown_text
                
                # Create paper object with the extracted text
                from ...data_model.papers import Paper
                import datetime
                
                paper = Paper(
                    title=paper_metadata.get('title', 'Unknown Title'),
                    abstract=paper_metadata.get('abstract', ''),
                    date=paper_metadata.get('date', datetime.date.today().strftime('%Y-%m-%d')),
                    date_run=datetime.date.today().strftime('%Y-%m-%d'),
                    score=paper_metadata.get('score', 0.0),
                    rationale=paper_metadata.get('rationale', ''),
                    related=paper_metadata.get('related', False),
                    cosine_similarity=paper_metadata.get('cosine_similarity', 0.0),
                    url=url,
                    embedding_model=self.embedding_model.model_name,
                    embedding=None,  # Will be computed later
                    text=full_text
                )
                
                # Insert the paper
                success = self.db.insert_paper(paper)
                if success:
                    return f"Successfully added paper from {url}: {paper.title}"
                else:
                    return f"Failed to insert paper from {url} (may already exist)"
                    
            finally:
                # Clean up the temporary file
                if os.path.exists(temp_pdf_path):
                    os.unlink(temp_pdf_path)
                    
        except requests.RequestException as e:
            return f"Failed to download PDF from {url}: {str(e)}"
        except Exception as e:
            return f"Error adding paper from {url}: {str(e)}"
    
    def get_search_stats(self) -> Dict[str, Any]:
        """Get statistics about the local search capabilities."""
        try:
            total_papers = len(self.db.fetch_all_papers())
            papers_with_embeddings = total_papers - len(self.get_papers_without_embeddings())
            papers_with_text = sum(1 for p in self.db.fetch_all_papers() if p.get('text'))
            
            return {
                "total_papers": total_papers,
                "papers_with_embeddings": papers_with_embeddings,
                "papers_with_full_text": papers_with_text,
                "embedding_coverage": papers_with_embeddings / total_papers if total_papers > 0 else 0,
                "full_text_coverage": papers_with_text / total_papers if total_papers > 0 else 0,
                "pdf_download_enabled": self.enable_pdf_download,
                "pdf_processor_available": self.pdf_processor is not None
            }
        except Exception as e:
            return {"error": f"Failed to get search stats: {str(e)}"} 