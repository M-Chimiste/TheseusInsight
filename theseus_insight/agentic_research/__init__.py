"""
Agentic Research Module

This module provides automated literature review capabilities with local-first search
and optional external expansion. It follows the PRD specifications for the Research Agent.

The module now includes both the legacy agent loop implementation and the new 
LangGraph-based workflow for enhanced research capabilities.
"""

# Legacy imports (maintained for backward compatibility)
from .local_search import LocalSearchTool, BaseSearchTool
from .model_router import (
    AgentModelRouter, 
    ResearchAgentModelConfig, 
    ModelRole,
    load_research_agent_model_config,
    save_research_agent_model_config
)

# New LangGraph-based research agent
from .research_graph import ResearchAgent, create_research_agent
from .graph_configuration import AgentConfiguration
from .graph_state import OverallState, ReflectionState, QueryGenerationState, WebSearchState
from .graph_model_router import GraphModelRouter, load_model_router

# External search integration
from .external_search import ExternalSearchTool

__all__ = [
    # Legacy exports
    'LocalSearchTool', 
    'BaseSearchTool',
    'AgentModelRouter', 
    'ResearchAgentModelConfig', 
    'ModelRole',
    'load_research_agent_model_config',
    'save_research_agent_model_config',
    
    # New LangGraph exports
    'ResearchAgent',
    'create_research_agent', 
    'AgentConfiguration',
    'OverallState',
    'ReflectionState', 
    'QueryGenerationState',
    'WebSearchState',
    'GraphModelRouter',
    'load_model_router',
    
    # External search
    'ExternalSearchTool',
] 