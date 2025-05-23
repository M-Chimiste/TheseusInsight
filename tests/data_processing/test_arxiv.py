import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
from datetime import date, datetime, timedelta

# Assuming ArxivDataProcessor is in this path, adjust if necessary
from theseus_insight.data_processing.arxiv import ArxivDataProcessor

class TestArxivDataProcessor(unittest.TestCase):

    def setUp(self):
        self.research_interests = "artificial intelligence"
        self.start_date = date(2023, 1, 1)
        self.end_date = date(2023, 1, 7)
        self.max_results = 10
        self.filter_categories = ["cs.AI", "cs.CL"]
        self.sort_by = "submittedDate" # Default, can be "lastUpdatedDate"

    def test_init_with_dates(self):
        processor = ArxivDataProcessor(
            research_interests=self.research_interests,
            start_date=self.start_date,
            end_date=self.end_date,
            max_results=self.max_results,
            filter_categories=self.filter_categories,
            sort_by="lastUpdatedDate"
        )
        self.assertEqual(processor.research_interests, self.research_interests)
        self.assertEqual(processor.start_date, self.start_date)
        self.assertEqual(processor.end_date, self.end_date)
        self.assertEqual(processor.max_results, self.max_results)
        self.assertEqual(processor.filter_categories, self.filter_categories)
        self.assertEqual(processor.sort_by_arxiv, "lastUpdatedDate")

    def test_init_with_days_ago(self):
        days_ago = 7
        processor = ArxivDataProcessor(
            research_interests=self.research_interests,
            days_ago=days_ago,
            max_results=self.max_results
        )
        expected_start_date = date.today() - timedelta(days=days_ago)
        self.assertEqual(processor.start_date, expected_start_date)
        self.assertEqual(processor.end_date, date.today()) # Default end_date if days_ago is used

    def test_init_date_validation(self):
        with self.assertRaises(ValueError) as context:
            ArxivDataProcessor(research_interests="test", start_date=date(2023,1,10), end_date=date(2023,1,1))
        self.assertIn("Start date cannot be after end date.", str(context.exception))

        with self.assertRaises(ValueError) as context:
            ArxivDataProcessor(research_interests="test", days_ago=-1)
        self.assertIn("days_ago must be a non-negative integer.", str(context.exception))


    @patch('arxiv.Client') # Mock the client
    @patch('arxiv.Search') # Mock the Search object
    def test_download_and_process_data_success(self, MockSearch, MockClient):
        # --- Mock Arxiv Client and Search ---
        mock_client_instance = MockClient.return_value
        mock_search_instance = MockSearch.return_value
        
        # --- Mock Arxiv Results ---
        mock_results_iterator = []
        # Mock paper 1
        paper1 = MagicMock()
        paper1.entry_id = "http://arxiv.org/abs/2301.00001v1"
        paper1.title = "Paper Title 1"
        paper1.summary = "Abstract for paper 1."
        paper1.authors = [MagicMock(name="Author A"), MagicMock(name="Author B")]
        paper1.published = datetime(2023, 1, 2, 12, 0, 0) # Arxivpy returns datetime
        paper1.updated = datetime(2023, 1, 3, 10, 0, 0)
        paper1.pdf_url = "http://arxiv.org/pdf/2301.00001v1.pdf"
        paper1.categories = ["cs.AI", "cs.LG"]
        mock_results_iterator.append(paper1)

        # Mock paper 2 (outside filter_categories if we were to test that strictly here)
        paper2 = MagicMock()
        paper2.entry_id = "http://arxiv.org/abs/2301.00002v1"
        paper2.title = "Paper Title 2"
        paper2.summary = "Abstract for paper 2, different topic."
        paper2.authors = [MagicMock(name="Author C")]
        paper2.published = datetime(2023, 1, 4, 10, 0, 0)
        paper2.updated = datetime(2023, 1, 5, 11, 0, 0)
        paper2.pdf_url = "http://arxiv.org/pdf/2301.00002v1.pdf"
        paper2.categories = ["stat.ML"] # Different category
        mock_results_iterator.append(paper2)
        
        mock_search_instance.results.return_value = iter(mock_results_iterator)

        # --- Initialize Processor ---
        processor = ArxivDataProcessor(
            research_interests=self.research_interests,
            start_date=self.start_date,
            end_date=self.end_date,
            max_results=self.max_results,
            filter_categories=self.filter_categories, # ["cs.AI", "cs.CL"]
            sort_by=self.sort_by
        )

        # --- Call the method ---
        df = processor.download_and_process_data()

        # --- Assertions ---
        # Verify arxiv.Search was called correctly
        expected_query = f'({self.research_interests}) AND submittedDate:[{self.start_date.strftime("%Y%m%d")} TO {self.end_date.strftime("%Y%m%d")}]'
        if self.filter_categories:
            cat_query_part = " OR ".join([f"cat:{cat}" for cat in self.filter_categories])
            expected_query += f" AND ({cat_query_part})"
        
        MockSearch.assert_called_once_with(
            query=expected_query,
            max_results=self.max_results,
            sort_by=self.sort_by, # This should be an arxiv.SortCriterion enum
            client=mock_client_instance
        )
        mock_search_instance.results.assert_called_once()

        # Verify DataFrame content
        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(len(df), 2) # Both papers should be processed initially, filtering might happen later.
                                     # The query itself should handle category filtering if Arxiv API supports it well.
                                     # If Arxiv API's category filtering is loose, then post-filtering might be needed
                                     # and this test would change. The current code relies on Arxiv's query.

        # Check Paper 1 details
        self.assertEqual(df.iloc[0]["id"], "2301.00001v1") # Stripped version
        self.assertEqual(df.iloc[0]["title"], "Paper Title 1")
        self.assertEqual(df.iloc[0]["abstract"], "Abstract for paper 1.")
        self.assertEqual(df.iloc[0]["authors"], ["Author A", "Author B"])
        self.assertEqual(df.iloc[0]["publish_date"], paper1.published.date()) # Should be date object
        self.assertEqual(df.iloc[0]["updated_date"], paper1.updated.date())
        self.assertEqual(df.iloc[0]["pdf_url"], "http://arxiv.org/pdf/2301.00001v1.pdf")
        self.assertEqual(df.iloc[0]["categories"], ["cs.AI", "cs.LG"])

    @patch('arxiv.Client')
    @patch('arxiv.Search')
    def test_download_and_process_data_empty_results(self, MockSearch, MockClient):
        mock_search_instance = MockSearch.return_value
        mock_search_instance.results.return_value = iter([]) # Empty iterator

        processor = ArxivDataProcessor(
            research_interests="obscure topic with no papers",
            start_date=self.start_date,
            end_date=self.end_date,
            max_results=self.max_results
        )
        df = processor.download_and_process_data()

        self.assertIsInstance(df, pd.DataFrame)
        self.assertTrue(df.empty)
        expected_columns = ['id', 'title', 'abstract', 'authors', 'publish_date', 'updated_date', 'pdf_url', 'categories']
        self.assertListEqual(list(df.columns), expected_columns)

    @patch('arxiv.Client')
    @patch('arxiv.Search')
    def test_download_and_process_data_no_filter_categories(self, MockSearch, MockClient):
        mock_search_instance = MockSearch.return_value
        mock_search_instance.results.return_value = iter([]) # No results needed, just testing query

        processor = ArxivDataProcessor(
            research_interests=self.research_interests,
            start_date=self.start_date,
            end_date=self.end_date,
            filter_categories=None # Test with no filter_categories
        )
        processor.download_and_process_data()

        expected_query = f'({self.research_interests}) AND submittedDate:[{self.start_date.strftime("%Y%m%d")} TO {self.end_date.strftime("%Y%m%d")}]'
        # No category part in the query
        
        args, kwargs = MockSearch.call_args
        self.assertEqual(kwargs['query'], expected_query)


if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
