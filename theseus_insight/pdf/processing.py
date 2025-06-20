import os
import logging
from pathlib import Path
import re
from typing import List, Dict, Any, Optional
import tempfile
import urllib.parse
import requests

import pandas as pd
from tqdm import tqdm
from markitdown import MarkItDown                 
from bs4 import BeautifulSoup                     
import markdown as md_lib  

import spacy
from spacy_layout import spaCyLayout
from docling.document_converter import DocumentConverter, PdfFormatOption, WordFormatOption
from docling.datamodel.base_models import InputFormat
from docling_core.types.doc import PictureItem, TableItem
from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode
from docling.pipeline.simple_pipeline import SimplePipeline
from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend

try:
    import mdpd                                   
except ImportError:                               
    mdpd = None

TABLE_REGEX = re.compile(r"(^\s*\|.*\|\s*$)", re.MULTILINE)


class FileNotAvailableError(Exception):
    """Exception raised when a file cannot be downloaded or accessed."""
    pass


class DoclingDocProcessor:
    """
    A class to process documents and export tables and figures.
    Attributes:
        doc_path (Path): The path to the document to be processed.
        export_tables (bool): Flag to indicate whether to export tables.
        export_figures (bool): Flag to indicate whether to export figures.
        verbose (bool): Flag to indicate whether to display progress information.
        table_format (str): The format in which to export tables ('csv', 'html', 'md').
        output_dir (Path): The directory where the output files will be saved.
        converter (DocumentConverter): The document converter instance.
        processed_doc: The processed document.
    Methods:
        __init__(doc_path, output_dir=None, table_format='csv', export_tables=True, export_figures=True, verbose=False):
            Initializes the DocProcessor with the given parameters.
        _process_doc(doc_path):
            Processes the document and returns the processed document.
        export_tables_method(output_dir):
        export_figures_method(output_dir):
    """

    def __init__(self, 
                 output_dir=None,
                 table_format='csv',
                 export_tables=True, 
                 export_figures=True,
                 save_text=False,
                 remove_md_image_tags=False,
                 verbose=False,
                 image_resolution_scale=2.0,
                 table_speed='accurate'):
        
        self.export_tables = export_tables
        self.export_figures = export_figures
        self.save_text = save_text
        self.remove_md_image_tags = remove_md_image_tags
        self.verbose = verbose
        self.output_dir = output_dir

        if table_format not in ['csv', 'html', 'md']:
            raise ValueError("table_format must be either 'csv', 'html', or 'md'")
        if table_speed not in ['accurate', 'fast']:
            raise ValueError("table_speed must be either 'accurate' or 'fast'")
        self.table_format = table_format

        self.output_dir = output_dir
        self.pipeline_options = PdfPipelineOptions()
        self.pipeline_options.generate_picture_images = True
        self.pipeline_options.images_scale = image_resolution_scale
        if table_speed == 'accurate':
            self.pipeline_options.table_structure_options.mode = TableFormerMode.ACCURATE
        if table_speed == 'fast':
            self.pipeline_options.table_structure_options.mode = TableFormerMode.FAST
        self.converter = DocumentConverter(
            allowed_formats=[
                InputFormat.PDF,
                InputFormat.IMAGE,
                InputFormat.DOCX,
                InputFormat.HTML,
                InputFormat.PPTX,
                InputFormat.ASCIIDOC,
                InputFormat.MD,
            ],
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_cls=StandardPdfPipeline, backend=PyPdfiumDocumentBackend, pipeline_options=self.pipeline_options
                ),
                InputFormat.DOCX: WordFormatOption(
                    pipeline_cls=SimplePipeline, 
                ),
            }
        )
        self.tables = None
        self.figures = None
        

    def export_markdown(self, converted_data):
        """
        Exports the converted data to a markdown format.

        Args:
            converted_data: The data that has been converted and needs to be exported.

        Returns:
            str: The markdown representation of the converted document.
        """
        data = converted_data.document.export_to_markdown()
        # Remove instances of 2+ newlines using regular expression
        data = re.sub(r'\n{2,}', '\n', data)
        if self.remove_md_image_tags:
            data = data.replace('<!-- image -->', '')
        return data
    
    def _process_doc(self, doc_path):
        return self.converter.convert(doc_path)
    

    def process_document(self, doc_path):
        """
        Processes an input document located at `doc_path` and performs various operations based on configuration 
        settings.

        The following steps are performed:
        1. Processes the original document to generate processed data.
        2. Exports generated markdown text from processing if enabled (`self.save_text`).
        - Saves as 'text.md' in a default output directory determined by `doc_path`.
        3. Extracts and exports tables using an internal method only when configured (via `self.export_tables`). 
        4. Processes the document further for figures extraction based on configuration settings.
        - Exports generated figure files to specified directories if enabled (`self.export_figures`).

        Args:
            doc_path: str, Path of input document that will be processed.

        Returns:
            dict: A dictionary with keys 'processed_data', 'tables', and 'figures'. 
                The values are markdown text (if saving was done), extracted tables,
                and figure data respectively. If a particular export is disabled (`self.export_tables`
                or `self.export_figures` set to False), the corresponding value will be None.
        """

        processed_data = self._process_doc(doc_path)
        markdown_data = self.export_markdown(processed_data)
        
        if self.save_text:
            output_dir = self.output_dir or self.get_default_output_dir(doc_path)
            with open(f"{output_dir}/text.md", "w") as f:
                f.write(markdown_data)
        if self.export_tables:
            output_dir = self.output_dir or self.get_default_output_dir(doc_path)
            tables = self.export_tables_method(output_dir, processed_data)
        else:
            tables = None
        if self.export_figures:
            output_dir = self.output_dir or self.get_default_output_dir(doc_path)
            figures = self.export_figures_method(output_dir, processed_data)
        else:
            figures = None
        if self.save_text:
            with open(f"{output_dir}/text.md", "w") as f:
                f.write(markdown_data)
        return {"processed_data": markdown_data, "tables": tables, "figures": figures}


    def get_default_output_dir(self, doc_path):
        """
        Generates and returns the default output directory for a given document path.

        This method takes the path to a document, extracts the filename, and creates
        a directory named after the filename (without extension) inside an 'output' folder.
        If the directory already exists, it will not raise an error.
        Args:
            str: The document path.
        Returns:
            str: The path to the default output directory.
        """
        base_path = self.output_dir or "output"
        filename = os.path.basename(doc_path)
        foldername = filename.split('.')[0]
        output_dir = f'{base_path}/{foldername}'
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        return output_dir


    def export_tables_method(self, output_dir, processed_doc):
        """
        Exports tables from the processed document to the specified output directory in the desired format.
        Args:
            output_dir (str): The directory where the tables will be saved.
        Raises:
            ValueError: If the table format is not supported.
        Notes:
            The supported table formats are 'csv', 'html', and 'md'. The method uses the `tqdm` library to display a progress bar if `self.verbose` is True.
        """
        table_format = self.table_format
        table_filenames = []
        for table_idx, table in tqdm(enumerate(processed_doc.document.tables), disable=not self.verbose):
            table_df: pd.DataFrame = table.export_to_dataframe()
            table_filename = f"{output_dir}/table_{table_idx+1}.{table_format}"
            table_filenames.append(table_filename)
            if table_format == 'csv':
                table_df.to_csv(table_filename, index=False)
            elif table_format == 'html':
                with open(table_filename, 'w') as f:
                    f.write(table.export_to_html())
            elif table_format == 'md':
                table_df.to_markdown(table_filename, index=False)

        return table_filenames


    def export_figures_method(self, output_dir, processed_doc):
        """
        Extracts and saves all figures from the processed document to the specified output directory.
        Args:
            output_dir (str): The directory where the extracted figures will be saved.
        Returns:
            list: A list of filenames for the saved figures.
        """
        document = processed_doc.document
        picture_counter = 0
        picture_filenames = []
        for element, _level in document.iterate_items():
            if isinstance(element, PictureItem):
                try:
                    picture_counter += 1
                    element_image_filename = Path(f"{output_dir}/picture-{picture_counter}.png")
                    picture_filenames.append(element_image_filename)
                    with element_image_filename.open("wb") as fp:
                        element.get_image(document).save(fp, "PNG")
                except AttributeError as e:
                    logging.error(f"Error saving picture: {e}")
                    continue
        return picture_filenames
    

