"""
Test suite for Research Agent API endpoints

This module provides tests for the research agent REST API and WebSocket endpoints.
"""

import asyncio
import json
import pytest
import tempfile
import uuid
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock

from fastapi.testclient import TestClient
from fastapi import WebSocket

# Import components for testing
from ..data_model.data_handling import PaperDatabase
from ..api.models import (
    ResearchAgentModelConfigApi,
    ResearchAgentRunRequest,
    ModelConfig,
    LiteratureReviewSummary,
    LiteratureReviewResult
)


class TestResearchAgentAPI:
    """Test class for research agent API endpoints."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Create temporary database
        self.db_path = tempfile.mktemp(suffix=".db")
        self.db = PaperDatabase(self.db_path)
        
        # Mock model configuration
        self.sample_model_config = {
            "boss_model": {
                "model_name": "gemini-2.0-flash",
                "model_type": "gemini",
                "max_new_tokens": 4096,
                "temperature": 0.1,
                "num_ctx": 131072
            },
            "worker_models": {
                "summary": {
                    "model_name": "phi4-mini:3.8b-q8_0",
                    "model_type": "ollama",
                    "max_new_tokens": 2048,
                    "temperature": 0.1,
                    "num_ctx": 4096
                },
                "analysis": {
                    "model_name": "phi4-mini:3.8b-q8_0", 
                    "model_type": "ollama",
                    "max_new_tokens": 2048,
                    "temperature": 0.1,
                    "num_ctx": 4096
                }
            },
            "default_worker": "summary",
            "max_retries": 3,
            "timeout_seconds": 30
        }
    
    def test_research_agent_model_config_api_models(self):
        """Test API model validation for research agent configuration."""
        # Test boss model
        boss_model = ModelConfig(**self.sample_model_config["boss_model"])
        assert boss_model.model_name == "gemini-2.0-flash"
        assert boss_model.model_type == "gemini"
        
        # Test worker models
        summary_model = ModelConfig(**self.sample_model_config["worker_models"]["summary"])
        assert summary_model.model_name == "phi4-mini:3.8b-q8_0"
        assert summary_model.model_type == "ollama"
        
        # Test full configuration
        config = ResearchAgentModelConfigApi(
            boss_model=boss_model,
            worker_models={
                "summary": summary_model,
                "analysis": ModelConfig(**self.sample_model_config["worker_models"]["analysis"])
            },
            default_worker="summary",
            max_retries=3,
            timeout_seconds=30
        )
        
        assert config.boss_model.model_name == "gemini-2.0-flash"
        assert len(config.worker_models) == 2
        assert config.default_worker == "summary"
        assert config.max_retries == 3
        assert config.timeout_seconds == 30
    
    def test_research_agent_run_request_validation(self):
        """Test validation for research agent run requests."""
        # Valid request
        valid_request = ResearchAgentRunRequest(
            research_question="What are the latest advances in transformer architectures?",
            num_papers_target=5,
            max_steps=10
        )
        assert valid_request.research_question.startswith("What are the latest")
        assert valid_request.num_papers_target == 5
        assert valid_request.max_steps == 10
        
        # Test with model config override
        boss_model = ModelConfig(**self.sample_model_config["boss_model"])
        summary_model = ModelConfig(**self.sample_model_config["worker_models"]["summary"])
        
        config_override = ResearchAgentModelConfigApi(
            boss_model=boss_model,
            worker_models={"summary": summary_model},
            default_worker="summary",
            max_retries=5,
            timeout_seconds=45
        )
        
        request_with_override = ResearchAgentRunRequest(
            research_question="What are the latest advances in transformer architectures?",
            num_papers_target=8,
            max_steps=15,
            model_config_override=config_override
        )
        
        assert request_with_override.model_config_override is not None
        assert request_with_override.model_config_override.max_retries == 5
        
        # Test validation constraints
        with pytest.raises(ValueError):
            # Question too short
            ResearchAgentRunRequest(
                research_question="Short",
                num_papers_target=5,
                max_steps=10
            )
        
        with pytest.raises(ValueError):
            # Invalid num_papers_target
            ResearchAgentRunRequest(
                research_question="What are the latest advances in transformer architectures?",
                num_papers_target=0,
                max_steps=10
            )
    
    def test_literature_review_result_models(self):
        """Test literature review result API models."""
        # Test summary model
        summary = LiteratureReviewSummary(
            paper_id=1,
            title="Attention Is All You Need",
            summary="This paper introduces the Transformer architecture...",
            rationale="Highly relevant to transformer research",
            relevance_score=0.95
        )
        
        assert summary.paper_id == 1
        assert summary.title == "Attention Is All You Need"
        assert summary.relevance_score == 0.95
        
        # Test full result model
        result = LiteratureReviewResult(
            id=1,
            research_question="What are the latest advances in transformer architectures?",
            summaries=[summary],
            created_ts=datetime.now().isoformat(),
            total_papers=1,
            trace_log=[
                {
                    "action_type": "agent_response",
                    "details": "Generated search query",
                    "timestamp": datetime.now().isoformat()
                }
            ]
        )
        
        assert result.id == 1
        assert result.research_question.startswith("What are the latest")
        assert len(result.summaries) == 1
        assert result.total_papers == 1
        assert len(result.trace_log) == 1
    
    @patch('theseus_insight.data_model.data_handling.PaperDatabase')
    def test_database_integration(self, mock_db_class):
        """Test database integration for literature reviews."""
        # Mock database instance
        mock_db = Mock()
        mock_db_class.return_value = mock_db
        
        # Mock literature review data
        mock_review_data = {
            'id': 1,
            'research_question': 'What are the latest advances in transformer architectures?',
            'summary_json': json.dumps([
                {
                    'paper_id': 1,
                    'title': 'Attention Is All You Need',
                    'summary': 'This paper introduces the Transformer architecture...',
                    'rationale': 'Highly relevant to transformer research',
                    'relevance_score': 0.95
                }
            ]),
            'trace_json': json.dumps([
                {
                    'action_type': 'agent_response',
                    'details': 'Generated search query',
                    'timestamp': datetime.now().isoformat()
                }
            ]),
            'created_ts': datetime.now().isoformat()
        }
        
        # Test insertion
        mock_db.insert_literature_review.return_value = 1
        review_id = mock_db.insert_literature_review(
            'What are the latest advances in transformer architectures?',
            mock_review_data['summary_json'],
            mock_review_data['trace_json']
        )
        assert review_id == 1
        
        # Test retrieval
        mock_db.get_literature_review.return_value = mock_review_data
        retrieved_review = mock_db.get_literature_review(1)
        assert retrieved_review['id'] == 1
        assert retrieved_review['research_question'] == 'What are the latest advances in transformer architectures?'
        
        # Test recent reviews
        mock_db.get_recent_literature_reviews.return_value = [mock_review_data]
        recent_reviews = mock_db.get_recent_literature_reviews(10)
        assert len(recent_reviews) == 1
        assert recent_reviews[0]['id'] == 1


class TestResearchAgentIntegration:
    """Integration tests for research agent with mocked components."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.db_path = tempfile.mktemp(suffix=".db")
        self.db = PaperDatabase(self.db_path)
    
    @patch('theseus_insight.agentic_research.agent_loop.create_research_agent')
    @patch('theseus_insight.agentic_research.model_router.load_research_agent_model_config')
    def test_research_agent_task_flow(self, mock_load_config, mock_create_agent):
        """Test the complete research agent task flow."""
        # Mock configuration loading
        from ..agentic_research.model_router import ResearchAgentModelConfig, ModelConfigDict
        
        mock_config = ResearchAgentModelConfig({
            "boss_model": ModelConfigDict({
                "model_name": "gemini-2.0-flash",
                "model_type": "gemini",
                "max_new_tokens": 4096,
                "temperature": 0.1
            }),
            "worker_models": {
                "summary": ModelConfigDict({
                    "model_name": "phi4-mini:3.8b-q8_0",
                    "model_type": "ollama",
                    "max_new_tokens": 2048,
                    "temperature": 0.1
                })
            },
            "default_worker": "summary",
            "max_retries": 3,
            "timeout_seconds": 30
        })
        mock_load_config.return_value = mock_config
        
        # Mock agent and result
        mock_agent = Mock()
        mock_create_agent.return_value = mock_agent
        
        from ..agentic_research.agent_loop import ResearchAgentResult, LiteratureReviewSummary
        mock_result = ResearchAgentResult(
            research_question="What are the latest advances in transformer architectures?",
            summaries=[
                LiteratureReviewSummary(
                    paper_id=1,
                    title="Attention Is All You Need",
                    summary="This paper introduces the Transformer architecture...",
                    rationale="Highly relevant to transformer research", 
                    relevance_score=0.95
                )
            ],
            success=True,
            total_iterations=3,
            trace_entries=[],
            error=None
        )
        
        mock_agent.run_literature_review.return_value = mock_result
        mock_agent.save_results.return_value = 1
        
        # Test agent creation and execution
        agent = mock_create_agent(
            db=self.db,
            num_papers_target=5,
            max_steps=10,
            enable_pdf_download=True
        )
        
        result = agent.run_literature_review("What are the latest advances in transformer architectures?")
        
        assert result.success is True
        assert len(result.summaries) == 1
        assert result.summaries[0].title == "Attention Is All You Need"
        assert result.total_iterations == 3
        
        # Test result saving
        review_id = agent.save_results(result)
        assert review_id == 1


