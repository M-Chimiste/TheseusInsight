import re
from typing import Dict, Union, List, Tuple
from pathlib import Path
from docling.document_converter import DocumentConverter
import requests
import warnings
import os
import tiktoken
from unidecode import unidecode
from ..utils import clean_string, remove_markdown_tables


def parse_pdf_to_markdown(pdf_path):
    """
    Parse a PDF file to markdown using the docling library.

    Args:
        pdf_path (str): The path to the PDF file.

    Returns:
        str: The markdown content of the PDF.
    """
    converter = DocumentConverter()
    response = converter.convert(pdf_path)
    markdown = response.document.export_to_markdown()
    return markdown


class MarkdownParser:
    """
    MarkdownParser is a class that parses markdown content into a hierarchical dictionary structure.

    Args:
        source (Union[str, Path]): The source of the markdown content, either as a string or a file path.

    Attributes:
        content (str): The raw markdown content.
        parsed_data (Dict): The parsed hierarchical representation of the markdown content.

    Methods:
        _load_content(source: Union[str, Path]) -> str:
            Loads the markdown content from a file or directly from a string.
        _parse_markdown() -> Dict:
            Parses the loaded markdown content into a hierarchical dictionary.
        get_parsed_data() -> Dict:
            Returns the parsed markdown data.
        find_sections(keyword: str) -> List[Dict]:
            Finds sections containing the given keyword.
    """
    def __init__(self, source: Union[str, Path]):
        self.content = self._load_content(source)
        self.parsed_data = self._parse_markdown()

    def _load_content(self, source: Union[str, Path]) -> str:
        if isinstance(source, Path):
            with open(source, 'r') as file:
                return file.read()
        return source

    def _parse_markdown(self) -> Dict:
        lines = self.content.split('\n')
        root = {}
        stack = [root]
        current_level = 0

        for line in lines:
            match = re.match(r'^(#+)\s+(.+)$', line)
            if match:
                level = len(match.group(1))
                title = match.group(2)

                while level <= current_level:
                    stack.pop()
                    current_level -= 1

                new_section = {}
                stack[-1][title] = new_section
                stack.append(new_section)
                current_level = level
            else:
                content = stack[-1].get('content', '')
                stack[-1]['content'] = content + line + '\n'

        return root

    def get_parsed_data(self) -> Dict:
        return self.parsed_data

    def find_sections(self, keyword: str) -> List[Dict]:
        """
        Find sections that contain the given keyword (case-insensitive).
        Matches sections even if the keyword is part of a larger title.
        """
        results = []
        self._search_sections(self.parsed_data, keyword.lower(), results)
        return results

    def _search_sections(self, data: Dict, keyword: str, results: List[Dict], path: List[str] = []):
        for title, content in data.items():
            current_path = path + [title]
            if keyword in title.lower():
                results.append({
                    'path': current_path,
                    'content': content.get('content', ''),
                    'subsections': {k: v for k, v in content.items() if k != 'content'}
                })
            elif isinstance(content, dict):
                self._search_sections(content, keyword, results, current_path)


class ReferencesParser(MarkdownParser):
    def __init__(self, content: str):
        super().__init__(content)
        self.references = self._extract_references()

    def _extract_references(self) -> List[str]:
        """
        Extract references from the parsed markdown content.

        Returns:
            List[str]: A list of references found in the content.
        """
        references_section = self.find_sections("references")
        if not references_section:
            return []

        references_content = references_section[0].get('content', '')
        references = self._parse_references(references_content)
        return references

    def _parse_references(self, content: str) -> List[str]:
        """
        Parse the references content to extract individual references.

        Args:
            content (str): The content of the references section.

        Returns:
            List[str]: A list of individual references.
        """
        # Split the content by newlines to get individual references
        references = content.split('\n')
        # Filter out empty lines and strip leading/trailing whitespace
        references = [ref.strip() for ref in references if ref.strip()]
        return references

    def get_references(self) -> List[str]:
        """
        Get the list of extracted references.

        Returns:
            List[str]: A list of references.
        """
        return self.references


