import unittest
from unittest.mock import patch, MagicMock, mock_open
import io
import os

# Assuming PDFTextExtractor and related classes/functions are in theseus_insight.pdf.parsers
# Adjust import paths if necessary
try:
    from theseus_insight.pdf.parsers import PDFTextExtractor, DocumentConverter # Assuming DocumentConverter might also be here or related
    PDF_PARSER_CLASSES_EXIST = True
except ImportError:
    PDF_PARSER_CLASSES_EXIST = False
    # Dummy classes if real ones are not found
    class PDFTextExtractor:
        def __init__(self, pdf_processing_timeout=60): self.timeout = pdf_processing_timeout
        def extract_text_from_pdf_url(self, url): raise NotImplementedError
        def extract_text_from_local_pdf(self, local_path): raise NotImplementedError
    class DocumentConverter: # If it's a separate entity for converting to Langchain Docs
        def convert(self, text_content, metadata=None): raise NotImplementedError


@unittest.skipIf(not PDF_PARSER_CLASSES_EXIST, "Actual PDF parser classes not found.")
class TestPDFTextExtractor(unittest.TestCase):

    def setUp(self):
        self.extractor = PDFTextExtractor(pdf_processing_timeout=30)
        self.test_url = "http://example.com/test.pdf"
        self.test_local_path = "test_document.pdf"
        self.dummy_pdf_content_bytes = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj..."
        self.expected_text = "This is the extracted text from the PDF."

    def tearDown(self):
        if os.path.exists(self.test_local_path):
            os.remove(self.test_local_path)

    @patch('requests.get')
    @patch('pdfminer.high_level.extract_text_to_fp')
    @patch('io.BytesIO') # To handle the content stream
    def test_extract_text_from_pdf_url_success(self, mock_bytes_io, mock_extract_text_fp, mock_requests_get):
        # Mock requests.get response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = self.dummy_pdf_content_bytes
        mock_requests_get.return_value = mock_response

        # Mock io.BytesIO to return a readable stream
        mock_pdf_stream = io.BytesIO(self.dummy_pdf_content_bytes)
        mock_bytes_io.return_value = mock_pdf_stream
        
        # Mock extract_text_to_fp to simulate writing to the output string_io
        def simulate_extract_text(pdf_file_obj, output_string_io, **kwargs):
            output_string_io.write(self.expected_text)
        mock_extract_text_fp.side_effect = simulate_extract_text

        extracted_text = self.extractor.extract_text_from_pdf_url(self.test_url)

        mock_requests_get.assert_called_once_with(self.test_url, timeout=self.extractor.timeout)
        mock_bytes_io.assert_called_once_with(self.dummy_pdf_content_bytes)
        # extract_text_to_fp is called with the BytesIO stream and an internal StringIO
        self.assertTrue(mock_extract_text_fp.called)
        # Check that the first arg to extract_text_to_fp was our BytesIO stream
        self.assertEqual(mock_extract_text_fp.call_args[0][0], mock_pdf_stream)
        
        self.assertEqual(extracted_text, self.expected_text)

    @patch('requests.get')
    def test_extract_text_from_pdf_url_http_error(self, mock_requests_get):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_requests_get.return_value = mock_response

        with self.assertRaises(Exception) as context: # Assuming it raises a generic Exception or specific HTTPError
            self.extractor.extract_text_from_pdf_url(self.test_url)
        self.assertIn(f"Failed to download PDF from {self.test_url}. Status code: 404", str(context.exception))

    @patch('builtins.open', new_callable=mock_open, read_data=b"%PDF-1.4...") # Mock opening local file
    @patch('pdfminer.high_level.extract_text_to_fp')
    def test_extract_text_from_local_pdf_success(self, mock_extract_text_fp, mock_file_open):
        # Setup dummy local PDF file
        # mock_open already provides a file-like object when 'open' is called.

        def simulate_extract_text(pdf_file_obj, output_string_io, **kwargs):
            output_string_io.write(self.expected_text)
        mock_extract_text_fp.side_effect = simulate_extract_text
        
        # Create the dummy file so os.path.exists passes if checked by the method (not in current snippet)
        with open(self.test_local_path, "wb") as f: # This write will be to the real FS for setup
            f.write(self.dummy_pdf_content_bytes)

        # The actual open call inside the method will be mocked by mock_file_open
        extracted_text = self.extractor.extract_text_from_local_pdf(self.test_local_path)
        
        mock_file_open.assert_called_once_with(self.test_local_path, "rb")
        self.assertTrue(mock_extract_text_fp.called)
        # Check that the first arg to extract_text_to_fp was the file object from mock_open
        self.assertEqual(mock_extract_text_fp.call_args[0][0], mock_file_open.return_value)
        self.assertEqual(extracted_text, self.expected_text)


    @patch('pdfminer.high_level.extract_text_to_fp')
    def test_extract_text_pdf_parsing_error(self, mock_extract_text_fp):
        # Simulate an error during pdfminer's extraction process
        mock_extract_text_fp.side_effect = Exception("PDF parsing failed")

        # Create a dummy local file for the test
        with open(self.test_local_path, "wb") as f:
            f.write(self.dummy_pdf_content_bytes)
        
        with patch('builtins.open', mock_open(read_data=self.dummy_pdf_content_bytes)):
            with self.assertRaises(Exception) as context:
                self.extractor.extract_text_from_local_pdf(self.test_local_path)
        self.assertIn(f"Error extracting text from PDF {self.test_local_path}: PDF parsing failed", str(context.exception))