class SpacyLayoutDocProcessor:
    """
    A class to process documents and extract layout information using spaCy.
    Attributes:
        doc_path (Path): The path to the document to be processed.
        verbose (bool): Flag to indicate whether to display progress information.
        nlp: The spaCy model instance.
        processed_doc: The processed document.
    Methods:
        __init__(doc_path, verbose=False):
            Initializes the SpacyLayoutProcessor with the given parameters.
        _process_doc(doc_path):
            Processes the document and returns the processed document.
        extract_layout_info():
            Extracts layout information from the processed document.
    """

    def __init__(self,
                language="en",
                table_format='csv',
                verbose=False,
                export_tables=True, 
                export_figures=True,
                save_text=False,
                image_resolution_scale=2.0,
                output_dir=None,
                remove_md_image_tags=False):
        
        if table_format not in ['csv', 'html', 'md']:
            raise ValueError("table_format must be either 'csv', 'html', or 'md'")
        self.table_format = table_format
        self.verbose = verbose
        self.export_tables = export_tables
        self.export_figures = export_figures
        self.save_text = save_text
        self.output_dir = output_dir
        self.remove_md_image_tags = remove_md_image_tags
        self.nlp = spacy.blank(language)
        self.converter = spaCyLayout(self.nlp)

        if export_figures:
            self.pipeline_options = PdfPipelineOptions()
            self.pipeline_options.generate_picture_images = True
            self.pipeline_options.images_scale = image_resolution_scale
            self.docling_converter = DocumentConverter(
            allowed_formats=[
                InputFormat.PDF,
                InputFormat.IMAGE,
                InputFormat.DOCX,
                InputFormat.HTML,
                InputFormat.PPTX,
                InputFormat.ASCIIDOC,
                InputFormat.MD,
            ],
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_cls=StandardPdfPipeline, backend=PyPdfiumDocumentBackend, pipeline_options=self.pipeline_options
                ),
                InputFormat.DOCX: WordFormatOption(
                    pipeline_cls=SimplePipeline, 
                ),
            }
        )

        
    def _process_doc(self, doc_path):
        return self.converter(doc_path)
    

    def _docling_process_doc(self, doc_path):
        return self.docling_converter.convert(doc_path)
    
    def process_document(self, doc_path):
        """
        Processes an input document located at `doc_path` and performs various operations based on configuration 
        settings.

        The following steps are performed:
        1. Processes the original document to generate processed data.
        2. Exports generated markdown text from processing if enabled (`self.save_text`).
        - Saves as 'text.md' in a default output directory determined by `doc_path`.
        3. Extracts and exports tables using an internal method only when configured (via `self.export_tables`). 
        4. Processes the document further for figures extraction based on configuration settings.
        - Exports generated figure files to specified directories if enabled (`self.export_figures`).

        Args:
            doc_path: str, Path of input document that will be processed.

        Returns:
            dict: A dictionary with keys 'processed_data', 'tables', and 'figures'. 
                The values are markdown text (if saving was done), extracted tables,
                and figure data respectively. If a particular export is disabled (`self.export_tables`
                or `self.export_figures` set to False), the corresponding value will be None.
        """

        processed_doc = self._process_doc(doc_path)
        markdown_data = self.export_markdown(processed_doc)
        if self.save_text:
            output_dir = self.get_default_output_dir(doc_path)
            with open(f"{output_dir}/text.md", "w") as f:
                f.write(markdown_data)
        if self.export_tables:
            output_dir = self.get_default_output_dir(doc_path)
            tables = self.export_tables_method(output_dir, processed_doc)
        else:
            tables = None

        if self.export_figures:
            output_dir = self.get_default_output_dir(doc_path)
            figure_data = self._docling_process_doc(doc_path)
            figures = self.export_figures_method(output_dir, figure_data)
        else:
            figures = None
        return {"processed_data": markdown_data, "tables": tables, "figures": figures}


    def get_default_output_dir(self, doc_path):
        """
        Generates and returns the default output directory for a given document path.

        This method takes the path to a document, extracts the filename, and creates
        a directory named after the filename (without extension) inside an 'output' folder.
        If the directory already exists, it will not raise an error.
        Args:
            str: The document path.
        Returns:
            str: The path to the default output directory.
        """
        base_path = self.output_dir or "output"
        filename = os.path.basename(doc_path)
        foldername = filename.split('.')[0]
        output_dir = f'{base_path}/{foldername}'
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        return output_dir


    def export_markdown(self, document):
        """
        Exports the markdown content of a document after processing.
        Args:
            document: The document object containing markdown content.
        Returns:
            str: The processed markdown content with optional image tags removed.
        """

        data = document._.markdown
        data = re.sub(r'\n{2,}', '\n', data)
        if self.remove_md_image_tags:
            data = data.replace('<!-- image -->', '')
        return data
    

    def export_tables_method(self, output_dir, document):
        """
        Exports tables from a document to the specified output directory in the specified format.
        Args:
            output_dir (str): The directory where the tables will be saved.
            document (Document): The document object containing tables to be exported.
        Returns:
            list: A list of filenames for the exported tables.
        Raises:
            ValueError: If the specified table format is not supported.
        Supported formats:
            - 'csv': Exports tables as CSV files.
            - 'html': Exports tables as HTML files.
            - 'md': Exports tables as Markdown files.
        """
        table_format = self.table_format
        tables = document._.tables
        table_filenames = []
        for table_idx, table in tqdm(enumerate(tables), disable=not self.verbose):
            table_df = table._.data
            table_filename = f"{output_dir}/table_{table_idx+1}.{table_format}"
            table_filenames.append(table_filename)
            if table_format == 'csv':
                table_df.to_csv(table_filename, index=False)
            elif table_format == 'html':
                with open(table_filename, 'w') as f:
                    f.write(table.export_to_html())
            elif table_format == 'md':
                table_df.to_markdown(table_filename, index=False)
        return table_filenames
    

    def export_figures_method(self, output_dir, processed_doc):
        """
        Extracts and saves all figures from the processed document to the specified output directory.
        Args:
            output_dir (str): The directory where the extracted figures will be saved.
        Returns:
            list: A list of filenames for the saved figures.
        """
        document = processed_doc.document
        picture_counter = 0
        picture_filenames = []
        for element, _level in document.iterate_items():
            if isinstance(element, PictureItem):
                try:
                    picture_counter += 1
                    element_image_filename = Path(f"{output_dir}/picture-{picture_counter}.png")
                    picture_filenames.append(element_image_filename)
                    with element_image_filename.open("wb") as fp:
                        element.get_image(document).save(fp, "PNG")
                except AttributeError as e:
                    logging.error(f"Error saving picture: {e}")
                    continue
        return picture_filenames    

