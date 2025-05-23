import unittest
from pydantic import ValidationError
from datetime import date, datetime

# Assuming models are in theseus_insight.data_model.papers and theseus_insight.data_model.dialog
# Adjust import paths if models are located elsewhere
from theseus_insight.data_model.papers import Paper, Newsletter, Logs, Podcast
from theseus_insight.data_model.dialog import DialogMessage, DialogTurn, LLMResponse

class TestPaperModels(unittest.TestCase):

    def test_paper_creation_valid(self):
        paper_data = {
            "id": "arxiv_12345",
            "title": "Test Paper",
            "abstract": "This is a test abstract.",
            "content_text": "Full text of the paper.",
            "authors": ["Author One", "Author Two"],
            "publish_date": date(2023, 1, 15),
            "pdf_url": "http://example.com/paper.pdf",
            "embedding_id": "emb_123",
            "embedding_model": "test_model_v1",
            "cosine_similarity_score": 0.95,
            "relevant_to_research_interests": True,
            "relevance_score": 9,
            "relevance_reason": "Highly relevant due to topic X."
        }
        paper = Paper(**paper_data)
        self.assertEqual(paper.id, paper_data["id"])
        self.assertEqual(paper.title, paper_data["title"])
        self.assertEqual(paper.publish_date, paper_data["publish_date"])
        self.assertEqual(paper.relevance_score, 9)

    def test_paper_invalid_data(self):
        with self.assertRaises(ValidationError):
            Paper(id="1", title="T", abstract="A", content_text="C", authors=[], publish_date="not-a-date")
        
        with self.assertRaises(ValidationError): # relevance_score should be int
            Paper(id="1", title="T", abstract="A", content_text="C", authors=[], publish_date=date.today(), relevance_score="high")

    def test_newsletter_creation_valid(self):
        newsletter_data = {
            "id": 1,
            "date_generated": datetime.now(),
            "content_markdown": "# Newsletter\nContent here.",
            "paper_ids": ["arxiv_123", "arxiv_456"],
            "run_id": "run_abc"
        }
        newsletter = Newsletter(**newsletter_data)
        self.assertEqual(newsletter.id, 1)
        self.assertEqual(len(newsletter.paper_ids), 2)

    def test_newsletter_invalid_data(self):
        with self.assertRaises(ValidationError): # date_generated should be datetime
            Newsletter(id=1, date_generated="not-a-datetime", content_markdown="md", paper_ids=[])
        
        with self.assertRaises(ValidationError): # paper_ids should be list of str
            Newsletter(id=1, date_generated=datetime.now(), content_markdown="md", paper_ids=[1, 2])


    def test_logs_creation_valid(self):
        log_data = {
            "id": 1,
            "timestamp": datetime.now(),
            "service_name": "Harvester",
            "level": "INFO",
            "message": "Harvesting complete.",
            "run_id": "run_xyz"
        }
        log_entry = Logs(**log_data)
        self.assertEqual(log_entry.service_name, "Harvester")
        self.assertEqual(log_entry.level, "INFO")

    def test_logs_invalid_data(self):
        with self.assertRaises(ValidationError): # timestamp should be datetime
            Logs(id=1, timestamp="yesterday", service_name="S", level="L", message="M")

    def test_podcast_creation_valid(self):
        podcast_data = {
            "id": 1,
            "title": "AI Weekly",
            "date_generated": datetime.now(),
            "audio_file_path": "/path/to/audio.mp3",
            "script_text": "Welcome to AI Weekly...",
            "paper_ids": ["arxiv_789"],
            "run_id": "run_podcast_1",
            "description": "A podcast about AI.",
            "cover_image_url": "http://example.com/cover.png",
            "script_json": [{"speaker": "Host", "line": "Hello world"}]
        }
        podcast = Podcast(**podcast_data)
        self.assertEqual(podcast.title, "AI Weekly")
        self.assertEqual(len(podcast.script_json), 1)

    def test_podcast_invalid_data(self):
        with self.assertRaises(ValidationError): # script_json should be list of dicts
            Podcast(id=1, title="T", date_generated=datetime.now(), audio_file_path="p", script_text="s", script_json="not-a-list-of-dicts")


class TestDialogModels(unittest.TestCase):

    def test_dialog_message_valid(self):
        msg = DialogMessage(role="user", content="Hello there")
        self.assertEqual(msg.role, "user")
        self.assertEqual(msg.content, "Hello there")

    def test_dialog_message_invalid_role(self):
        with self.assertRaises(ValidationError):
            DialogMessage(role="invalid_role", content="Hi")

    def test_dialog_turn_valid(self):
        user_msg = DialogMessage(role="user", content="Question?")
        assistant_msg = DialogMessage(role="assistant", content="Answer!")
        turn = DialogTurn(user_message=user_msg, assistant_message=assistant_msg, timestamp=datetime.now())
        self.assertEqual(turn.user_message.content, "Question?")
        self.assertEqual(turn.assistant_message.role, "assistant")

    def test_llm_response_valid(self):
        resp = LLMResponse(
            response_text="This is a response.",
            model_name="gpt-4",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost=0.0025
        )
        self.assertEqual(resp.model_name, "gpt-4")
        self.assertEqual(resp.cost, 0.0025)
        self.assertIsNone(resp.response_json) # Default

    def test_llm_response_with_json(self):
        json_data = {"key": "value", "details": {"info": "more info"}}
        resp = LLMResponse(
            response_text="Response with JSON.",
            response_json=json_data, # Check if it handles dict input for JSON field
            model_name="claude-3"
        )
        self.assertEqual(resp.response_json["key"], "value")
        self.assertEqual(resp.response_json["details"]["info"], "more info")

    def test_llm_response_invalid_tokens(self):
        with self.assertRaises(ValidationError): # prompt_tokens should be int
            LLMResponse(response_text="Test", model_name="m", prompt_tokens="many")


if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