@unittest.skipIf(not PDF_PARSER_CLASSES_EXIST or not hasattr(PDFTextExtractor, 'process_pdfs_from_urls'), "PDFTextExtractor.process_pdfs_from_urls not available.")
class TestPDFTextExtractorProcessMultiple(unittest.TestCase):
    def setUp(self):
        self.extractor = PDFTextExtractor()

    @patch.object(PDFTextExtractor, 'extract_text_from_pdf_url')
    def test_process_pdfs_from_urls(self, mock_extract_single_url):
        urls = ["http://example.com/pdf1.pdf", "http://example.com/pdf2.pdf"]
        expected_texts = {
            urls[0]: "Text from PDF 1.",
            urls[1]: "Text from PDF 2."
        }
        mock_extract_single_url.side_effect = lambda url, timeout: (expected_texts[url], None) # Return (text, error) tuple

        results_df = self.extractor.process_pdfs_from_urls(urls)

        self.assertIsInstance(results_df, pd.DataFrame)
        self.assertEqual(len(results_df), 2)
        self.assertListEqual(list(results_df.columns), ['url', 'content_text', 'error'])
        self.assertEqual(results_df.loc[results_df['url'] == urls[0], 'content_text'].iloc[0], expected_texts[urls[0]])
        self.assertEqual(results_df.loc[results_df['url'] == urls[1], 'content_text'].iloc[0], expected_texts[urls[1]])
        self.assertTrue(pd.isna(results_df['error']).all())

    @patch.object(PDFTextExtractor, 'extract_text_from_pdf_url')
    def test_process_pdfs_from_urls_with_errors(self, mock_extract_single_url):
        urls = ["http://example.com/pdf1.pdf", "http://example.com/pdf_error.pdf"]
        
        def side_effect_func(url, timeout):
            if "error" in url:
                return (None, "Simulated extraction error")
            return (f"Text from {url}", None)
        mock_extract_single_url.side_effect = side_effect_func

        results_df = self.extractor.process_pdfs_from_urls(urls)
        
        self.assertEqual(len(results_df), 2)
        self.assertEqual(results_df.loc[results_df['url'] == urls[0], 'content_text'].iloc[0], f"Text from {urls[0]}")
        self.assertTrue(pd.isna(results_df.loc[results_df['url'] == urls[0], 'error'].iloc[0]))
        
        self.assertTrue(pd.isna(results_df.loc[results_df['url'] == urls[1], 'content_text'].iloc[0]))
        self.assertEqual(results_df.loc[results_df['url'] == urls[1], 'error'].iloc[0], "Simulated extraction error")


# Assuming DocumentConverter is a separate class for converting text to Langchain Documents
@unittest.skipIf(not PDF_PARSER_CLASSES_EXIST or not 'DocumentConverter' in globals(), "DocumentConverter class not found.")
class TestDocumentConverter(unittest.TestCase):
    @patch('langchain_core.documents.Document') # Mock the Langchain Document class
    def test_convert_basic(self, MockLangchainDocument):
        converter = DocumentConverter()
        text_content = "This is a document page."
        metadata = {"source": "test.pdf", "page": 1}
        
        mock_doc_instance = MagicMock()
        MockLangchainDocument.return_value = mock_doc_instance

        result_docs = converter.convert(text_content, metadata=metadata)

        self.assertEqual(len(result_docs), 1) # Assuming it creates one doc per text content
        MockLangchainDocument.assert_called_once_with(page_content=text_content, metadata=metadata)
        self.assertIn(mock_doc_instance, result_docs)

    # Add more tests for DocumentConverter if it has chunking logic, etc.

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
