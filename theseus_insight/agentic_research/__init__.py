"""
Agentic Research Module

This module provides automated literature review capabilities with local-first search
and optional external expansion. It follows the PRD specifications for the Research Agent.
"""

from .local_search import LocalSearchTool, BaseSearchTool
from .model_router import (
    AgentModelRouter, 
    ResearchAgentModelConfig, 
    ModelRole,
    load_research_agent_model_config,
    save_research_agent_model_config
)

__all__ = [
    'LocalSearchTool', 
    'BaseSearchTool',
    'AgentModelRouter', 
    'ResearchAgentModelConfig', 
    'ModelRole',
    'load_research_agent_model_config',
    'save_research_agent_model_config'
] 