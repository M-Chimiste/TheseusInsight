import unittest
import sqlite3
from datetime import datetime, date, timedelta
import json
import os

# Assuming PaperDatabase is in this path, adjust if necessary
from theseus_insight.data_model.data_handling import PaperDatabase
from theseus_insight.data_model.papers import Paper, Newsletter, Logs, Podcast

# Constants for default providers, matching the schema
DEFAULT_MODEL_PROVIDERS = sorted(['ollama', 'openai', 'anthropic', 'gemini', 'sentence-transformers', 'huggingface'])


class TestPaperDatabase(unittest.TestCase):

    def setUp(self):
        # Use an in-memory SQLite database for each test
        self.db_path = ":memory:"
        self.db = PaperDatabase(db_path=self.db_path)
        # Can also connect directly to verify schema or specific states if needed
        self.conn = self.db.conn 
        self.cursor = self.db.cursor

    def tearDown(self):
        self.conn.close()

    def _table_exists(self, table_name):
        self.cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}';")
        return self.cursor.fetchone() is not None

    def test_init_creates_tables(self):
        self.assertTrue(self._table_exists("papers"))
        self.assertTrue(self._table_exists("newsletters"))
        self.assertTrue(self._table_exists("podcasts"))
        self.assertTrue(self._table_exists("logs"))
        self.assertTrue(self._table_exists("settings"))
        self.assertTrue(self._table_exists("email_recipients"))
        self.assertTrue(self._table_exists("model_providers"))
        self.assertTrue(self._table_exists("orchestration_runs"))

    def test_insert_and_fetch_paper(self):
        paper_data = Paper(
            id="arxiv_test_001", title="Test Paper 1", abstract="Abstract 1",
            content_text="Content 1", authors=["Auth A"], publish_date=date(2023, 1, 1),
            pdf_url="http://example.com/p1.pdf", embedding_id="emb1", embedding_model="model_v1",
            cosine_similarity_score=0.88, relevant_to_research_interests=True,
            relevance_score=8, relevance_reason="Reason 1"
        )
        self.db.insert_paper(paper_data)

        # Fetch all
        all_papers = self.db.fetch_all_papers()
        self.assertEqual(len(all_papers), 1)
        retrieved_dict = all_papers[0]
        self.assertEqual(retrieved_dict["id"], paper_data.id)
        self.assertEqual(retrieved_dict["title"], paper_data.title)
        self.assertEqual(retrieved_dict["publish_date"], paper_data.publish_date.isoformat())
        self.assertEqual(retrieved_dict["relevance_score"], paper_data.relevance_score)

        # Fetch by ID
        retrieved_by_id_dict = self.db.fetch_paper_by_id(paper_data.id)
        self.assertIsNotNone(retrieved_by_id_dict)
        self.assertEqual(retrieved_by_id_dict["title"], paper_data.title)

        # Fetch non-existent
        self.assertIsNone(self.db.fetch_paper_by_id("non_existent_id"))

    def test_insert_and_fetch_newsletter(self):
        newsletter_data = Newsletter(
            date_generated=datetime(2023, 2, 1, 10, 0, 0),
            content_markdown="# Top News\n- Paper A\n- Paper B",
            paper_ids=["arxiv_test_001", "arxiv_test_002"],
            run_id="newsletter_run_01"
        )
        # insert_newsletter returns the ID of the newly inserted row
        newsletter_id = self.db.insert_newsletter(newsletter_data)
        self.assertIsNotNone(newsletter_id)

        all_newsletters = self.db.fetch_all_newsletters()
        self.assertEqual(len(all_newsletters), 1)
        retrieved_dict = all_newsletters[0]
        self.assertEqual(retrieved_dict["id"], newsletter_id)
        self.assertEqual(retrieved_dict["content_markdown"], newsletter_data.content_markdown)
        # paper_ids are stored as JSON string
        self.assertEqual(json.loads(retrieved_dict["paper_ids"]), newsletter_data.paper_ids)
        self.assertEqual(retrieved_dict["date_generated"], newsletter_data.date_generated.isoformat())


        retrieved_by_id_dict = self.db.fetch_newsletter_by_id(newsletter_id)
        self.assertIsNotNone(retrieved_by_id_dict)
        self.assertEqual(retrieved_by_id_dict["run_id"], newsletter_data.run_id)

    def test_insert_and_fetch_podcast(self):
        script_json_data = [{"speaker": "Host", "line": "Welcome!"}, {"speaker": "AI", "line": "Analyzing papers..."}]
        podcast_data = Podcast(
            title="AI Research Review Ep.1", date_generated=datetime(2023, 3, 1, 12, 0, 0),
            audio_file_path="/audio/ep1.mp3", script_text="Full script here.",
            paper_ids=["arxiv_test_003"], run_id="podcast_run_01",
            description="First episode.", cover_image_url="http://example.com/cover1.jpg",
            script_json=script_json_data 
        )
        podcast_id = self.db.insert_podcast(podcast_data)
        self.assertIsNotNone(podcast_id)

        all_podcasts = self.db.fetch_all_podcasts()
        self.assertEqual(len(all_podcasts), 1)
        retrieved_dict = all_podcasts[0]
        self.assertEqual(retrieved_dict["id"], podcast_id)
        self.assertEqual(retrieved_dict["title"], podcast_data.title)
        self.assertEqual(json.loads(retrieved_dict["script_json"]), podcast_data.script_json)

        retrieved_by_id_dict = self.db.fetch_podcast_by_id(podcast_id)
        self.assertIsNotNone(retrieved_by_id_dict)
        self.assertEqual(retrieved_by_id_dict["description"], podcast_data.description)

    def test_insert_and_get_logs(self):
        log_data1 = Logs(
            timestamp=datetime(2023, 4, 1, 10, 0, 0), service_name="LoggerTest",
            level="INFO", message="Log message 1", run_id="log_run_01"
        )
        log_data2 = Logs(
            timestamp=datetime(2023, 4, 1, 10, 5, 0), service_name="LoggerTest",
            level="WARNING", message="Log message 2", run_id="log_run_01"
        )
        self.db.insert_log(log_data1)
        self.db.insert_log(log_data2)

        recent_logs = self.db.get_recent_logs(limit=5)
        self.assertEqual(len(recent_logs), 2)
        self.assertEqual(recent_logs[0]["message"], log_data2.message) # Ordered by timestamp DESC
        self.assertEqual(recent_logs[1]["level"], log_data1.level)

        # Test limit
        limited_logs = self.db.get_recent_logs(limit=1)
        self.assertEqual(len(limited_logs), 1)

        # Test date filtering
        logs_on_date = self.db.get_recent_logs(from_date="2023-04-01", to_date="2023-04-01")
        self.assertEqual(len(logs_on_date), 2)
        
        logs_before_date = self.db.get_recent_logs(to_date="2023-03-31")
        self.assertEqual(len(logs_before_date), 0)

        logs_after_date = self.db.get_recent_logs(from_date="2023-04-02")
        self.assertEqual(len(logs_after_date), 0)


    def test_settings(self):
        # Test string setting
        self.db.set_setting("api_key", "test_key_123")
        self.assertEqual(self.db.get_setting("api_key"), "test_key_123")

        # Test JSON setting (e.g. a dictionary)
        json_value = {"url": "http://example.com", "port": 8080}
        self.db.set_setting("service_config", json.dumps(json_value))
        retrieved_json_str = self.db.get_setting("service_config")
        self.assertEqual(json.loads(retrieved_json_str), json_value)

        # Test getting non-existent setting
        self.assertIsNone(self.db.get_setting("non_existent_key"))

        # Update setting
        self.db.set_setting("api_key", "updated_key_456")
        self.assertEqual(self.db.get_setting("api_key"), "updated_key_456")

    def test_email_recipients(self):
        self.assertEqual(self.db.get_email_recipients(), []) # Initially empty

        recipients1 = ["user1@example.com", "user2@example.com"]
        self.db.set_email_recipients(recipients1)
        self.assertEqual(sorted(self.db.get_email_recipients()), sorted(recipients1))

        recipients2 = ["user3@example.com"]
        self.db.set_email_recipients(recipients2) # Should replace old list
        self.assertEqual(sorted(self.db.get_email_recipients()), sorted(recipients2))

        self.db.set_email_recipients([]) # Set back to empty
        self.assertEqual(self.db.get_email_recipients(), [])


    def test_model_providers_defaults(self):
        # The schema populates default model providers
        providers = self.db.get_model_providers()
        provider_names = sorted([p["name"] for p in providers])
        self.assertEqual(provider_names, DEFAULT_MODEL_PROVIDERS)
        
        # Test that IDs are present and are integers
        for p in providers:
            self.assertIn("id", p)
            self.assertIsInstance(p["id"], int)


    def test_visualizer_settings(self):
        # Test default (should be None or empty if not set)
        self.assertIsNone(self.db.get_visualizer_settings()) # schema doesn't pre-populate this

        settings_data = {"theme": "dark", "node_size": 10}
        self.db.set_setting("visualizer_settings", json.dumps(settings_data))
        
        retrieved_settings = self.db.get_visualizer_settings()
        self.assertEqual(retrieved_settings, settings_data)

    def test_orchestration_run_tracking(self):
        run_id_1 = "run_orchestration_1"
        run_id_2 = "run_orchestration_2"
        
        self.db.record_run(run_id_1, "newsletter_pipeline", "STARTED", datetime.now() - timedelta(minutes=10))
        run_status_1 = self.db.get_run_status(run_id_1)
        self.assertEqual(run_status_1["status"], "STARTED")
        self.assertEqual(run_status_1["pipeline_type"], "newsletter_pipeline")

        self.db.update_run_status(run_id_1, "COMPLETED")
        self.db.update_run_duration(run_id_1, 600.5) # 10 minutes
        self.db.update_run_artifact_path(run_id_1, "/path/to/artifact1.zip")
        
        run_status_1_updated = self.db.get_run_status(run_id_1)
        self.assertEqual(run_status_1_updated["status"], "COMPLETED")
        self.assertEqual(run_status_1_updated["duration_seconds"], 600.5)
        self.assertEqual(run_status_1_updated["artifact_path"], "/path/to/artifact1.zip")

        self.db.record_run(run_id_2, "podcast_pipeline", "PROCESSING", datetime.now())
        self.db.update_run_error_message(run_id_2, "Something went wrong during podcast generation.")
        run_status_2 = self.db.get_run_status(run_id_2)
        self.assertEqual(run_status_2["status"], "PROCESSING") # Status not changed by error message alone
        self.assertEqual(run_status_2["error_message"], "Something went wrong during podcast generation.")
        
        # Test fetching all runs
        all_runs = self.db.get_all_runs(limit=5)
        self.assertEqual(len(all_runs), 2)
        # Assuming run_id_2 was recorded later, it should appear first (default DESC order)
        self.assertEqual(all_runs[0]["run_id"], run_id_2)
        self.assertEqual(all_runs[1]["run_id"], run_id_1)

        # Test fetching non-existent run status
        self.assertIsNone(self.db.get_run_status("non_existent_run"))


if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
