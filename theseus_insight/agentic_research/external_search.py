import time
import random
import datetime
import tempfile
import os
from typing import List, Dict, Optional
import requests
import xml.etree.ElementTree as ET

from .local_search import BaseSearchTool




class SemanticScholarSearch:
    """
    Enhanced Semantic Scholar API client with improved error handling and rate limiting.

    This class provides a robust interface for searching papers on the Semantic Scholar API. 
    It handles API rate limiting, request retries, and response parsing with comprehensive
    error handling for production use.

    Attributes:
        BASE_URL (str): The base URL for the Semantic Scholar API.
        max_retries (int): The maximum number of retries for failed requests.
        backoff_factor (float): The factor to use for exponential backoff in case of retries.
        session (requests.Session): The session to use for requests.
    """

    BASE_URL = "https://api.semanticscholar.org/graph/v1/paper/search"

    def __init__(
        self,
        max_retries: int = 5,
        backoff_factor: float = 1.5,
        session: Optional[requests.Session] = None,
    ):
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        # Re-use a session for connection pooling
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                # Omitting a custom User-Agent avoids the 4xx rejection you saw
                "Accept": "application/json",
                "User-Agent": "TheseusInsight-ResearchAgent/1.0"
            }
        )

    def search(
        self,
        query: str,
        *,
        limit: int = 100,
        offset: int = 0,
        require_pdf: bool = False,  # Changed default to False for better coverage
        fields: Optional[List[str]] = None,
    ) -> List[Dict]:
        """
        Performs a search on Semantic Scholar using the provided query and parameters.

        Args:
            query (str): The search query to execute.
            limit (int, optional): The maximum number of results to return. Defaults to 10.
            offset (int, optional): The offset for pagination. Defaults to 0.
            require_pdf (bool, optional): If True, only returns papers with a PDF available. Defaults to False.
            fields (Optional[List[str]], optional): A list of fields to include in the response. Defaults to None.

        Returns:
            List[Dict]: A list of dictionaries, each representing a paper and its details.
        """
        if fields is None:
            fields = [
                "title",
                "year",
                "authors",
                "abstract",
                "url",
                "venue",
                "citationCount", 
                "influentialCitationCount",
                "isOpenAccess",
                "openAccessPdf",
                "publicationDate",
                "publicationTypes"
            ]

        params = {
            "query": query,
            "limit": limit,
            "offset": offset,
            "fields": ",".join(fields),
        }

        try:
            data = self._request(params)
            
            papers = [
                self._normalize_paper(p)
                for p in data.get("data", [])
                if not require_pdf  # no filtering
                or (p.get("openAccessPdf") and p["openAccessPdf"].get("url"))
            ]
            
            return papers
            
        except Exception as e:
            print(f"Warning: Semantic Scholar search failed for query '{query}': {e}")
            return []

    def _request(self, params: Dict) -> Dict:
        """GET with exponential back-off on 429/5xx and network errors."""
        retries = 0
        while True:
            try:
                resp = self.session.get(self.BASE_URL, params=params, timeout=30)
                if resp.status_code == 429:
                    raise requests.exceptions.RetryError(
                        "Rate limit reached (429)", response=resp
                    )
                resp.raise_for_status()
                return resp.json()

            except (requests.exceptions.RetryError, requests.exceptions.RequestException) as e:
                if retries >= self.max_retries:
                    raise RuntimeError(f"Semantic Scholar API request failed after {self.max_retries} retries: {e}")

                # Exponential back-off with jitter
                sleep_for = self.backoff_factor * (2 ** retries) + random.uniform(0, 1)
                print(f"Retrying Semantic Scholar request in {sleep_for:.1f}s (attempt {retries + 1}/{self.max_retries})")
                time.sleep(sleep_for)
                retries += 1

    @staticmethod
    def _normalize_paper(paper: Dict) -> Dict:
        """
        Normalize a paper dictionary by flattening its structure and adding a 'pdf_url' field if available.

        This method takes a paper dictionary as input, which may contain nested structures. It flattens the dictionary
        by removing any nested structures and adding the 'pdf_url' field if the paper has an open access PDF available.
        The resulting dictionary is a shallow copy of the original, ensuring the original data structure is not modified.

        Args:
            paper (Dict): The paper dictionary to be normalized.

        Returns:
            Dict: A flattened dictionary representation of the paper with an added 'pdf_url' field if applicable.
        """
        pdf_url = None
        if paper.get("openAccessPdf"):
            pdf_url = paper["openAccessPdf"].get("url")

        # Make a shallow copy so we don't mutate the original dict
        flat = {k: v for k, v in paper.items() if k != "openAccessPdf"}
        if pdf_url:
            flat["pdf_url"] = pdf_url
            
        # Add formatted author string
        if paper.get("authors"):
            author_names = [author.get("name", "Unknown") for author in paper["authors"]]
            flat["authors_str"] = ", ".join(author_names[:3])  # Show up to 3 authors
            if len(author_names) > 3:
                flat["authors_str"] += f" et al. ({len(author_names)} total)"
        else:
            flat["authors_str"] = "Unknown authors"
            
        return flat


