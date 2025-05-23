import unittest

# Assuming system prompt constants/functions are in theseus_insight.prompt.system_prompts
# Adjust imports as per actual file structure and contents
try:
    from theseus_insight.prompt.system_prompts import (
        DEFAULT_SYSTEM_PROMPT,
        NEWSLETTER_SYSTEM_PROMPT,
        PODCAST_SCRIPT_SYSTEM_PROMPT,
        JUDGE_SYSTEM_PROMPT,
        # Add other specific system prompt constants if they exist
    )
    SYSTEM_PROMPTS_EXIST = True
except ImportError:
    SYSTEM_PROMPTS_EXIST = False
    # Dummy constants if real ones are not found
    DEFAULT_SYSTEM_PROMPT = "You are a generic helpful assistant."
    NEWSLETTER_SYSTEM_PROMPT = "You are an AI assistant for creating research newsletters."
    PODCAST_SCRIPT_SYSTEM_PROMPT = "You are an AI assistant for writing podcast scripts about research."
    JUDGE_SYSTEM_PROMPT = "You are an AI judge evaluating research papers."


@unittest.skipIf(not SYSTEM_PROMPTS_EXIST, "Actual system prompt constants not found.")
class TestSystemPrompts(unittest.TestCase):

    def test_default_system_prompt_content(self):
        self.assertIsInstance(DEFAULT_SYSTEM_PROMPT, str)
        self.assertIn("helpful assistant", DEFAULT_SYSTEM_PROMPT.lower())
        # Add more specific checks based on the actual default prompt
        self.assertGreater(len(DEFAULT_SYSTEM_PROMPT), 20)

    def test_newsletter_system_prompt_content(self):
        self.assertIsInstance(NEWSLETTER_SYSTEM_PROMPT, str)
        self.assertIn("newsletter", NEWSLETTER_SYSTEM_PROMPT.lower())
        self.assertIn("research papers", NEWSLETTER_SYSTEM_PROMPT.lower())
        self.assertIn("summaries", NEWSLETTER_SYSTEM_PROMPT.lower())
        # Example: self.assertIn("target audience is researchers", NEWSLETTER_SYSTEM_PROMPT.lower())

    def test_podcast_script_system_prompt_content(self):
        self.assertIsInstance(PODCAST_SCRIPT_SYSTEM_PROMPT, str)
        self.assertIn("podcast script", PODCAST_SCRIPT_SYSTEM_PROMPT.lower())
        self.assertIn("engaging manner", PODCAST_SCRIPT_SYSTEM_PROMPT.lower())
        # Example: self.assertIn("conversational tone", PODCAST_SCRIPT_SYSTEM_PROMPT.lower())

    def test_judge_system_prompt_content(self):
        self.assertIsInstance(JUDGE_SYSTEM_PROMPT, str)
        self.assertIn("evaluate the relevance", JUDGE_SYSTEM_PROMPT.lower())
        self.assertIn("research paper", JUDGE_SYSTEM_PROMPT.lower())
        self.assertIn("scale of 1 to 10", JUDGE_SYSTEM_PROMPT.lower())
        self.assertIn("provide a brief reason", JUDGE_SYSTEM_PROMPT.lower())
        self.assertIn("JSON format", JUDGE_SYSTEM_PROMPT) # Assuming it asks for JSON output

    # Add more tests if there are other specific system prompts
    # For example:
    # def test_another_specific_system_prompt(self):
    #     from theseus_insight.prompt.system_prompts import ANOTHER_PROMPT
    #     self.assertIn("specific keyword", ANOTHER_PROMPT.lower())

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
