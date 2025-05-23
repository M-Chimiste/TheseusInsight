import unittest
from unittest.mock import patch, MagicMock
import os
from datetime import datetime

# Attempt to import TheseusInsight, adjust path if necessary
try:
    from theseus_insight.theseus_insight import TheseusInsight
    from theseus_insight.inference.llm import LLMInterface, ChatAnthropic, ChatOpenAI, ChatVertexAI, ChatOllama
    from theseus_insight.constants import ANTHROPIC_API_KEY_ENV_VAR, OPENAI_API_KEY_ENV_VAR, GOOGLE_APPLICATION_CREDENTIALS_ENV_VAR
    from theseus_insight.data_processing.arxiv import ArxivDataProcessor # For mocking
    from theseus_insight.communication.communication import GmailCommunication # For mocking
    from theseus_insight.podcast.generator import PodcastGenerator # For mocking
    from theseus_insight.data_model.papers import Paper # For creating Paper objects
    from langchain_core.documents import Document # For mocking DocumentConverter
except ModuleNotFoundError:
    # This is a fallback for local testing if the module path is not correctly set up
    # You might need to adjust this based on your project structure and PYTHONPATH
    import sys
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from theseus_insight.theseus_insight import TheseusInsight
    from theseus_insight.inference.llm import LLMInterface, ChatAnthropic, ChatOpenAI, ChatVertexAI, ChatOllama
    from theseus_insight.constants import ANTHROPIC_API_KEY_ENV_VAR, OPENAI_API_KEY_ENV_VAR, GOOGLE_APPLICATION_CREDENTIALS_ENV_VAR
    from theseus_insight.data_processing.arxiv import ArxivDataProcessor # For mocking
    from theseus_insight.communication.communication import GmailCommunication # For mocking
    from theseus_insight.podcast.generator import PodcastGenerator # For mocking
    from theseus_insight.data_model.papers import Paper # For creating Paper objects
    from langchain_core.documents import Document # For mocking DocumentConverter

import pandas as pd

