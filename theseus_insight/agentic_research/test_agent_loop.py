import json
import tempfile
import pytest
from unittest.mock import Mock, patch

from ..data_model.data_handling import PaperDatabase
from .agent_loop import ResearchAgentLoop, create_research_agent, LiteratureReviewSummary
from .local_search import LocalSearchTool
from .model_router import AgentModelRouter


class TestResearchAgentLoop:
    """Test cases for ResearchAgentLoop functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_db = Mock(spec=PaperDatabase)
        self.mock_search_tool = Mock(spec=LocalSearchTool)
        self.mock_model_router = Mock(spec=AgentModelRouter)
        
        self.agent = ResearchAgentLoop(
            db=self.mock_db,
            search_tool=self.mock_search_tool,
            model_router=self.mock_model_router,
            num_papers_target=3,
            max_steps=5
        )
    
    def test_command_parsing(self):
        """Test parsing of agent commands."""
        response = """
        I need to search for papers on this topic.
        
        ```SUMMARY transformer language models```
        
        Let me also get the full text of an interesting paper.
        
        ```FULL_TEXT 12345```
        
        And I should add this specific paper.
        
        ```ADD_PAPER https://arxiv.org/abs/2106.04554```
        """
        
        commands = self.agent._parse_agent_commands(response)
        
        expected = [
            ("SUMMARY", "transformer language models"),
            ("FULL_TEXT", "12345"),
            ("ADD_PAPER", "https://arxiv.org/abs/2106.04554")
        ]
        
        assert commands == expected
    
    def test_summary_command_execution(self):
        """Test SUMMARY command execution."""
        self.mock_search_tool.find_papers_by_str.return_value = """
        Paper ID: 123
        Title: Attention Is All You Need
        Abstract: The dominant sequence transduction models are based on complex recurrent...
        Score: 0.95
        
        Paper ID: 456
        Title: BERT: Pre-training of Deep Bidirectional Transformers
        Abstract: We introduce a new language representation model called BERT...
        Score: 0.92
        """
        
        result = self.agent._execute_summary_command("transformer models")
        
        self.mock_search_tool.find_papers_by_str.assert_called_once_with("transformer models", top_k=10)
        assert "Paper ID: 123" in result
        assert "Attention Is All You Need" in result
    
    def test_full_text_command_execution(self):
        """Test FULL_TEXT command execution."""
        self.mock_search_tool.retrieve_full_text.return_value = "This is the full text of the paper..."
        
        result = self.agent._execute_full_text_command("123")
        
        self.mock_search_tool.retrieve_full_text.assert_called_once_with(123)
        assert result == "This is the full text of the paper..."
    
    def test_add_paper_command_execution(self):
        """Test ADD_PAPER command execution."""
        # Test with existing paper ID
        self.mock_db.get_paper_by_id.return_value = {
            "id": 123,
            "title": "Test Paper",
            "abstract": "Test abstract"
        }
        
        result = self.agent._execute_add_paper_command("123")
        
        self.mock_db.get_paper_by_id.assert_called_once_with(123)
        assert "Paper 123 added to consideration" in result
        assert "Test Paper" in result
    
    def test_add_paper_command_with_url(self):
        """Test ADD_PAPER command with URL."""
        self.mock_search_tool.add_paper_from_url.return_value = 456
        self.mock_db.get_paper_by_id.return_value = {
            "id": 456,
            "title": "Downloaded Paper",
            "abstract": "Downloaded abstract"
        }
        
        result = self.agent._execute_add_paper_command("https://arxiv.org/abs/2106.04554")
        
        self.mock_search_tool.add_paper_from_url.assert_called_once_with("https://arxiv.org/abs/2106.04554")
        assert "Successfully downloaded and added paper 456" in result
    
    def test_prompt_building(self):
        """Test agent prompt construction."""
        # Add some existing summaries
        self.agent.collected_summaries = [
            LiteratureReviewSummary(
                paper_id=123,
                title="Test Paper",
                summary="This paper discusses...",
                rationale="Relevant because...",
                relevance_score=0.9
            )
        ]
        
        prompt = self.agent._build_agent_prompt("transformer models in NLP")
        
        assert "transformer models in NLP" in prompt
        assert "step 1" in prompt
        assert "Test Paper" in prompt
        assert "This paper discusses..." in prompt
        assert "Target papers: 3" in prompt
    
    def test_termination_conditions(self):
        """Test that agent terminates correctly."""
        # Mock successful responses
        self.mock_model_router.call_model.return_value = "```COMPLETE```"
        
        # Mock search results
        self.mock_search_tool.find_papers_by_str.return_value = "No papers found"
        
        result = self.agent.run_literature_review("test question")
        
        assert result.research_question == "test question"
        assert result.total_iterations >= 1
        assert len(result.trace_entries) > 0
    
    def test_save_results(self):
        """Test saving results to database."""
        # Create test result
        result = self.agent.run_literature_review("test question")
        result.summaries = [
            LiteratureReviewSummary(
                paper_id=123,
                title="Test Paper",
                summary="Test summary",
                rationale="Test rationale",
                relevance_score=0.9
            )
        ]
        
        self.mock_db.insert_literature_review.return_value = 42
        
        review_id = self.agent.save_results(result)
        
        assert review_id == 42
        self.mock_db.insert_literature_review.assert_called_once()
        
        # Verify the call arguments
        call_args = self.mock_db.insert_literature_review.call_args
        assert call_args[1]["question"] == "test question"
        
        # Verify JSON structure
        summaries_json = json.loads(call_args[1]["summary_json"])
        assert len(summaries_json) == 1
        assert summaries_json[0]["paper_id"] == 123
        assert summaries_json[0]["title"] == "Test Paper"


def test_create_research_agent():
    """Test the factory function for creating research agents."""
    mock_db = Mock(spec=PaperDatabase)
    
    agent = create_research_agent(
        db=mock_db,
        num_papers_target=7,
        max_steps=15,
        enable_pdf_download=False
    )
    
    assert isinstance(agent, ResearchAgentLoop)
    assert agent.num_papers_target == 7
    assert agent.max_steps == 15
    assert isinstance(agent.search_tool, LocalSearchTool)
    assert isinstance(agent.model_router, AgentModelRouter)


def example_usage():
    """Example of how to use the Research Agent Loop."""
    from ..data_model.data_handling import PaperDatabase
    
    # Initialize database connection
    db = PaperDatabase("data/theseus.db")
    
    # Create research agent
    agent = create_research_agent(
        db=db,
        num_papers_target=5,
        max_steps=10,
        enable_pdf_download=True
    )
    
    # Run literature review
    result = agent.run_literature_review(
        "Recent advances in transformer architectures for natural language processing"
    )
    
    # Save results
    if result.success:
        review_id = agent.save_results(result)
        print(f"Literature review completed successfully! Review ID: {review_id}")
        print(f"Found {len(result.summaries)} papers in {result.total_iterations} iterations")
        
        for summary in result.summaries:
            print(f"\nPaper {summary.paper_id}: {summary.title}")
            print(f"Relevance: {summary.relevance_score:.2f}")
            print(f"Summary: {summary.summary}")
    else:
        print(f"Literature review failed: {result.error}")
        print(f"Collected {len(result.summaries)} papers before failure")


if __name__ == "__main__":
    # Run example usage
    example_usage() 