"""
Agentic Research Module

This module provides automated literature review capabilities with local-first search
and optional external expansion. It follows the PRD specifications for the Research Agent.

The module uses a LangGraph-based workflow for enhanced research capabilities.
"""

# Core search functionality
from .local_search import LocalSearchTool, BaseSearchTool

# LangGraph-based research agent
from .research_graph import ResearchAgent, create_research_agent
from .graph_configuration import AgentConfiguration
from .graph_state import OverallState, ReflectionState, QueryGenerationState, WebSearchState
from .unified_model_router import UnifiedModelRouter, load_unified_router

# External search integration
from .external_search import ExternalSearchTool

__all__ = [
    # Search tools
    'LocalSearchTool', 
    'BaseSearchTool',
    
    # LangGraph exports
    'ResearchAgent',
    'create_research_agent', 
    'AgentConfiguration',
    'OverallState',
    'ReflectionState', 
    'QueryGenerationState',
    'WebSearchState',
    'UnifiedModelRouter',
    'load_unified_router',
    
    # External search
    'ExternalSearchTool',
] 