class TestTheseusInsight(unittest.TestCase):

    def setUp(self):
        # Clear relevant environment variables before each test
        for env_var in [ANTHROPIC_API_KEY_ENV_VAR, OPENAI_API_KEY_ENV_VAR, GOOGLE_APPLICATION_CREDENTIALS_ENV_VAR, "OLLAMA_HOST"]:
            if env_var in os.environ:
                del os.environ[env_var]

    @patch.dict(os.environ, {ANTHROPIC_API_KEY_ENV_VAR: "test_anthropic_key"})
    @patch('theseus_insight.theseus_insight.Config')
    @patch('theseus_insight.theseus_insight.OrchestrationDB')
    @patch('theseus_insight.theseus_insight.PaperDB')
    def test_init_default_parameters(self, MockPaperDB, MockOrchestrationDB, MockConfig):
        """Test TheseusInsight initialization with default parameters."""
        # Mock config values
        mock_config_instance = MockConfig.return_value
        mock_config_instance.get_research_interests.return_value = "default interests"
        mock_config_instance.get_model_config.return_value = {"type": "anthropic", "model_name": "claude-3-opus-20240229"}
        mock_config_instance.get_start_date.return_value = "2023-01-01"
        mock_config_instance.get_harvester_config.return_value = {"batch_size": 10}
        mock_config_instance.get_arxiv_config.return_value = {"max_results": 100}
        mock_config_instance.get_summarization_config.return_value = {"max_tokens": 500}
        mock_config_instance.get_communication_config.return_value = {"enable_email": False}
        mock_config_instance.get_db_path.return_value = ":memory:"
        mock_config_instance.get_vector_db_path.return_value = ":memory:"


        insight = TheseusInsight()

        self.assertIsNotNone(insight)
        self.assertEqual(insight.research_interests, "default interests")
        self.assertEqual(insight.start_date, datetime(2023, 1, 1).date())
        self.assertIsInstance(insight.inference_model, ChatAnthropic)
        MockPaperDB.assert_called_once()
        MockOrchestrationDB.assert_called_once()
        MockConfig.assert_called_once()

    @patch.dict(os.environ, {OPENAI_API_KEY_ENV_VAR: "test_openai_key"})
    @patch('theseus_insight.theseus_insight.Config')
    @patch('theseus_insight.theseus_insight.OrchestrationDB')
    @patch('theseus_insight.theseus_insight.PaperDB')
    def test_init_with_overrides_and_openai(self, MockPaperDB, MockOrchestrationDB, MockConfig):
        """Test TheseusInsight initialization with overridden parameters and OpenAI model."""
        # Mock config values
        mock_config_instance = MockConfig.return_value
        # These will be overridden by constructor arguments
        mock_config_instance.get_research_interests.return_value = "default interests"
        mock_config_instance.get_start_date.return_value = "2023-01-01"
        # This will be used as it's not overridden by constructor
        mock_config_instance.get_model_config.return_value = {"type": "openai", "model_name": "gpt-4"}
        mock_config_instance.get_harvester_config.return_value = {"batch_size": 10}
        mock_config_instance.get_arxiv_config.return_value = {"max_results": 100}
        mock_config_instance.get_summarization_config.return_value = {"max_tokens": 500}
        mock_config_instance.get_communication_config.return_value = {"enable_email": False}
        mock_config_instance.get_db_path.return_value = ":memory:"
        mock_config_instance.get_vector_db_path.return_value = ":memory:"


        override_interests = "override interests"
        override_start_date = "2024-02-15"
        override_model_config = {"type": "openai", "model_name": "gpt-3.5-turbo"}

        insight = TheseusInsight(
            research_interests_override=override_interests,
            start_date_override=override_start_date,
            model_config_override=override_model_config
        )

        self.assertEqual(insight.research_interests, override_interests)
        self.assertEqual(insight.start_date, datetime(2024, 2, 15).date())
        self.assertIsInstance(insight.inference_model, ChatOpenAI)
        self.assertEqual(insight.inference_model.model_name, "gpt-3.5-turbo")
        # Ensure Config methods for overridden values were not called
        mock_config_instance.get_research_interests.assert_not_called()
        mock_config_instance.get_start_date.assert_not_called()
        # Ensure Config method for model_config was called (as it's used by _load_inference_model directly)
        # but then overridden by model_config_override
        mock_config_instance.get_model_config.assert_not_called()


    @patch.dict(os.environ, {GOOGLE_APPLICATION_CREDENTIALS_ENV_VAR: "test_google_creds.json"})
    @patch('theseus_insight.theseus_insight.Config')
    @patch('theseus_insight.theseus_insight.OrchestrationDB')
    @patch('theseus_insight.theseus_insight.PaperDB')
    @patch('google.auth.default', return_value=(None, None)) # Mock google auth
    def test_load_inference_model_gemini(self, mock_google_auth, MockPaperDB, MockOrchestrationDB, MockConfig):
        """Test loading Gemini model."""
        mock_config_instance = MockConfig.return_value
        mock_config_instance.get_research_interests.return_value = "interests"
        mock_config_instance.get_start_date.return_value = "2023-01-01"
        mock_config_instance.get_model_config.return_value = {"type": "gemini", "model_name": "gemini-pro"}
        mock_config_instance.get_db_path.return_value = ":memory:"
        mock_config_instance.get_vector_db_path.return_value = ":memory:"

        insight = TheseusInsight()
        self.assertIsInstance(insight.inference_model, ChatVertexAI)
        self.assertEqual(insight.inference_model.model_name, "gemini-pro")

    @patch.dict(os.environ, {"OLLAMA_HOST": "http://localhost:11434"})
    @patch('theseus_insight.theseus_insight.Config')
    @patch('theseus_insight.theseus_insight.OrchestrationDB')
    @patch('theseus_insight.theseus_insight.PaperDB')
    def test_load_inference_model_ollama(self, MockPaperDB, MockOrchestrationDB, MockConfig):
        """Test loading Ollama model."""
        mock_config_instance = MockConfig.return_value
        mock_config_instance.get_research_interests.return_value = "interests"
        mock_config_instance.get_start_date.return_value = "2023-01-01"
        mock_config_instance.get_model_config.return_value = {"type": "ollama", "model_name": "llama2"}
        mock_config_instance.get_db_path.return_value = ":memory:"
        mock_config_instance.get_vector_db_path.return_value = ":memory:"

        insight = TheseusInsight()
        self.assertIsInstance(insight.inference_model, ChatOllama)
        self.assertEqual(insight.inference_model.model_name, "llama2")

    @patch('theseus_insight.theseus_insight.Config')
    @patch('theseus_insight.theseus_insight.OrchestrationDB')
    @patch('theseus_insight.theseus_insight.PaperDB')
    def test_load_inference_model_invalid_type(self, MockPaperDB, MockOrchestrationDB, MockConfig):
        """Test loading an invalid model type."""
        mock_config_instance = MockConfig.return_value
        mock_config_instance.get_research_interests.return_value = "interests"
        mock_config_instance.get_start_date.return_value = "2023-01-01"
        mock_config_instance.get_model_config.return_value = {"type": "unknown_model", "model_name": "unknown"}
        mock_config_instance.get_db_path.return_value = ":memory:"
        mock_config_instance.get_vector_db_path.return_value = ":memory:"


        with self.assertRaises(ValueError) as context:
            TheseusInsight()
        self.assertIn("Unsupported model type: unknown_model", str(context.exception))

    @patch.dict(os.environ, {ANTHROPIC_API_KEY_ENV_VAR: "test_anthropic_key"})
    @patch('theseus_insight.theseus_insight.Config')
    @patch('theseus_insight.theseus_insight.OrchestrationDB')
    @patch('theseus_insight.theseus_insight.PaperDB')
    def test_init_start_date_override_format(self, MockPaperDB, MockOrchestrationDB, MockConfig):
        """Test TheseusInsight initialization with start_date_override in different valid formats."""
        mock_config_instance = MockConfig.return_value
        mock_config_instance.get_research_interests.return_value = "default interests"
        mock_config_instance.get_model_config.return_value = {"type": "anthropic", "model_name": "claude-3-opus-20240229"}
        # This will be overridden
        mock_config_instance.get_start_date.return_value = "2023-01-01"
        mock_config_instance.get_db_path.return_value = ":memory:"
        mock_config_instance.get_vector_db_path.return_value = ":memory:"


        # Test with YYYY-MM-DD
        insight1 = TheseusInsight(start_date_override="2024-03-20")
        self.assertEqual(insight1.start_date, datetime(2024, 3, 20).date())

        # Test with datetime object
        date_obj = datetime(2022, 5, 10)
        insight2 = TheseusInsight(start_date_override=date_obj)
        self.assertEqual(insight2.start_date, date_obj.date())
        
        # Test with date object
        date_only_obj = date_obj.date()
        insight3 = TheseusInsight(start_date_override=date_only_obj)
        self.assertEqual(insight3.start_date, date_only_obj)

        # Test with invalid date string format
        with self.assertRaises(ValueError) as context:
            TheseusInsight(start_date_override="20-03-2024") # DD-MM-YYYY is not the expected format
        self.assertIn("Invalid date format for start_date_override", str(context.exception))

        # Test with invalid type
        with self.assertRaises(TypeError) as context:
            TheseusInsight(start_date_override=12345)
        self.assertIn("start_date_override must be a string, datetime.datetime, or datetime.date object", str(context.exception))

    @patch.dict(os.environ, {ANTHROPIC_API_KEY_ENV_VAR: "test_anthropic_key"})
    @patch('theseus_insight.theseus_insight.Config')
    @patch('theseus_insight.theseus_insight.PaperDB') # Only PaperDB needed for rank_papers
    @patch('theseus_insight.theseus_insight.LLMInterface') # Mock the LLMInterface for judge_inference
    def test_rank_papers(self, MockLLMInterface, MockPaperDB, MockConfig):
        """Test the rank_papers method."""
        # Setup Config mock
        mock_config_instance = MockConfig.return_value
        mock_config_instance.get_research_interests.return_value = "AI safety"
        mock_config_instance.get_model_config.return_value = {"type": "anthropic", "model_name": "claude-3"} # For main model
        mock_config_instance.get_db_path.return_value = ":memory:"
        mock_config_instance.get_vector_db_path.return_value = ":memory:"
        mock_config_instance.get_start_date.return_value = "2023-01-01"


        # Setup TheseusInsight instance
        # We don't need OrchestrationDB for rank_papers isolated test
        with patch('theseus_insight.theseus_insight.OrchestrationDB'):
            insight = TheseusInsight(model_config_override={"type": "anthropic", "model_name": "claude-3-haiku-20240307"}) # Use a specific judge model

        # Mock judge_inference model (part of the main inference_model in the code, but conceptually separate here)
        mock_judge_model = MockLLMInterface.return_value # This will be insight.inference_model
        
        # Mock papers DataFrame
        papers_data = {
            'id': ['1', '2', '3'],
            'title': ['Paper A', 'Paper B', 'Paper C'],
            'abstract': ['Abstract A', 'Abstract B', 'Abstract C'],
            'content_text': ['Content A', 'Content B', 'Content C'],
            'authors': [['Author A1'], ['Author B1'], ['Author C1']],
            'publish_date': [datetime(2023,1,1).date(), datetime(2023,1,2).date(), datetime(2023,1,3).date()],
            'pdf_url': ['url_a', 'url_b', 'url_c'],
            'cosine_similarity_score': [0.8, 0.9, 0.7] # Pre-calculated embedding scores
        }
        papers_df = pd.DataFrame(papers_data)

        # Mock judge model responses
        # Paper 1: Relevant, score 9
        # Paper 2: Not relevant, score 3
        # Paper 3: Relevant, score 7
        mock_judge_model.invoke.side_effect = [
            MagicMock(response={"related": "yes", "score": 9, "reason": "Reason A"}),
            MagicMock(response={"related": "no", "score": 3, "reason": "Reason B"}),
            MagicMock(response={"related": "yes", "score": 7, "reason": "Reason C"}),
        ]

        ranked_papers_df = insight.rank_papers(papers_df, db_saving=True)

        # Verify sorting (Paper 1 should be first, then Paper 3)
        self.assertEqual(len(ranked_papers_df), 2) # Paper 2 should be filtered out
        self.assertEqual(ranked_papers_df.iloc[0]['id'], '1')
        self.assertEqual(ranked_papers_df.iloc[0]['relevance_score'], 9)
        self.assertEqual(ranked_papers_df.iloc[1]['id'], '3')
        self.assertEqual(ranked_papers_df.iloc[1]['relevance_score'], 7)

        # Verify PaperDB interaction
        mock_paper_db_instance = MockPaperDB.return_value
        # Expected calls: one for paper '1' and one for paper '3'
        self.assertEqual(mock_paper_db_instance.insert_paper.call_count, 2)

        # Check that the correct data was passed to insert_paper for the first relevant paper
        call_args_paper1 = mock_paper_db_instance.insert_paper.call_args_list[0][0][0]
        self.assertIsInstance(call_args_paper1, Paper)
        self.assertEqual(call_args_paper1.id, '1')
        self.assertEqual(call_args_paper1.title, 'Paper A')
        self.assertEqual(call_args_paper1.relevance_score, 9)
        self.assertEqual(call_args_paper1.relevance_reason, "Reason A")
        self.assertTrue(call_args_paper1.relevant_to_research_interests)

        # Check no saving if db_saving is False
        mock_paper_db_instance.reset_mock()
        mock_judge_model.invoke.side_effect = [ # Reset side effect for new calls
            MagicMock(response={"related": "yes", "score": 9, "reason": "Reason A"}),
            MagicMock(response={"related": "no", "score": 3, "reason": "Reason B"}),
            MagicMock(response={"related": "yes", "score": 7, "reason": "Reason C"}),
        ]
        ranked_papers_df_no_save = insight.rank_papers(papers_df.copy(), db_saving=False)
        self.assertEqual(len(ranked_papers_df_no_save), 2)
        mock_paper_db_instance.insert_paper.assert_not_called()

    # More tests for 'run' method will follow here

    # Helper method to create TheseusInsight instance with common mocks for run tests
    def _create_theseus_insight_for_run_test(self, mock_config_instance, mock_progress_callback=None):
        mock_config_instance.get_research_interests.return_value = "AI ethics"
        mock_config_instance.get_model_config.return_value = {"type": "anthropic", "model_name": "claude-3-sonnet-20240229"}
        mock_config_instance.get_start_date.return_value = "2023-01-01"
        mock_config_instance.get_harvester_config.return_value = {"batch_size": 5, "pdf_parsing_timeout": 60}
        mock_config_instance.get_arxiv_config.return_value = {"max_results": 10}
        mock_config_instance.get_summarization_config.return_value = {"max_tokens": 300, "max_sum_model_tokens": 2000}
        mock_config_instance.get_communication_config.return_value = {
            "enable_email": True, "email_recipient": "test@example.com", "email_sender": "sender@example.com",
            "newsletter_title": "AI News", "newsletter_intro": "Welcome!", "max_papers_in_newsletter": 3
        }
        mock_config_instance.get_podcast_config.return_value = {
            "generate_podcast": True, "podcast_title": "AI Podcast", "podcast_artist": "Theseus",
            "podcast_description": "Podcast about AI", "podcast_cover_image_url": "http://example.com/cover.png",
            "podcast_intro_prompt": "Intro...", "podcast_outro_prompt": "Outro...", "podcast_model_name": "tts-1",
            "podcast_voice": "alloy", "max_papers_in_podcast": 3, "publish_podcast": False, "youtube_playlist_id": "playlist_id"
        }
        mock_config_instance.get_db_path.return_value = ":memory:" # Use in-memory for tests
        mock_config_instance.get_vector_db_path.return_value = ":memory:"
        mock_config_instance.get_checkpoint_dir.return_value = "test_checkpoints" # Ensure this dir exists or is mocked
        mock_config_instance.get_temp_dir.return_value = "test_temp"
        mock_config_instance.get_output_dir.return_value = "test_output"


        # Ensure API key for the default model type (anthropic)
        with patch.dict(os.environ, {ANTHROPIC_API_KEY_ENV_VAR: "test_anthropic_key"}):
             # Mock OrchestrationDB and PaperDB as they are always initialized
            with patch('theseus_insight.theseus_insight.OrchestrationDB') as MockOrchestrationDB, \
                 patch('theseus_insight.theseus_insight.PaperDB') as MockPaperDB:
                insight = TheseusInsight(progress_callback=mock_progress_callback)
                # Attach mocks for easier access in tests
                insight.mock_orchestration_db = MockOrchestrationDB.return_value
                insight.mock_paper_db = MockPaperDB.return_value
                return insight


    @patch('theseus_insight.theseus_insight.shutil.rmtree') # Mock shutil.rmtree for cleanup
    @patch('theseus_insight.theseus_insight.os.makedirs') # Mock os.makedirs
    @patch('theseus_insight.theseus_insight.os.path.exists', return_value=True) # Assume checkpoint/temp dirs exist
    @patch('theseus_insight.theseus_insight.Config')
    @patch('theseus_insight.theseus_insight.ArxivDataProcessor')
    @patch('theseus_insight.theseus_insight.EmbeddingModel') # Covers get_embedding_model
    @patch('theseus_insight.theseus_insight.LLMInterface') # Covers judge, content_extraction, newsletter_sections, newsletter_intro
    @patch('theseus_insight.theseus_insight.DocumentConverter')
    @patch('theseus_insight.theseus_insight.GmailCommunication')
    @patch('theseus_insight.theseus_insight.PodcastGenerator')
    @patch('theseus_insight.theseus_insight.upload_video_to_youtube') # Mock youtube upload
    def test_run_full_pipeline_success(self, mock_upload_video, MockPodcastGenerator, MockGmailCommunication,
                                       MockDocumentConverter, MockLLMInterface, MockEmbeddingModel,
                                       MockArxivProcessor, MockConfig, mock_os_path_exists, mock_os_makedirs, mock_shutil_rmtree):
        """Test the full run method pipeline successfully executes all stages."""
        mock_progress_callback = MagicMock()
        mock_config_instance = MockConfig.return_value
        insight = self._create_theseus_insight_for_run_test(mock_config_instance, mock_progress_callback)

        # --- Mock ArxivDataProcessor ---
        mock_arxiv_processor_instance = MockArxivProcessor.return_value
        raw_papers_data = {
            'id': ['arxiv1', 'arxiv2', 'arxiv3', 'arxiv4', 'arxiv5'],
            'title': ['Title 1', 'Title 2', 'Title 3', 'Title 4', 'Title 5'],
            'abstract': ['Abstract 1', 'Abstract 2', 'Abstract 3', 'Abstract 4', 'Abstract 5'],
            'content_text': ['Content 1', 'Content 2', 'Content 3', 'Content 4', 'Content 5'],
            'authors': [['Auth1'], ['Auth2'], ['Auth3'], ['Auth4'], ['Auth5']],
            'publish_date': [datetime(2023,1,i+1).date() for i in range(5)],
            'pdf_url': [f'url{i+1}' for i in range(5)]
        }
        mock_arxiv_processor_instance.download_and_process_data.return_value = pd.DataFrame(raw_papers_data)

        # --- Mock EmbeddingModel ---
        mock_embedding_model_instance = MockEmbeddingModel.return_value
        # Simulate embeddings and cosine similarities
        mock_embedding_model_instance.get_embeddings_for_papers.return_value = (
            pd.DataFrame({**raw_papers_data, 'embedding_id': [f'emb{i}' for i in range(5)]}), # papers_with_embeddings_df
            pd.DataFrame({ # similarity_df
                'id': ['arxiv1', 'arxiv2', 'arxiv3', 'arxiv4', 'arxiv5'],
                'cosine_similarity_score': [0.9, 0.85, 0.6, 0.95, 0.7] # paper 3 below threshold
            })
        )
        insight.cosine_similarity_threshold = 0.8 # Set a threshold

        # --- Mock LLMInterface (used for multiple steps) ---
        # This single mock instance will be returned for all LLM calls in TheseusInsight
        # We'll need to configure its side_effect or return_value per call if different behaviors are needed.
        mock_llm_instance = MockLLMInterface.return_value
        insight.inference_model = mock_llm_instance # Ensure the instance uses the main mocked LLM
        insight.judge_inference = mock_llm_instance # And for judge
        insight.content_extraction_inference = mock_llm_instance # And for content extraction
        insight.newsletter_sections_inference = mock_llm_instance # etc.
        insight.newsletter_intro_inference = mock_llm_instance

        # Mock judge model responses (for rank_papers stage)
        # Papers arxiv1, arxiv2, arxiv4 are above embedding threshold
        # Let's say arxiv1 (0.9) and arxiv4 (0.95) are relevant, arxiv2 (0.85) is not.
        mock_llm_instance.invoke.side_effect = [
            # Judge responses for rank_papers
            MagicMock(response={"related": "yes", "score": 9, "reason": "Relevant"}), # arxiv1
            MagicMock(response={"related": "no", "score": 4, "reason": "Not relevant"}),# arxiv2
            MagicMock(response={"related": "yes", "score": 8, "reason": "Relevant"}), # arxiv4
            # Content extraction (summaries) for arxiv1, arxiv4
            MagicMock(response={"summary": "Summary for arxiv1"}),
            MagicMock(response={"summary": "Summary for arxiv4"}),
            # Newsletter sections for arxiv1, arxiv4
            MagicMock(response={"title": "Section for arxiv1", "key_takeaways": ["kt1"], "problem_statement": "ps1", "methodology": "m1", "results_and_discussion": "rd1", "conclusion": "c1", "critique_and_limitations": "cl1", "future_work": "fw1"}),
            MagicMock(response={"title": "Section for arxiv4", "key_takeaways": ["kt4"], "problem_statement": "ps4", "methodology": "m4", "results_and_discussion": "rd4", "conclusion": "c4", "critique_and_limitations": "cl4", "future_work": "fw4"}),
            # Newsletter intro
            MagicMock(response={"intro": "Generated Newsletter Intro"}),
        ]


        # --- Mock DocumentConverter ---
        mock_doc_converter_instance = MockDocumentConverter.return_value
        mock_doc_converter_instance.convert.return_value = [Document(page_content="markdown_doc_content")]


        # --- Mock GmailCommunication ---
        mock_gmail_comm_instance = MockGmailCommunication.return_value
        mock_gmail_comm_instance.compose_message.return_value = "composed_email_content"

        # --- Mock PodcastGenerator ---
        mock_podcast_generator_instance = MockPodcastGenerator.return_value
        mock_podcast_generator_instance.generate_podcast_script_from_papers.return_value = "podcast_script_content"
        mock_podcast_generator_instance.generate_podcast.return_value = ("podcast_audio.mp3", "podcast_script_final.txt")
        mock_podcast_generator_instance.generate_visualization_for_podcast.return_value = "podcast_video.mp4"


        # --- Execute the run method ---
        # Clear mocks for checkpoint loading to simulate a fresh run first
        with patch('theseus_insight.theseus_insight.TheseusInsight._load_checkpoint', return_value=None) as mock_load_checkpoint, \
             patch('theseus_insight.theseus_insight.TheseusInsight._save_checkpoint') as mock_save_checkpoint:

            result_df = insight.run(db_saving=True, generate_email=True, generate_podcast=True, publish_podcast=True)

            # --- Assertions ---
            self.assertIsNotNone(result_df)
            self.assertEqual(len(result_df), 2) # arxiv1 and arxiv4 should be the final papers
            self.assertEqual(list(result_df['id']), ['arxiv1', 'arxiv4']) # Sorted by score (9 then 8)

            # Verify ArxivDataProcessor calls
            mock_arxiv_processor_instance.download_and_process_data.assert_called_once()

            # Verify EmbeddingModel calls
            mock_embedding_model_instance.get_embeddings_for_papers.assert_called_once()

            # Verify LLM calls (count them based on the side_effect list)
            # 3 for ranking, 2 for summaries, 2 for sections, 1 for intro = 8 calls
            self.assertEqual(mock_llm_instance.invoke.call_count, 8)


            # Verify DocumentConverter calls (called for each of the 2 selected papers for newsletter)
            self.assertEqual(mock_doc_converter_instance.convert.call_count, 2)


            # Verify GmailCommunication calls
            mock_gmail_comm_instance.compose_message.assert_called_once()
            mock_gmail_comm_instance.send_email.assert_called_once_with("composed_email_content")

            # Verify PodcastGenerator calls
            mock_podcast_generator_instance.generate_podcast_script_from_papers.assert_called_once()
            mock_podcast_generator_instance.generate_podcast.assert_called_once()
            mock_podcast_generator_instance.generate_visualization_for_podcast.assert_called_once()
            mock_upload_video.assert_called_once_with(
                video_file="test_output/podcast_video.mp4", # Assuming output dir from config
                title="AI Podcast",
                description="Podcast about AI",
                playlist_id="playlist_id",
                tags=["AI", "Research", "Podcast"]
            )


            # Verify DB insertions
            self.assertEqual(insight.mock_paper_db.insert_paper.call_count, 2) # For the two relevant papers
            insight.mock_paper_db.insert_newsletter.assert_called_once()
            insight.mock_paper_db.insert_podcast.assert_called_once()
            insight.mock_orchestration_db.record_run.assert_called_once()


            # Verify checkpoint saving (one for each major stage)
            # download, embed, rank, newsletter_sections, newsletter_content, podcast_script, podcast_visualized
            self.assertEqual(mock_save_checkpoint.call_count, 7)
            expected_checkpoints = [
                'papers_downloaded.pkl', 'papers_embedded.pkl', 'papers_ranked.pkl',
                'newsletter_sections.pkl', 'newsletter_content.txt', 'podcast_script.txt', 'podcast_visualized.mp4'
            ]
            for i, expected_name in enumerate(expected_checkpoints):
                args, _ = mock_save_checkpoint.call_args_list[i]
                self.assertEqual(args[1], expected_name) # args[0] is the data, args[1] is the filename


            # Verify progress callback
            # download_start, download_end, embed_start, embed_end, rank_start, rank_end,
            # newsletter_sections_start, newsletter_sections_end, newsletter_content_start, newsletter_content_end,
            # email_start, email_end, podcast_script_start, podcast_script_end,
            # podcast_audio_start, podcast_audio_end, podcast_viz_start, podcast_viz_end, podcast_publish_start, podcast_publish_end
            self.assertTrue(mock_progress_callback.call_count >= 20) # At least start/end for each main step
            mock_progress_callback.assert_any_call("download_papers_start", 0, {"total_steps": 7})
            mock_progress_callback.assert_any_call("podcast_publish_end", 7, {"output_video_file": "test_output/podcast_video.mp4"})


            # Verify cleanup
            mock_shutil_rmtree.assert_any_call("test_checkpoints")
            mock_shutil_rmtree.assert_any_call("test_temp")


    @patch('theseus_insight.theseus_insight.shutil.rmtree')
    @patch('theseus_insight.theseus_insight.os.makedirs')
    @patch('theseus_insight.theseus_insight.os.path.exists', return_value=True)
    @patch('theseus_insight.theseus_insight.Config')
    # Mock only the components relevant up to 'rank_papers' stage for this test
    @patch('theseus_insight.theseus_insight.ArxivDataProcessor')
    @patch('theseus_insight.theseus_insight.EmbeddingModel')
    @patch('theseus_insight.theseus_insight.LLMInterface') # For judge_inference
    @patch('theseus_insight.theseus_insight.TheseusInsight._save_checkpoint') # To inspect saved checkpoints
    @patch('theseus_insight.theseus_insight.TheseusInsight._load_checkpoint') # To control loaded checkpoints
    def test_run_start_from_rank_papers(self, mock_load_checkpoint, mock_save_checkpoint,
                                       MockLLMInterface, MockEmbeddingModel, MockArxivProcessor,
                                       MockConfig, mock_os_path_exists, mock_os_makedirs, mock_shutil_rmtree):
        """Test the run method starting from the 'rank_papers' stage."""
        mock_progress_callback = MagicMock()
        mock_config_instance = MockConfig.return_value
        # Disable email and podcast for this focused test
        comm_config = mock_config_instance.get_communication_config()
        comm_config["enable_email"] = False
        podcast_config = mock_config_instance.get_podcast_config()
        podcast_config["generate_podcast"] = False
        mock_config_instance.get_communication_config.return_value = comm_config
        mock_config_instance.get_podcast_config.return_value = podcast_config

        insight = self._create_theseus_insight_for_run_test(mock_config_instance, mock_progress_callback)

        # --- Setup loaded checkpoint data for 'papers_embedded' ---
        embedded_papers_data = {
            'id': ['arxiv1', 'arxiv2', 'arxiv3'], # Assume these passed embedding
            'title': ['Title 1', 'Title 2', 'Title 3'],
            'abstract': ['Abstract 1', 'Abstract 2', 'Abstract 3'],
            'content_text': ['Content 1', 'Content 2', 'Content 3'],
            'authors': [['Auth1'], ['Auth2'], ['Auth3']],
            'publish_date': [datetime(2023,1,i+1).date() for i in range(3)],
            'pdf_url': [f'url{i+1}' for i in range(3)],
            'cosine_similarity_score': [0.9, 0.85, 0.92]
        }
        mock_loaded_df = pd.DataFrame(embedded_papers_data)
        mock_load_checkpoint.side_effect = lambda name, _: mock_loaded_df if name == "papers_embedded.pkl" else None

        # --- Mock LLMInterface for judge model ---
        mock_llm_instance = MockLLMInterface.return_value
        insight.judge_inference = mock_llm_instance
        mock_llm_instance.invoke.side_effect = [
            MagicMock(response={"related": "yes", "score": 9, "reason": "Relevant"}), # arxiv1
            MagicMock(response={"related": "no", "score": 3, "reason": "Not Relevant"}), # arxiv2
            MagicMock(response={"related": "yes", "score": 7, "reason": "Relevant"}), # arxiv3
             # Mocks for subsequent stages (newsletter sections, intro - will be called if not skipped)
            MagicMock(response={"summary": "Summary for arxiv1"}),
            MagicMock(response={"summary": "Summary for arxiv3"}),
            MagicMock(response={"title": "Section for arxiv1", "key_takeaways": ["kt1"], "problem_statement": "ps1", "methodology": "m1", "results_and_discussion": "rd1", "conclusion": "c1", "critique_and_limitations": "cl1", "future_work": "fw1"}),
            MagicMock(response={"title": "Section for arxiv3", "key_takeaways": ["kt3"], "problem_statement": "ps3", "methodology": "m3", "results_and_discussion": "rd3", "conclusion": "c3", "critique_and_limitations": "cl3", "future_work": "fw3"}),
            MagicMock(response={"intro": "Newsletter Intro"}),
        ]
        # Also need to mock for content_extraction, newsletter_sections, newsletter_intro
        insight.inference_model = mock_llm_instance
        insight.content_extraction_inference = mock_llm_instance
        insight.newsletter_sections_inference = mock_llm_instance
        insight.newsletter_intro_inference = mock_llm_instance

        # --- Mock DocumentConverter for newsletter stage ---
        with patch('theseus_insight.theseus_insight.DocumentConverter') as MockDocumentConverter:
            mock_doc_converter_instance = MockDocumentConverter.return_value
            mock_doc_converter_instance.convert.return_value = [Document(page_content="markdown_doc_content")]

            # --- Execute run from 'rank_papers' ---
            result_df = insight.run(start_from='rank_papers', db_saving=False, generate_email=False, generate_podcast=False)

            # --- Assertions ---
            self.assertIsNotNone(result_df)
            self.assertEqual(len(result_df), 2) # arxiv1 and arxiv3
            self.assertEqual(list(result_df['id']), ['arxiv1', 'arxiv3'])

            # ArxivProcessor and EmbeddingModel should NOT have been called
            MockArxivProcessor.return_value.download_and_process_data.assert_not_called()
            MockEmbeddingModel.return_value.get_embeddings_for_papers.assert_not_called()

            # LLM invoke calls: 3 for ranking, 2 for summaries, 2 for sections, 1 for intro
            self.assertEqual(mock_llm_instance.invoke.call_count, 8)


            # Check that 'papers_embedded.pkl' was loaded
            mock_load_checkpoint.assert_any_call("papers_embedded.pkl", type='dataframe')

            # Check checkpoints saved (rank, newsletter_sections, newsletter_content)
            # Since email/podcast are off, only these should be saved after start_from
            # + the initial (empty) checkpoints for download/embed that _init_checkpoints might create if not careful
            # However, with start_from, it should skip saving for prior stages.
            saved_checkpoints = [args[1] for args, _ in mock_save_checkpoint.call_args_list]
            self.assertIn('papers_ranked.pkl', saved_checkpoints)
            self.assertIn('newsletter_sections.pkl', saved_checkpoints)
            self.assertIn('newsletter_content.txt', saved_checkpoints)
            self.assertNotIn('papers_downloaded.pkl', saved_checkpoints) # Should not be re-saved
            self.assertNotIn('papers_embedded.pkl', saved_checkpoints)   # Should not be re-saved


            # Progress callback should reflect starting from rank_papers
            mock_progress_callback.assert_any_call("rank_papers_start", 2, {"total_steps": 7, "num_papers": 3})


    @patch('theseus_insight.theseus_insight.shutil.rmtree')
    @patch('theseus_insight.theseus_insight.os.makedirs')
    @patch('theseus_insight.theseus_insight.os.path.exists', return_value=True)
    @patch('theseus_insight.theseus_insight.Config')
    @patch('theseus_insight.theseus_insight.ArxivDataProcessor') # Needed for the first step
    @patch('theseus_insight.theseus_insight.logging.getLogger') # To mock the logger
    def test_run_error_handling_and_logging(self, mock_get_logger, MockArxivProcessor, MockConfig, mock_os_path_exists, mock_os_makedirs, mock_shutil_rmtree):
        """Test error handling and logging within the run method."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        mock_progress_callback = MagicMock()
        mock_config_instance = MockConfig.return_value
        # Disable most things to focus on early error
        comm_config = mock_config_instance.get_communication_config(); comm_config["enable_email"] = False
        podcast_config = mock_config_instance.get_podcast_config(); podcast_config["generate_podcast"] = False
        mock_config_instance.get_communication_config.return_value = comm_config
        mock_config_instance.get_podcast_config.return_value = podcast_config

        insight = self._create_theseus_insight_for_run_test(mock_config_instance, mock_progress_callback)

        # --- Simulate error during ArxivDataProcessor ---
        mock_arxiv_processor_instance = MockArxivProcessor.return_value
        mock_arxiv_processor_instance.download_and_process_data.side_effect = Exception("Arxiv download failed")

        with self.assertRaises(Exception) as context:
            insight.run(db_saving=False)

        self.assertIn("Arxiv download failed", str(context.exception))

        # Verify logging
        # Check if _log_error was called (indirectly via the logger)
        self.assertTrue(any("Error during download_papers stage" in call_args[0][0] for call_args in mock_logger.error.call_args_list))

        # Verify orchestration DB status update on error
        insight.mock_orchestration_db.update_run_status.assert_any_call(insight.run_id, "FAILED")
        insight.mock_orchestration_db.update_run_error_message.assert_any_call(insight.run_id, "Arxiv download failed")


        # Verify cleanup is still called
        mock_shutil_rmtree.assert_any_call("test_checkpoints")
        # temp_dir might not be created if error is very early, but if it is, it should be cleaned.
        # mock_shutil_rmtree.assert_any_call("test_temp")


    @patch('theseus_insight.theseus_insight.shutil.rmtree')
    @patch('theseus_insight.theseus_insight.os.makedirs')
    @patch('theseus_insight.theseus_insight.os.path.exists', return_value=True)
    @patch('theseus_insight.theseus_insight.Config')
    @patch('theseus_insight.theseus_insight.ArxivDataProcessor') # Stage 1
    @patch('theseus_insight.theseus_insight.EmbeddingModel')   # Stage 2
    @patch('theseus_insight.theseus_insight.LLMInterface')     # Stage 3, 4, 5
    @patch('theseus_insight.theseus_insight.DocumentConverter')# Stage 4
    @patch('theseus_insight.theseus_insight.GmailCommunication')# Stage 6
    def test_run_skip_email_and_podcast(self, MockGmailComm, MockDocConverter, MockLLM, MockEmbedding, MockArxiv, MockConfig, mock_os_path_exists, mock_os_makedirs, mock_shutil_rmtree):
        """Test that email and podcast stages are skipped if configured."""
        mock_progress_callback = MagicMock()
        mock_config_instance = MockConfig.return_value
        
        # Explicitly disable email and podcast in config
        comm_config = mock_config_instance.get_communication_config(); comm_config["enable_email"] = False
        podcast_config = mock_config_instance.get_podcast_config(); podcast_config["generate_podcast"] = False
        mock_config_instance.get_communication_config.return_value = comm_config
        mock_config_instance.get_podcast_config.return_value = podcast_config

        insight = self._create_theseus_insight_for_run_test(mock_config_instance, mock_progress_callback)

        # Mock previous stages to return some data
        MockArxiv.return_value.download_and_process_data.return_value = pd.DataFrame({'id': ['1'], 'title': ['T'], 'abstract': ['A'], 'content_text': ['C'], 'authors': [['AU']], 'publish_date': [datetime.now().date()], 'pdf_url': ['url']})
        MockEmbedding.return_value.get_embeddings_for_papers.return_value = (pd.DataFrame({'id': ['1'], 'embedding_id': ['e1']}), pd.DataFrame({'id': ['1'], 'cosine_similarity_score': [0.9]}))
        
        mock_llm_instance = MockLLM.return_value
        insight.inference_model = mock_llm_instance
        insight.judge_inference = mock_llm_instance
        insight.content_extraction_inference = mock_llm_instance
        insight.newsletter_sections_inference = mock_llm_instance
        insight.newsletter_intro_inference = mock_llm_instance
        mock_llm_instance.invoke.side_effect = [ # rank, summary, section, intro
            MagicMock(response={"related": "yes", "score": 9, "reason": "R"}),
            MagicMock(response={"summary": "S"}),
            MagicMock(response={"title": "T", "key_takeaways": ["kt"], "problem_statement": "ps", "methodology": "m", "results_and_discussion": "rd", "conclusion": "c", "critique_and_limitations": "cl", "future_work": "fw"}),
            MagicMock(response={"intro": "I"}),
        ]
        MockDocConverter.return_value.convert.return_value = [Document(page_content="md")]

        with patch('theseus_insight.theseus_insight.TheseusInsight._load_checkpoint', return_value=None), \
             patch('theseus_insight.theseus_insight.TheseusInsight._save_checkpoint'):
            insight.run(generate_email=False, generate_podcast=False, db_saving=False)

        MockGmailComm.return_value.send_email.assert_not_called()
        # Check progress callback for skipped stages
        # Find all calls to progress_callback
        callback_calls = [call[0][0] for call in mock_progress_callback.call_args_list] # Get the first arg of each call
        self.assertIn("send_email_skipped", callback_calls)
        self.assertIn("generate_podcast_skipped", callback_calls)
        self.assertNotIn("send_email_start", callback_calls)
        self.assertNotIn("generate_podcast_script_start", callback_calls)


if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