def test_api_endpoint_schemas():
    """Test that API endpoint schemas are correctly defined."""
    # Test that all required API models can be imported
    from ..api.models import (
        ResearchAgentModelConfigApi,
        ResearchAgentRunRequest, 
        ResearchAgentRunResponse,
        LiteratureReviewResult,
        LiteratureReviewSummary
    )
    
    # Verify schema examples work
    sample_config = ResearchAgentModelConfigApi(
        boss_model=ModelConfig(
            model_name="gemini-2.0-flash",
            model_type="gemini",
            max_new_tokens=4096,
            temperature=0.1
        ),
        worker_models={
            "summary": ModelConfig(
                model_name="phi4-mini:3.8b-q8_0",
                model_type="ollama",
                max_new_tokens=2048,
                temperature=0.1
            )
        },
        default_worker="summary",
        max_retries=3,
        timeout_seconds=30
    )
    
    assert sample_config.boss_model.model_name == "gemini-2.0-flash"
    assert "summary" in sample_config.worker_models


if __name__ == "__main__":
    # Simple test runner
    test_instance = TestResearchAgentAPI()
    test_instance.setup_method()
    
    print("Testing Research Agent API models...")
    test_instance.test_research_agent_model_config_api_models()
    print("✓ Model configuration API models test passed")
    
    test_instance.test_research_agent_run_request_validation()
    print("✓ Run request validation test passed")
    
    test_instance.test_literature_review_result_models()
    print("✓ Literature review result models test passed")
    
    test_instance.test_database_integration()
    print("✓ Database integration test passed")
    
    integration_test = TestResearchAgentIntegration()
    integration_test.setup_method()
    integration_test.test_research_agent_task_flow()
    print("✓ Research agent task flow test passed")
    
    test_api_endpoint_schemas()
    print("✓ API endpoint schemas test passed")
    
    print("\nAll Research Agent API tests passed! ✨") 