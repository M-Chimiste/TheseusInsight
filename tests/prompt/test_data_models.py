import unittest
from pydantic import ValidationError

# Assuming Pydantic models are in theseus_insight.prompt.data_models
# Adjust imports as per actual file structure and contents
try:
    from theseus_insight.prompt.data_models import (
        PaperAnalysisSchema, # Example names, replace with actual
        RelevanceJudgementSchema,
        NewsletterContentSchema,
        PodcastScriptSegmentSchema
    )
    PROMPT_DATA_MODELS_EXIST = True
except ImportError:
    PROMPT_DATA_MODELS_EXIST = False
    # Dummy Pydantic models if real ones are not found
    from pydantic import BaseModel, Field
    from typing import List, Optional

    class PaperAnalysisSchema(BaseModel):
        title: str
        summary: str
        key_points: List[str]
        critique: Optional[str] = None

    class RelevanceJudgementSchema(BaseModel):
        is_relevant: bool
        score: int = Field(..., ge=1, le=10)
        reason: str

    class NewsletterContentSchema(BaseModel):
        title: str
        introduction: str
        sections: List[dict] # Each dict could be another Pydantic model
        conclusion: str

    class PodcastScriptSegmentSchema(BaseModel):
        speaker: str
        dialogue: str
        segment_type: str # e.g., "intro", "paper_summary", "discussion", "outro"


@unittest.skipIf(not PROMPT_DATA_MODELS_EXIST, "Actual prompt data Pydantic models not found.")
class TestPromptDataModels(unittest.TestCase):

    def test_paper_analysis_schema_valid(self):
        data = {
            "title": "The Future of AI",
            "summary": "A comprehensive look at future AI trends.",
            "key_points": ["LLMs will advance.", "Ethical AI is crucial."],
            "critique": "Lacks discussion on quantum AI."
        }
        analysis = PaperAnalysisSchema(**data)
        self.assertEqual(analysis.title, data["title"])
        self.assertEqual(len(analysis.key_points), 2)
        self.assertEqual(analysis.critique, data["critique"])

    def test_paper_analysis_schema_missing_optional(self):
        data = {
            "title": "AI and Society",
            "summary": "Impact of AI on modern society.",
            "key_points": ["Job displacement.", "New opportunities."]
        } # critique is missing
        analysis = PaperAnalysisSchema(**data)
        self.assertEqual(analysis.title, data["title"])
        self.assertIsNone(analysis.critique) # Optional fields default to None

    def test_paper_analysis_schema_invalid_data(self):
        with self.assertRaises(ValidationError): # summary is missing
            PaperAnalysisSchema(title="Incomplete Data", key_points=[])
        
        with self.assertRaises(ValidationError): # key_points should be list
            PaperAnalysisSchema(title="Bad Type", summary="Sum", key_points="point 1")

    def test_relevance_judgement_schema_valid(self):
        data = {"is_relevant": True, "score": 9, "reason": "Highly aligned with research interests."}
        judgement = RelevanceJudgementSchema(**data)
        self.assertTrue(judgement.is_relevant)
        self.assertEqual(judgement.score, 9)

    def test_relevance_judgement_schema_invalid_score(self):
        with self.assertRaises(ValidationError): # score out of range
            RelevanceJudgementSchema(is_relevant=True, score=11, reason="Too high score")
        
        with self.assertRaises(ValidationError): # score not an int
            RelevanceJudgementSchema(is_relevant=False, score="low", reason="Score is string")

    def test_newsletter_content_schema_valid(self):
        data = {
            "title": "Weekly AI Digest",
            "introduction": "Welcome to this week's AI news!",
            "sections": [
                {"paper_title": "Paper A", "content": "Content for A"},
                {"paper_title": "Paper B", "content": "Content for B"}
            ],
            "conclusion": "See you next week!"
        }
        newsletter = NewsletterContentSchema(**data)
        self.assertEqual(newsletter.title, data["title"])
        self.assertEqual(len(newsletter.sections), 2)

    def test_podcast_script_segment_schema_valid(self):
        data = {
            "speaker": "Host Alice",
            "dialogue": "Today, we're diving into...",
            "segment_type": "intro"
        }
        segment = PodcastScriptSegmentSchema(**data)
        self.assertEqual(segment.speaker, "Host Alice")
        self.assertEqual(segment.segment_type, "intro")

    def test_podcast_script_segment_schema_missing_fields(self):
        with self.assertRaises(ValidationError): # dialogue is missing
            PodcastScriptSegmentSchema(speaker="Bob", segment_type="outro")


if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