class ArxivData:
    def __init__(self, url=None, arxiv_id=None) -> None:
        self.url = url
        self.arxiv_id = arxiv_id
        
        if url:
            self.pdf_path = self.download_url()
        if arxiv_id:
            self.pdf_path = self.download_id()
        else:
            self.pdf_path = None
        if not url and not arxiv_id:
           
            warnings.warn("No URL or Arxiv ID provided. To download a PDF, please pass a URL or Arxiv ID as a parameter, or call the download_url or download_id methods manually.", UserWarning)

        self.markdown_data = self.extract_content()


    def download_url(self, url=None):
        """Method to download a pdf from a given url

        Args:
            url (str): The url to download the pdf from.

        Returns:
            str: The path to the downloaded pdf.
        """
        
        url = url or self.url
        response = requests.get(url)
        temp_pdf_name = url.split('/')[-1]
        with open(f'temp_data/{temp_pdf_name}', 'wb') as f:
            f.write(response.content)
        
        pdf_path = Path(f'temp_data/{temp_pdf_name}')
        return pdf_path
    

    def download_id(self, arxiv=None):
        """Method to download a pdf from a given arxiv id

        Args:
            arxiv (str): The arxiv id to download the pdf from.

        Returns:
            str: The path to the downloaded pdf.
        """
        arxiv = arxiv or self.arxiv_id
        url = f"https://arxiv.org/pdf/{arxiv}.pdf"
        response = requests.get(url)
        with open('temp_data/temp.pdf', 'wb') as f:
            f.write(response.content)
        pdf_path = Path('temp_data/temp.pdf')
        return pdf_path
    

    def extract_content(self):
        """Method to extract the content from the pdf"""
        markdown = parse_pdf_to_markdown(self.pdf_path)
        if self.pdf_path and os.path.exists(self.pdf_path):
            os.remove(self.pdf_path)
        return markdown

class FlatMarkdownParser:
    """
    FlatMarkdownParser parses markdown content into a list of strings,
    binning content by a specified number of tokens using tiktoken.
    Headers are included as markdown headers within the list.

    If the entire content fits within the max_tokens limit, it's returned as a
    single-element list. Otherwise, it's binned based on headers and token limits.

    Args:
        source (Union[str, Path]): The source of the markdown content.
        max_tokens (int): The maximum number of tokens per content bin.

    Attributes:
        content (str): The raw markdown content.
        max_tokens (int): The maximum number of tokens per content bin.
        parsed_data (List[str]): The parsed list of content binned by tokens.
        encoding (tiktoken.Encoding): The tiktoken encoding used for tokenization.

    Methods:
        _load_content(source: Union[str, Path]) -> str:
            Loads the markdown content.
        _extract_headers() -> List[str]:
            Extracts headers from the markdown.
        _parse_markdown() -> List[str]:
            Parses the markdown content and returns a list.
        _bin_content(header: str, text: str) -> List[str]:
            Bins the text into chunks based on max_tokens, adding the header to each bin.
        get_parsed_data() -> List[str]:
            Returns the parsed data.
    """

    def __init__(self, 
                 source: Union[str, Path],
                 max_tokens: int = 60000,
                 remove_tables: bool = True):
        self.remove_tables = remove_tables
        self.content = self._load_content(source)
        self.max_tokens = max_tokens
        self.encoding = tiktoken.get_encoding("cl100k_base")

        # Internally, we store a list of (chunk_text, start_offset) 
        # so we can easily enable or disable span logic in get_parsed_data.
        self._parsed_tuples: List[Tuple[str,int]] = []

        # Run parse
        self._parse_markdown()

        # Do a final cleanup pass
        self._parsed_tuples = [(clean_string(txt), off) for (txt, off) in self._parsed_tuples]

    def _load_content(self, source: Union[str, Path]) -> str:
        if isinstance(source, Path):
            with open(source, 'r') as f:
                source = f.read()
        source = unidecode(source)
        if self.remove_tables:
            source = remove_markdown_tables(source)
        return source

    def _parse_markdown(self):
        """
        If the entire doc fits within max_tokens, store as a single chunk (text, offset=0).
        Otherwise, do naive chunking by lines. Adapt or improve as needed.
        """
        tokens = self.encoding.encode(self.content)
        if len(tokens) <= self.max_tokens:
            self._parsed_tuples.append((self.content, 0))
            return

        # A naive approach: we chunk by lines, respecting max_tokens. 
        # (You might do more robust logic: headers, paragraphs, etc.)
        lines = self.content.split('\n')
        running_offset = 0
        current_buffer = []
        current_buffer_tokens = 0

        for i, line in enumerate(lines):
            line_with_break = (line + '\n') if i < len(lines) - 1 else line
            line_tokens = len(self.encoding.encode(line_with_break))

            if current_buffer_tokens + line_tokens > self.max_tokens:
                # Flush existing buffer
                chunk_str = ''.join(current_buffer)
                self._parsed_tuples.append((chunk_str, running_offset))
                running_offset += len(chunk_str)
                current_buffer = [line_with_break]
                current_buffer_tokens = line_tokens
            else:
                current_buffer.append(line_with_break)
                current_buffer_tokens += line_tokens

        # Flush remainder
        if current_buffer:
            chunk_str = ''.join(current_buffer)
            self._parsed_tuples.append((chunk_str, running_offset))

    def get_parsed_data(self, return_spans: bool = False) -> Union[List[str], List[Tuple[str,int]]]:
        """
        If return_spans=False, returns a List[str] (old behavior).
        If return_spans=True, returns a List[(chunk_text, start_offset)].
        """
        if not return_spans:
            # Old behavior: just the chunk text
            return [txt for (txt, _) in self._parsed_tuples]
        else:
            # New behavior: text + offset
            return self._parsed_tuples