class ArxivSearch:
    """
    Simple arXiv API client for searching papers.
    """
    BASE_URL = "http://export.arxiv.org/api/query"

    def __init__(
        self,
        max_retries: int = 3,
        backoff_factor: float = 1.5,
        session: Optional[requests.Session] = None
    ):
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.session = session or requests.Session()

    def _request(self, params: Dict) -> str:
        """GET with exponential back-off on 429/5xx and network errors, returns response text."""
        retries = 0
        delay = 2
        while True:
            try:
                resp = self.session.get(self.BASE_URL, params=params, timeout=30)
                if resp.status_code == 429:
                    raise requests.exceptions.RetryError(
                        "Rate limit reached (429)", response=resp
                    )
                resp.raise_for_status()
                return resp.text
            except (requests.exceptions.RetryError, requests.exceptions.RequestException) as e:
                if retries >= self.max_retries:
                    raise RuntimeError(f"arXiv API request failed after {self.max_retries} retries: {e}")
                sleep_for = delay
                print(f"Retrying arXiv request in {sleep_for:.1f}s (attempt {retries + 1}/{self.max_retries})")
                time.sleep(sleep_for)
                delay *= self.backoff_factor
                retries += 1

    def search(
        self,
        query: str,
        limit: int = 10,
        offset: int = 0,
        *,
        sort_by: str = "submittedDate",       # submittedDate or lastUpdatedDate
        sort_order: str = "descending"        # ascending or descending
    ) -> List[Dict]:
        params = {
            "search_query": f"all:{query}",
            "start": offset,
            "max_results": limit,
            "sortBy": sort_by,
            "sortOrder": sort_order,
        }
        xml_text = self._request(params)
        root = ET.fromstring(xml_text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        entries = root.findall("atom:entry", ns)
        results = []
        for entry in entries:
            title = entry.find("atom:title", ns).text.strip()
            summary = entry.find("atom:summary", ns).text.strip()
            published = entry.find("atom:published", ns).text[:10]
            # Restore original ID extraction
            id_url = entry.find("atom:id", ns).text.strip()
            # Convert arXiv abstract URL to direct PDF link
            pdf_url = id_url.replace('/abs/', '/pdf/')
            authors = [a.find("atom:name", ns).text for a in entry.findall("atom:author", ns)]
            results.append({
                "title": title,
                "abstract": summary,
                "authors": authors,
                "url": pdf_url,
                "published": published,
            })
        return results


class ExternalSearchTool(BaseSearchTool):
    """Enhanced search tool that queries ArXiv with comprehensive PDF processing."""

    def __init__(self, enable_pdf_download: bool = True, default_provider: str = "arxiv"):
        """Create a new tool instance with enhanced capabilities."""
        self.searcher = SemanticScholarSearch()
        self.arxiv_searcher = ArxivSearch()
        self.enable_pdf_download = enable_pdf_download
        self.default_provider = default_provider
        self.pdf_processor = None
        self._init_pdf_processor()

    def _init_pdf_processor(self):
        """Initialize PDF processor if dependencies are available."""
        try:
            from ..pdf.processing import SpacyLayoutDocProcessor
            self.pdf_processor = SpacyLayoutDocProcessor(
                language="en",
                save_text=False,
                export_tables=False,
                export_figures=False,
                remove_md_image_tags=True,
            )
        except ImportError:
            print("Warning: PDF processing dependencies not available for external search. PDF download will be disabled.")
            self.enable_pdf_download = False


    def find_papers_by_str(self, query: str, limit: int = 10, provider: str = None, sort_by_date: bool = True) -> str:
        """Search for papers using the specified provider (defaults to ArXiv)."""
        # Use default provider if none specified
        if provider is None:
            provider = self.default_provider
            
        if provider == "semantic_scholar":
            try:
                papers = self.searcher.search(query, limit=limit)
            except Exception as e:  # pragma: no cover - network failure handling
                return f"EXTERNAL SEARCH FAILED for '{query}': {e}\n\nPlease try the search again or use local search only."

            # Optionally sort by year (most recent first)
            if sort_by_date:
                papers.sort(key=lambda p: p.get("year", 0), reverse=True)

            if not papers:
                return f"No papers found in Semantic Scholar for query: '{query}'"

            # Enhanced formatting for agent consumption
            formatted_papers = []
            for i, paper in enumerate(papers, 1):
                paper_info = [
                    f"EXTERNAL PAPER {i}:",
                    f"  Title: {paper.get('title', 'Unknown Title')}",
                    f"  Authors: {paper.get('authors_str', 'Unknown authors')}",
                    f"  Year: {paper.get('year', 'Unknown')}",
                    f"  Venue: {paper.get('venue', 'Unknown venue')}"
                ]

                # Add citation metrics if available
                if paper.get('citationCount') is not None:
                    citations = paper.get('citationCount', 0)
                    influential = paper.get('influentialCitationCount', 0)
                    paper_info.append(f"  Citations: {citations} total, {influential} influential")

                # Add access information
                access_info = []
                if paper.get('isOpenAccess'):
                    access_info.append("Open Access")
                if paper.get('pdf_url'):
                    access_info.append("PDF available")
                if access_info:
                    paper_info.append(f"  Access: {', '.join(access_info)}")

                # Add URLs
                if paper.get('url'):
                    paper_info.append(f"  Semantic Scholar: {paper['url']}")
                if paper.get('pdf_url'):
                    paper_info.append(f"  PDF URL: {paper['pdf_url']}")

                # Add abstract with smart truncation
                abstract = paper.get('abstract', '')
                if abstract:
                    if len(abstract) > 300:
                        # Find a good break point near 300 characters
                        truncated = abstract[:300]
                        last_sentence = truncated.rfind('.')
                        if last_sentence > 250:  # If we found a sentence end reasonably close
                            abstract_preview = abstract[:last_sentence + 1] + "..."
                        else:
                            abstract_preview = truncated + "..."
                    else:
                        abstract_preview = abstract

                    paper_info.append(f"  Abstract: {abstract_preview}")

                formatted_papers.append('\n'.join(paper_info))

            # Create comprehensive result summary
            result_lines = [
                f"SEMANTIC SCHOLAR SEARCH RESULTS for '{query}':",
                f"Found {len(papers)} papers from external sources (showing top {limit}):",
                "",
                *formatted_papers,
                "",
                f"Source: Semantic Scholar API",
                f"Query processed at: {time.strftime('%Y-%m-%d %H:%M:%S')}"
            ]

            return '\n'.join(result_lines)
        elif provider == "arxiv":
            try:
                papers = self.arxiv_searcher.search(
                    query,
                    limit=limit,
                    sort_by="submittedDate",
                    sort_order="descending"
                )
            except Exception as e:
                return f"ARXIV SEARCH FAILED for '{query}': {e}\n\nPlease try the search again or use local search only."
            
            # Optionally sort by published date (newest first)
            if sort_by_date:
                papers.sort(
                    key=lambda p: datetime.datetime.strptime(p.get("published", "1900-01-01"), "%Y-%m-%d"),
                    reverse=True
                )
            
            if not papers:
                return f"No papers found in arXiv for query: '{query}'"

            # Enhanced formatting for agent consumption with ArXiv-specific metadata
            formatted_papers = []
            for i, paper in enumerate(papers, 1):
                paper_info = [
                    f"ARXIV PAPER {i}:",
                    f"  Title: {paper.get('title', 'Unknown Title')}",
                    f"  Authors: {', '.join(paper.get('authors', [])) or 'Unknown authors'}",
                    f"  Published: {paper.get('published', 'Unknown')}",
                    f"  ArXiv PDF: {paper.get('url', 'Unknown')}"
                ]
                
                # Add abstract with smart truncation
                abstract = paper.get("abstract", "")
                if abstract:
                    if len(abstract) > 300:
                        # Find a good break point near 300 characters
                        truncated = abstract[:300]
                        last_sentence = truncated.rfind('.')
                        if last_sentence > 250:  # If we found a sentence end reasonably close
                            abstract_preview = abstract[:last_sentence + 1] + "..."
                        else:
                            abstract_preview = truncated + "..."
                    else:
                        abstract_preview = abstract
                    paper_info.append(f"  Abstract: {abstract_preview}")
                
                formatted_papers.append("\n".join(paper_info))

            # Create comprehensive result summary  
            result_lines = [
                f"ARXIV SEARCH RESULTS for '{query}':",
                f"Found {len(papers)} papers on arXiv (showing top {limit}):",
                f"Note: All arXiv papers are open access with full PDF available",
                "",
                *formatted_papers,
            ]
            return "\n".join(result_lines)
        else:
            return f"Search provider '{provider}' not supported. Available providers: arxiv, semantic_scholar"

    def retrieve_full_text(self, paper_url: str) -> str:
        """Download and process a PDF from the provided URL."""
        if not self.enable_pdf_download:
            return "PDF download disabled for external search."
        
        if not self.pdf_processor:
            return "PDF processing not available for external search."
            
        return self._download_and_process_pdf(paper_url)

    def _download_and_process_pdf(self, url: str) -> str:
        """Download and process a PDF from URL with comprehensive error handling."""
        try:
            print(f"Downloading external PDF from {url}...")
            
            print(f"Processing external PDF content...")
            result = self.pdf_processor.process_document(url)
            markdown_text = result.get("processed_data", "")
            
            if not markdown_text:
                return f"FAILED TO EXTRACT TEXT from external PDF: {url}\nError: PDF processing returned empty content"
            
            # Parse the markdown if parser is available
            try:
                from ..pdf.parsers import FlatMarkdownParser
                parser = FlatMarkdownParser(markdown_text, max_tokens=60000)
                parsed_chunks = parser.get_parsed_data()
                full_text = '\n'.join(parsed_chunks)
            except ImportError:
                # Fallback to raw markdown if parser not available
                full_text = markdown_text
            
            return (
                f"EXTERNAL PDF CONTENT RETRIEVED:\n"
                f"Source: {url}\n"
                f"Content length: {len(full_text)} characters\n"
                f"Processing completed at: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"{'-' * 50}\n\n"
                f"{full_text}"
            )
            
                    
        except requests.RequestException as e:
            return (
                f"FAILED TO DOWNLOAD external PDF from {url}:\n"
                f"Network Error: {str(e)}\n"
                f"This may be due to access restrictions, network issues, or an invalid URL."
            )
        except Exception as e:  # pragma: no cover - network failure handling
            return (
                f"ERROR PROCESSING external PDF from {url}:\n"
                f"Processing Error: {str(e)}\n"
                f"The PDF may be corrupted, password-protected, or in an unsupported format."
            )
    
    def search_and_rank(self, query: str, limit: int = 10, provider: str = None) -> List[Dict]:
        """
        Search and return ranked results as structured data.
        
        Args:
            query: Search query
            limit: Maximum number of results
            provider: Search provider to use (defaults to ArXiv)
            
        Returns:
            List of paper dictionaries with enhanced metadata
        """
        # Use default provider if none specified
        if provider is None:
            provider = self.default_provider
            
        try:
            if provider == "semantic_scholar":
                papers = self.searcher.search(query, limit=limit)
                
                # Add ranking score based on multiple factors
                for i, paper in enumerate(papers):
                    # Base score from position in results
                    position_score = 1.0 - (i / len(papers)) * 0.3
                    
                    # Citation score (normalized)
                    citation_count = paper.get('citationCount', 0)
                    max_citations = max((p.get('citationCount', 0) for p in papers), default=1)
                    citation_score = citation_count / max_citations if max_citations > 0 else 0
                    
                    # Access score
                    access_score = 0.2
                    if paper.get('isOpenAccess'):
                        access_score += 0.3
                    if paper.get('pdf_url'):
                        access_score += 0.5
                    
                    # Recency score (papers from last 5 years get bonus)
                    current_year = time.gmtime().tm_year
                    paper_year = paper.get('year', current_year - 10)
                    if isinstance(paper_year, (int, float)) and paper_year >= current_year - 5:
                        recency_score = 0.2
                    else:
                        recency_score = 0
                    
                    # Combined ranking score
                    paper['external_ranking_score'] = (
                        position_score * 0.4 +
                        citation_score * 0.3 +
                        access_score * 0.2 +
                        recency_score * 0.1
                    )
                
                # Sort by ranking score
                papers.sort(key=lambda p: p.get('external_ranking_score', 0), reverse=True)
                
            elif provider == "arxiv":
                papers = self.arxiv_searcher.search(
                    query,
                    limit=limit,
                    sort_by="submittedDate",
                    sort_order="descending"
                )
                
                # Add ArXiv-specific ranking
                current_year = time.gmtime().tm_year
                for i, paper in enumerate(papers):
                    # Base score from position in results (ArXiv returns relevance-sorted results)
                    position_score = 1.0 - (i / len(papers)) * 0.3
                    
                    # Recency score (ArXiv papers are typically recent, so weight this highly)
                    try:
                        paper_year = int(paper.get('published', '1900')[:4])
                        if paper_year >= current_year - 2:
                            recency_score = 0.3  # Very recent
                        elif paper_year >= current_year - 5:
                            recency_score = 0.2  # Recent
                        else:
                            recency_score = 0.1  # Older
                    except (ValueError, TypeError):
                        recency_score = 0.1
                    
                    # Access score (all ArXiv papers have full PDF access)
                    access_score = 1.0
                    
                    # Title/abstract relevance score (simple keyword matching)
                    query_terms = set(query.lower().split())
                    paper_text = (paper.get('title', '') + ' ' + paper.get('abstract', '')).lower()
                    relevance_score = len([term for term in query_terms if term in paper_text]) / len(query_terms) if query_terms else 0
                    
                    # Combined ranking score for ArXiv
                    paper['external_ranking_score'] = (
                        position_score * 0.3 +
                        recency_score * 0.3 +
                        access_score * 0.2 +
                        relevance_score * 0.2
                    )
                    
                    # Add ArXiv-specific metadata
                    paper['pdf_url'] = paper.get('url', '')  # ArXiv URL is already PDF
                    paper['isOpenAccess'] = True  # All ArXiv papers are open access
                    paper['source_provider'] = 'arxiv'
                
                # Sort by ranking score
                papers.sort(key=lambda p: p.get('external_ranking_score', 0), reverse=True)
                
            else:
                print(f"Warning: Unsupported provider '{provider}', no results returned")
                return []
            
            return papers
            
        except Exception as e:
            print(f"Warning: External search ranking failed for '{query}' with provider '{provider}': {e}")
            return []
    
    def get_search_capabilities(self) -> Dict[str, any]:
        """Get information about external search capabilities."""
        return {
            "default_provider": self.default_provider,
            "available_providers": ["arxiv", "semantic_scholar"],
            "arxiv_capabilities": {
                "api_base_url": self.arxiv_searcher.BASE_URL,
                "rate_limit": "1 request per 2 seconds (per arXiv guidelines)",
                "access": "All papers open access with PDF",
                "coverage": "Computer science, mathematics, physics, and related fields"
            },
            "semantic_scholar_capabilities": {
                "api_base_url": self.searcher.BASE_URL,
                "rate_limit": "Exponential backoff on rate limits",
                "access": "Mixed - some open access, some abstracts only",
                "coverage": "Broader academic literature across disciplines"
            },
            "pdf_download_enabled": self.enable_pdf_download,
            "pdf_processor_available": self.pdf_processor is not None,
            "features": [
                "Academic paper search",
                "PDF download and processing",
                "Author information",
                "Publication date sorting",
                "Open access prioritization"
            ]
        }