class MarkitdownDocProcessor:
    """
    A class for processing and extracting data from Markdown documents.

    This class provides methods for converting Markdown documents to other formats,
    extracting tables and figures, and saving the extracted data to files. It also
    includes utilities for processing and cleaning the extracted data.
    
    The processor now supports both local file paths and URLs. When a URL is provided,
    the file is downloaded temporarily to the data directory, processed, and then
    cleaned up automatically.

    Attributes:
        table_format (str): The format to use when exporting tables. Defaults to 'dataframe'.
        export_tables (bool): Whether to export tables from the document. Defaults to True.
        export_figures (bool): Whether to export figures from the document. Defaults to True.
        save_text (bool): Whether to save the text content of the document. Defaults to False.
        remove_md_image_tags (bool): Whether to remove Markdown image tags from the text content. Defaults to False.
        verbose (bool): Whether to display progress information. Defaults to False.
        converter (MarkItDown): An instance of the MarkItDown converter for processing Markdown documents.
        
    Raises:
        FileNotAvailableError: When a URL cannot be downloaded or accessed.
    """
    # ---------- CTOR ----------
    def __init__(self,
                 table_format: str = "dataframe",
                 export_tables: bool = True,
                 export_figures: bool = True,
                 save_text: bool = False,
                 remove_md_image_tags: bool = False,
                 verbose: bool = False):
        if table_format not in {"dataframe", "raw"}:
            raise ValueError("table_format must be 'dataframe' or 'raw'")
        self.table_format         = table_format
        self.export_tables        = export_tables
        self.export_figures       = export_figures
        self.save_text            = save_text
        self.remove_md_image_tags = remove_md_image_tags
        self.verbose              = verbose

        # one MarkItDown instance is thread‑safe & cheap to re‑use
        self.converter = MarkItDown(enable_plugins=False)    #  [oai_citation:6‡github.com](https://github.com/microsoft/markitdown)

    # ---------- internal helpers ----------
    def _process_doc(self, doc_path: str):
        """Process a document, handling both local files and URLs."""
        # Check if doc_path is a URL
        parsed_url = urllib.parse.urlparse(doc_path)
        if parsed_url.scheme in ('http', 'https'):
            # Download the file temporarily
            return self._process_url(doc_path)
        else:
            # MarkItDown wants either a path or a binary stream – we give it the path.
            return self.converter.convert(doc_path)
    
    def _process_url(self, url: str):
        """Download a file from URL and process it temporarily."""
        temp_file = None
        try:
            # Create data directory if it doesn't exist
            data_dir = Path("data")
            data_dir.mkdir(exist_ok=True)
            
            # Download the file
            response = requests.get(url, timeout=30, stream=True)
            response.raise_for_status()
            
            # Determine file extension from URL or Content-Type
            file_ext = self._get_file_extension(url, response.headers.get('content-type', ''))
            
            # Create temporary file in data directory
            with tempfile.NamedTemporaryFile(
                delete=False, 
                dir=data_dir, 
                suffix=file_ext,
                prefix="temp_download_"
            ) as temp_file:
                # Download in chunks
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        temp_file.write(chunk)
                temp_file_path = temp_file.name
            
            # Process the temporary file
            result = self.converter.convert(temp_file_path)
            return result
            
        except requests.exceptions.RequestException as e:
            raise FileNotAvailableError(f"Failed to download file from {url}: {str(e)}")
        except Exception as e:
            raise FileNotAvailableError(f"Error processing file from {url}: {str(e)}")
        finally:
            # Clean up temporary file
            if temp_file and hasattr(temp_file, 'name') and os.path.exists(temp_file.name):
                try:
                    os.unlink(temp_file.name)
                except OSError:
                    logging.warning(f"Failed to remove temporary file: {temp_file.name}")
            elif 'temp_file_path' in locals() and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except OSError:
                    logging.warning(f"Failed to remove temporary file: {temp_file_path}")
    
    def _get_file_extension(self, url: str, content_type: str) -> str:
        """Determine file extension from URL or content type."""
        # First try to get extension from URL
        parsed_url = urllib.parse.urlparse(url)
        path = parsed_url.path
        if path:
            ext = os.path.splitext(path)[1]
            if ext:
                return ext
        
        # Fall back to content type mapping
        content_type_map = {
            'application/pdf': '.pdf',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation': '.pptx',
            'text/html': '.html',
            'text/markdown': '.md',
            'image/png': '.png',
            'image/jpeg': '.jpg',
            'image/gif': '.gif'
        }
        
        if content_type:
            # Remove charset and other parameters
            main_type = content_type.split(';')[0].strip()
            return content_type_map.get(main_type, '.tmp')
        
        return '.tmp'

    @staticmethod
    def _strip_double_newlines(text: str) -> str:
        return re.sub(r"\n{2,}", "\n", text)

    # ---------- public helpers ----------
    def export_markdown(self, converted) -> str:
        data = self._strip_double_newlines(converted.text_content)
        if self.remove_md_image_tags:
            data = re.sub(r"<!--\s*image\s*-->", "", data, flags=re.I)
        return data

    def _markdown_tables_to_dfs(self, markdown_text: str) -> List[pd.DataFrame]:
        dfs: List[pd.DataFrame] = []
        if mdpd:                                       # fast path   [oai_citation:7‡github.com](https://github.com/kyoto7250/mdpd)
            for tbl in mdpd.find_all_md(markdown_text):
                dfs.append(mdpd.from_md(tbl))
            return dfs

        # Fallback: convert whole doc to HTML then rely on pandas.read_html
        html = md_lib.markdown(markdown_text, extensions=["tables"])
        soup = BeautifulSoup(html, "html.parser")
        for tbl in soup.find_all("table"):
            try:
                df = pd.read_html(str(tbl))[0]         #  [oai_citation:8‡pandas.pydata.org](https://pandas.pydata.org/docs/reference/api/pandas.read_html.html?utm_source=chatgpt.com)
                dfs.append(df)
            except ValueError:
                continue
        return dfs

    def export_tables_method(self, markdown_text: str):
        if self.table_format == "raw":
            return TABLE_REGEX.findall(markdown_text)
        return self._markdown_tables_to_dfs(markdown_text)

    def export_figures_method(self, markdown_text: str) -> List[str]:
        # capture image paths – later you can resolve / download, etc.
        return re.findall(r"!\[.*?\]\((.*?)\)", markdown_text)

    def process_document(self, doc_path: str) -> Dict[str, Any]:
        """
        Processes a document and returns its content in markdown format along with extracted tables and figures.

        Args:
            doc_path (str): The path to the document file.

        Returns:
            Dict[str, Any]: A dictionary containing the processed markdown content, extracted tables, and figures.
        """
        converted = self._process_doc(doc_path)
        markdown  = self.export_markdown(converted)

        tables  = self.export_tables_method(markdown)  if self.export_tables  else None
        figures = self.export_figures_method(markdown) if self.export_figures else None

        # optional text dump for inspection
        if self.save_text:
            out = Path(doc_path).with_suffix(".md")
            out.write_text(markdown, encoding="utf-8")

        return {"processed_data": markdown, "tables": tables, "figures": figures}
