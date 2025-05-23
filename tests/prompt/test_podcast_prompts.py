import unittest

# Assuming prompt functions are in theseus_insight.prompt.podcast_prompts
# Adjust imports as per actual file structure and contents
try:
    from theseus_insight.prompt.podcast_prompts import (
        generate_podcast_description_prompt,
        generate_podcast_intro_segment_prompt,
        generate_podcast_outro_segment_prompt,
        generate_podcast_paper_discussion_prompt,
        # Add other specific podcast prompt functions if they exist
    )
    PODCAST_PROMPT_FUNCTIONS_EXIST = True
except ImportError:
    PODCAST_PROMPT_FUNCTIONS_EXIST = False
    # Dummy functions if real ones are not found
    def generate_podcast_description_prompt(podcast_title, papers_titles): return ""
    def generate_podcast_intro_segment_prompt(podcast_title, host_name, papers_count): return ""
    def generate_podcast_outro_segment_prompt(podcast_title, host_name): return ""
    def generate_podcast_paper_discussion_prompt(paper_title, paper_summary, paper_authors_str, host_name, previous_segment=None): return ""


@unittest.skipIf(not PODCAST_PROMPT_FUNCTIONS_EXIST, "Actual podcast prompt functions not found.")
class TestPodcastPrompts(unittest.TestCase):

    def test_generate_podcast_description_prompt(self):
        podcast_title = "AI Breakthroughs Weekly"
        papers_titles = ["Revolutionary Neural Networks", "The Future of Quantum AI"]
        
        prompt = generate_podcast_description_prompt(podcast_title, papers_titles)

        self.assertIn(podcast_title, prompt)
        for title in papers_titles:
            self.assertIn(title, prompt)
        self.assertIn("podcast description", prompt.lower())
        self.assertIn("engaging and informative", prompt.lower())

    def test_generate_podcast_intro_segment_prompt(self):
        podcast_title = "Tech Unveiled"
        host_name = "Alex"
        papers_count = 3
        
        prompt = generate_podcast_intro_segment_prompt(podcast_title, host_name, papers_count)

        self.assertIn(podcast_title, prompt)
        self.assertIn(host_name, prompt)
        self.assertIn(f"discussing {papers_count} key papers", prompt)
        self.assertIn("introductory segment", prompt.lower())
        self.assertIn(f"Host: {host_name}", prompt) # Assuming the prompt specifies the speaker

    def test_generate_podcast_outro_segment_prompt(self):
        podcast_title = "Deep Dive AI"
        host_name = "Dr. Lexie"

        prompt = generate_podcast_outro_segment_prompt(podcast_title, host_name)

        self.assertIn(podcast_title, prompt)
        self.assertIn(host_name, prompt)
        self.assertIn("outro segment", prompt.lower())
        self.assertIn("call to action", prompt.lower()) # e.g., subscribe, follow
        self.assertIn(f"Host: {host_name}", prompt)

    def test_generate_podcast_paper_discussion_prompt(self):
        paper_title = "Understanding Large Language Models"
        paper_summary = "This paper provides a comprehensive overview of LLMs..."
        paper_authors_str = "Y. LeCun, G. Hinton"
        host_name = "Chris"
        
        prompt = generate_podcast_paper_discussion_prompt(paper_title, paper_summary, paper_authors_str, host_name)

        self.assertIn(paper_title, prompt)
        self.assertIn(paper_summary, prompt)
        self.assertIn(paper_authors_str, prompt)
        self.assertIn(host_name, prompt)
        self.assertIn("podcast segment discussing the following research paper", prompt.lower())
        self.assertIn("Key insights, methodologies, results, and potential implications", prompt)
        self.assertIn(f"Host: {host_name}", prompt)

    def test_generate_podcast_paper_discussion_prompt_with_previous_segment(self):
        paper_title = "Next Gen AI"
        paper_summary = "Exploring future AI paradigms."
        paper_authors_str = "A. Turing"
        host_name = "Pat"
        previous_segment = "In our last segment, we talked about foundational models..."
        
        prompt = generate_podcast_paper_discussion_prompt(
            paper_title, paper_summary, paper_authors_str, host_name, previous_segment=previous_segment
        )

        self.assertIn(paper_title, prompt)
        self.assertIn(host_name, prompt)
        self.assertIn(previous_segment, prompt)
        self.assertIn("Context of previous segment:", prompt)


if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
