import json
import os
import tempfile
import requests
from pathlib import Path
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod

from ..data_model.data_handling import PaperDatabase
from ..inference import SentenceTransformerInference
from ..pdf.processing import SpacyLayoutDocProcessor
from ..pdf.parsers import FlatMarkdownParser


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
    Local-first search tool that implements hybrid search over the papers database.
    
    Features:
    - Hybrid search combining BM25 (keyword) + vector similarity
    - Lazy embedding computation and caching
    - Automatic PDF download and processing using SpacyLayoutDocProcessor
    - Full text extraction and storage for papers
    - Configurable search parameters
    """
    
    def __init__(
        self,
        db: PaperDatabase,
        embedding_model: SentenceTransformerInference,
        semantic_weight: float = 0.6,
        keyword_weight: float = 0.4,
        similarity_threshold: float = 0.3,
        enable_pdf_download: bool = True
    ):
        """
        Initialize LocalSearchTool.
        
        Args:
            db: PaperDatabase instance for data access
            embedding_model: SentenceTransformerInference instance for embeddings
            semantic_weight: Weight for semantic similarity (default 0.6)
            keyword_weight: Weight for keyword/BM25 similarity (default 0.4)
            similarity_threshold: Minimum similarity threshold (default 0.3)
            enable_pdf_download: Enable automatic PDF download and processing (default True)
        """
        self.db = db
        self.embedding_model = embedding_model
        self.semantic_weight = semantic_weight
        self.keyword_weight = keyword_weight
        self.similarity_threshold = similarity_threshold
        self.enable_pdf_download = enable_pdf_download
        
        # Initialize PDF processor
        self.pdf_processor = SpacyLayoutDocProcessor(
            language="en",
            save_text=False,
            export_tables=False,
            export_figures=False,
            remove_md_image_tags=True
        )
    
    def find_papers_by_str(self, query: str, limit: int = 10) -> str:
        """
        Find papers by search query using hybrid search.
        
        Args:
            query: Search query string
            limit: Maximum number of results to return
            
        Returns:
            Formatted string with paper results for the agent
        """
        try:
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
                return f"No papers found for query: '{query}'"
            
            # Format results for the agent
            formatted_papers = []
            for paper in papers:
                paper_info = (
                    f"ID: {paper['id']}\n"
                    f"Title: {paper['title']}\n"
                    f"Date: {paper['date']}\n"
                    f"Hybrid Score: {paper.get('hybrid_score', 0):.3f} "
                    f"(Semantic: {paper.get('semantic_score', 0):.3f}, "
                    f"Keyword: {paper.get('keyword_score', 0):.3f})\n"
                    f"Abstract: {paper['abstract'][:300]}...\n"
                    f"---"
                )
                formatted_papers.append(paper_info)
            
            result_summary = (
                f"Found {len(papers)} papers for query: '{query}'\n"
                f"Showing top {limit} results:\n\n" +
                "\n".join(formatted_papers)
            )
            
            return result_summary
            
        except Exception as e:
            return f"Error searching papers: {str(e)}"
    
    def retrieve_full_text(self, paper_id: str) -> str:
        """
        Retrieve full text content of a paper by ID.
        If text is not available, attempt to download and process the PDF.
        
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
                return f"Paper with ID {paper_id} not found."
            
            # Check if full text is available
            full_text = paper.get('text')
            if full_text:
                return (
                    f"Full text for paper ID {paper_id}:\n"
                    f"Title: {paper['title']}\n"
                    f"Date: {paper['date']}\n"
                    f"URL: {paper['url']}\n\n"
                    f"Content:\n{full_text}"
                )
            
            # If no full text and PDF download is enabled, try to download and process
            if self.enable_pdf_download and paper.get('url'):
                return self._download_and_process_pdf(paper_id_int, paper)
            else:
                return (
                    f"Full text not available for paper ID {paper_id}.\n"
                    f"Title: {paper['title']}\n"
                    f"Abstract: {paper['abstract']}\n"
                    f"URL: {paper['url']}\n"
                    f"Note: PDF download is disabled or no URL available."
                )
                
        except ValueError:
            return f"Invalid paper ID format: {paper_id}. Expected integer."
        except Exception as e:
            return f"Error retrieving paper {paper_id}: {str(e)}"
    
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
            print(f"Error computing embedding for paper {paper_id}: {e}")
    
    def ensure_embeddings_computed(self) -> None:
        """Ensure all papers have embeddings computed (lazy caching)."""
        papers_without_embeddings = self.get_papers_without_embeddings()
        
        for paper in papers_without_embeddings:
            # Use abstract for embedding if no full text available
            text_to_embed = paper.get('text') or paper['abstract']
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
        Download and process a PDF from the paper's URL.
        
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
                
                # Download the PDF
                print(f"Downloading PDF from {url}...")
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                
                temp_file.write(response.content)
            
            try:
                # Process the PDF using SpacyLayoutDocProcessor
                print(f"Processing PDF for paper {paper_id}...")
                result = self.pdf_processor.process_document(temp_pdf_path)
                markdown_text = result.get('processed_data', '')
                
                if not markdown_text:
                    return (
                        f"Failed to extract text from PDF for paper ID {paper_id}.\n"
                        f"Title: {paper['title']}\n"
                        f"URL: {url}\n"
                        f"Note: PDF processing returned empty content."
                    )
                
                # Parse the markdown using FlatMarkdownParser
                parser = FlatMarkdownParser(markdown_text, max_tokens=60000)
                parsed_chunks = parser.get_parsed_data()
                
                # Combine all chunks into a single text
                full_text = '\n'.join(parsed_chunks)
                
                # Store the full text in the database
                self.db.update_paper_text(paper_id, full_text)
                
                return (
                    f"Full text for paper ID {paper_id} (downloaded and processed):\n"
                    f"Title: {paper['title']}\n"
                    f"Date: {paper['date']}\n"
                    f"URL: {url}\n\n"
                    f"Content:\n{full_text}"
                )
                
            finally:
                # Clean up the temporary file
                if os.path.exists(temp_pdf_path):
                    os.unlink(temp_pdf_path)
                    
        except requests.RequestException as e:
            return (
                f"Failed to download PDF for paper ID {paper_id}.\n"
                f"Title: {paper['title']}\n"
                f"URL: {url}\n"
                f"Error: {str(e)}"
            )
        except Exception as e:
            return (
                f"Error processing PDF for paper ID {paper_id}.\n"
                f"Title: {paper['title']}\n"
                f"URL: {url}\n"
                f"Error: {str(e)}"
            )
    
    def add_paper_from_url(self, url: str, paper_metadata: Dict[str, Any] = None) -> str:
        """
        Add a new paper from a URL by downloading and processing the PDF.
        This implements the ADD_PAPER functionality from FR-4.
        
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
            
            # Create a temporary file for the PDF
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
                temp_pdf_path = temp_file.name
                
                # Download the PDF
                print(f"Downloading PDF from {url}...")
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                
                temp_file.write(response.content)
            
            try:
                # Process the PDF
                print(f"Processing PDF from {url}...")
                result = self.pdf_processor.process_document(temp_pdf_path)
                markdown_text = result.get('processed_data', '')
                
                # Parse the markdown
                if markdown_text:
                    parser = FlatMarkdownParser(markdown_text, max_tokens=60000)
                    parsed_chunks = parser.get_parsed_data()
                    full_text = '\n'.join(parsed_chunks)
                else:
                    full_text = None
                
                # Create paper object with the extracted text
                from ..data_model.papers import Paper
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