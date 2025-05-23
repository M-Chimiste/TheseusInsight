import unittest
from unittest.mock import patch, MagicMock
import numpy as np
import datetime
import re # For testing clean_string, remove_markdown_tables

# Assuming utility functions are in theseus_insight.utils
from theseus_insight.utils import (
    get_n_days_ago,
    cosine_similarity,
    purge_ollama_cache, # Assuming this is the one to test
    clean_string,
    remove_markdown_tables
)

class TestUtils(unittest.TestCase):

    def test_get_n_days_ago(self):
        today = datetime.date.today()
        
        date_0_days_ago = get_n_days_ago(0)
        self.assertEqual(date_0_days_ago, today)

        date_7_days_ago = get_n_days_ago(7)
        expected_date_7_days_ago = today - datetime.timedelta(days=7)
        self.assertEqual(date_7_days_ago, expected_date_7_days_ago)

        date_30_days_ago = get_n_days_ago(30)
        expected_date_30_days_ago = today - datetime.timedelta(days=30)
        self.assertEqual(date_30_days_ago, expected_date_30_days_ago)

    def test_cosine_similarity(self):
        vec_a = np.array([1, 0, 0])
        vec_b = np.array([0, 1, 0])
        vec_c = np.array([1, 0, 0])
        vec_d = np.array([1, 1, 0]) / np.sqrt(2) # Normalized version of [1,1,0]
        vec_e = np.array([2, 0, 0]) # Same direction as A, different magnitude

        # Orthogonal vectors
        self.assertAlmostEqual(cosine_similarity(vec_a, vec_b), 0.0)
        
        # Identical vectors
        self.assertAlmostEqual(cosine_similarity(vec_a, vec_c), 1.0)
        
        # Known similarity (A and D are 45 degrees apart, cos(45) = 1/sqrt(2) ~ 0.707)
        self.assertAlmostEqual(cosine_similarity(vec_a, vec_d), 1/np.sqrt(2))
        
        # Vectors with different magnitudes but same direction
        self.assertAlmostEqual(cosine_similarity(vec_a, vec_e), 1.0)

        # Zero vector (handle gracefully if specified by implementation, otherwise may error or give nan)
        vec_zero = np.array([0,0,0])
        # Cosine similarity with zero vector is undefined (can result in NaN due to division by zero).
        # Check how the function handles this. If it's expected to raise error or return specific value:
        with np.errstate(invalid='ignore'): # Suppress runtime warning for division by zero
            similarity_with_zero = cosine_similarity(vec_a, vec_zero)
        self.assertTrue(np.isnan(similarity_with_zero) or similarity_with_zero == 0.0, 
                        "Cosine similarity with zero vector should be NaN or 0 depending on implementation details.")


    @patch('requests.post')
    def test_purge_ollama_cache_success(self, mock_requests_post):
        ollama_url = "http://localhost:11434"
        model_name = "llama2:latest"
        
        # Mock successful response from requests.post
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None # Simulate no HTTP error
        mock_requests_post.return_value = mock_response

        try:
            purge_ollama_cache(ollama_url, model_name)
            # No exception means success for this test's purpose
        except Exception as e:
            self.fail(f"purge_ollama_cache raised an unexpected exception: {e}")

        mock_requests_post.assert_called_once_with(
            f"{ollama_url}/api/generate",
            json={"model": model_name, "keep_alive": 0}
        )
        mock_response.raise_for_status.assert_called_once()


    @patch('requests.post')
    @patch('logging.error') # Assuming errors are logged
    def test_purge_ollama_cache_http_error(self, mock_logging_error, mock_requests_post):
        ollama_url = "http://ollama.server:11434"
        model_name = "gemma:7b"
        
        # Simulate an HTTP error
        import requests
        mock_requests_post.side_effect = requests.exceptions.RequestException("Connection failed")

        # The function is expected to catch the exception and log an error.
        # It should not re-raise the exception to the caller.
        try:
            purge_ollama_cache(ollama_url, model_name)
        except requests.exceptions.RequestException:
            self.fail("purge_ollama_cache should handle RequestException and not re-raise it.")
        
        mock_logging_error.assert_called_once()
        args, _ = mock_logging_error.call_args
        self.assertIn(f"Error purging Ollama cache for model {model_name}", args[0])
        self.assertIn("Connection failed", args[0])


    def test_clean_string(self):
        self.assertEqual(clean_string("  Hello\n\nWorld  "), "Hello\nWorld")
        self.assertEqual(clean_string("\n\n\nMultiple\n\n\nNewlines\n"), "Multiple\nNewlines")
        self.assertEqual(clean_string("   Leading and trailing spaces   "), "Leading and trailing spaces")
        self.assertEqual(clean_string("NoExtraSpaces"), "NoExtraSpaces")
        self.assertEqual(clean_string(""), "") # Empty string
        self.assertEqual(clean_string("\n"), "") # Only newlines
        self.assertEqual(clean_string("  \n  "), "") # Spaces and newlines

    def test_remove_markdown_tables(self):
        text_with_table = """
This is some text.
| Header 1 | Header 2 | Header 3 |
| -------- | :------: | -------- |
| Cell 1   | Cell 2   | Cell 3   |
| Cell 4   | Cell 5   | Cell 6   |
This is more text after the table.

Another paragraph.
| Simple | Table |
|---|---|
| A | B |

End of text.
"""
        expected_text_without_table = """
This is some text.
This is more text after the table.

Another paragraph.

End of text.
"""
        # Normalize by splitting lines and stripping, then rejoining.
        # This makes the comparison less sensitive to exact leading/trailing whitespace of the whole block.
        normalize = lambda s: "\n".join(line.strip() for line in s.strip().split('\n') if line.strip())
        
        processed_text = remove_markdown_tables(text_with_table)
        self.assertEqual(normalize(processed_text), normalize(expected_text_without_table))

        text_without_table = "This is simple text\nwithout any tables."
        self.assertEqual(normalize(remove_markdown_tables(text_without_table)), normalize(text_without_table))

        text_with_only_table = """
| Just | A | Table |
|------|---|-------|
| 1    | 2 | 3     |
"""
        self.assertEqual(normalize(remove_markdown_tables(text_with_only_table)), "")
        
        text_with_malformed_table_like_lines = """
This is text.
| Not really a table row but starts and ends with pipe |
This is | also not | a table.
| --- | --- | but not closed
"""
        # Current logic might remove the first malformed line. This depends on strictness.
        # The current regex `^\s*\|.*\|\s*$` will match it.
        # The second malformed line will not be removed.
        # The third malformed line `| --- | --- | but not closed` will not be removed by `table_separator_pattern` if it expects a closing pipe.
        # If the current regex for table_separator_pattern is `^\s*\|(?:\s*:?-+:?\s*\|)+\s*$` it expects a closing pipe.
        
        expected_after_malformed = """
This is text.
This is | also not | a table.
| --- | --- | but not closed
"""
        processed_malformed = remove_markdown_tables(text_with_malformed_table_like_lines)
        self.assertEqual(normalize(processed_malformed), normalize(expected_after_malformed))


if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
