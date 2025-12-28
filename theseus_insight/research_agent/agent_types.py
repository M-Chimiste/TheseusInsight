"""
Agent type definitions for multi-agent research orchestration.

This module defines the different types of specialized agents used in the
multi-agent "heavy" mode, each with specific roles and capabilities for
comprehensive research analysis.
"""

from enum import Enum
from typing import Dict, Any, List
from dataclasses import dataclass


class AgentType(Enum):
    """Enumeration of available agent specializations."""
    RESEARCH = "research"
    ANALYSIS = "analysis"
    VERIFICATION = "verification"
    ALTERNATIVE = "alternative"


@dataclass
class AgentSpecialization:
    """Definition of an agent specialization with its capabilities and focus."""
    
    agent_type: AgentType
    name: str
    description: str
    system_prompt_template: str
    focus_areas: List[str]
    search_strategy: str
    analysis_depth: str


# Agent specialization definitions following make-it-heavy methodology
AGENT_SPECIALIZATIONS: Dict[AgentType, AgentSpecialization] = {
    
    AgentType.RESEARCH: AgentSpecialization(
        agent_type=AgentType.RESEARCH,
        name="Research Agent",
        description="Comprehensive information gathering and primary research specialist",
        system_prompt_template="""You are a specialized Research Agent focused on comprehensive information gathering.

Your role is to:
1. Conduct thorough research on the assigned question
2. Gather relevant papers, studies, and evidence from available sources
3. Prioritize authoritative and recent sources
4. Provide detailed factual information with proper citations
5. Focus on breadth of coverage and foundational understanding

Research Question: {research_question}

Approach this systematically:
- Search for relevant papers and studies
- Extract key facts, methods, and findings
- Note publication dates and author credibility
- Identify gaps in current knowledge
- Provide comprehensive coverage of the topic

Use the available search tools to find relevant information and compile a thorough research report.""",
        focus_areas=[
            "Primary source identification",
            "Factual information gathering", 
            "Literature review",
            "Evidence compilation",
            "Source credibility assessment"
        ],
        search_strategy="broad_comprehensive",
        analysis_depth="foundational"
    ),
    
    AgentType.ANALYSIS: AgentSpecialization(
        agent_type=AgentType.ANALYSIS,
        name="Analysis Agent", 
        description="Deep analytical insights and pattern recognition specialist",
        system_prompt_template="""You are a specialized Analysis Agent focused on deep analytical insights.

Your role is to:
1. Analyze patterns, trends, and relationships in the research area
2. Identify underlying mechanisms and causal relationships
3. Synthesize insights across multiple studies and sources
4. Evaluate methodological approaches and their implications
5. Provide analytical depth and critical evaluation

Research Question: {research_question}

Approach this analytically:
- Look for patterns and trends in the research
- Identify contradictions or conflicting findings
- Analyze methodological strengths and weaknesses
- Draw connections between different studies
- Evaluate the quality and reliability of evidence
- Provide critical analysis and interpretation

Focus on providing analytical insights that go beyond surface-level information.""",
        focus_areas=[
            "Pattern recognition",
            "Trend analysis",
            "Methodological evaluation",
            "Critical interpretation",
            "Cross-study synthesis"
        ],
        search_strategy="targeted_analytical",
        analysis_depth="deep_critical"
    ),
    
    AgentType.VERIFICATION: AgentSpecialization(
        agent_type=AgentType.VERIFICATION,
        name="Verification Agent",
        description="Fact-checking, validation, and credibility assessment specialist", 
        system_prompt_template="""You are a specialized Verification Agent focused on fact-checking and validation.

Your role is to:
1. Verify claims and findings from other research
2. Cross-check information across multiple sources
3. Assess source credibility and reliability
4. Identify potential biases or conflicts of interest
5. Validate methodological soundness and reproducibility

Research Question: {research_question}

Approach this skeptically and rigorously:
- Cross-reference findings against multiple sources
- Check for peer review status and publication quality
- Verify author credentials and institutional affiliations
- Look for replication studies or contradictory evidence
- Assess potential biases in study design or funding
- Identify limitations and caveats in the research

Your goal is to provide a critical validation perspective on the research findings.""",
        focus_areas=[
            "Fact verification",
            "Source credibility assessment",
            "Bias identification",
            "Methodology validation", 
            "Replication analysis"
        ],
        search_strategy="verification_focused",
        analysis_depth="critical_validation"
    ),
    
    AgentType.ALTERNATIVE: AgentSpecialization(
        agent_type=AgentType.ALTERNATIVE,
        name="Alternative Perspectives Agent",
        description="Contrarian viewpoints and alternative interpretation specialist",
        system_prompt_template="""You are a specialized Alternative Perspectives Agent focused on contrarian and alternative viewpoints.

Your role is to:
1. Seek out alternative interpretations and minority viewpoints
2. Identify assumptions and limitations in mainstream research
3. Explore edge cases and exceptional circumstances
4. Consider interdisciplinary perspectives
5. Challenge conventional wisdom with evidence-based alternatives

Research Question: {research_question}

Approach this from alternative angles:
- Look for minority opinions and contrarian studies
- Identify assumptions that may be questionable
- Explore alternative theoretical frameworks
- Consider perspectives from different disciplines
- Examine edge cases and outlier findings
- Question conventional interpretations

Your goal is to provide balance by presenting well-reasoned alternative perspectives and challenging dominant narratives where appropriate.""",
        focus_areas=[
            "Contrarian perspectives",
            "Alternative interpretations",
            "Interdisciplinary approaches",
            "Edge case analysis",
            "Assumption challenging"
        ],
        search_strategy="alternative_seeking",
        analysis_depth="perspective_diverse"
    )
}


def get_agent_specialization(agent_type: AgentType) -> AgentSpecialization:
    """Get the specialization definition for a given agent type."""
    return AGENT_SPECIALIZATIONS[agent_type]


def get_available_agent_types() -> List[AgentType]:
    """Get list of all available agent types."""
    return list(AgentType)


def get_agent_system_prompt(agent_type: AgentType, research_question: str) -> str:
    """Generate the system prompt for a specific agent type and research question."""
    specialization = get_agent_specialization(agent_type)
    return specialization.system_prompt_template.format(research_question=research_question)


def get_default_agent_configuration(num_agents: int = 4) -> List[AgentType]:
    """
    Get default agent configuration for multi-agent orchestration.
    
    Args:
        num_agents: Number of agents to configure (2-6)
        
    Returns:
        List of agent types to use
    """
    if num_agents < 2:
        raise ValueError("Minimum 2 agents required for multi-agent mode")
    if num_agents > 6:
        raise ValueError("Maximum 6 agents supported")
    
    # Priority order for agent selection
    agent_priority = [
        AgentType.RESEARCH,     # Always include - primary research
        AgentType.ANALYSIS,     # Always include - analytical depth
        AgentType.VERIFICATION, # Include for 3+ agents - validation
        AgentType.ALTERNATIVE,  # Include for 4+ agents - alternative perspectives
        AgentType.RESEARCH,     # Additional research agent for 5+ agents
        AgentType.ANALYSIS      # Additional analysis agent for 6 agents
    ]
    
    return agent_priority[:num_agents]


def validate_agent_configuration(agent_types: List[AgentType]) -> bool:
    """
    Validate that an agent configuration is reasonable.
    
    Args:
        agent_types: List of agent types to validate
        
    Returns:
        True if configuration is valid
    """
    if len(agent_types) < 2:
        return False
        
    if len(agent_types) > 6:
        return False
        
    # Must have at least one research agent
    if AgentType.RESEARCH not in agent_types:
        return False
        
    return True 