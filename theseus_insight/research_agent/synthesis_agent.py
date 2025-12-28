"""
Synthesis agent for multi-agent research orchestration.

This module provides intelligent synthesis of multiple agent responses into 
a comprehensive, coherent final answer that leverages all perspectives and
resolves any conflicts between agent findings.
"""

import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from .agent_manager import AgentResult
from .agent_types import AgentType, get_agent_specialization
from .model_router import get_model

logger = logging.getLogger(__name__)


@dataclass
class ConflictIdentification:
    """Represents a conflict between agent responses."""
    conflict_type: str  # "factual", "methodological", "interpretative"
    agents_involved: List[int]
    conflicting_claims: List[str]
    severity: str  # "low", "medium", "high"
    resolution_strategy: str


@dataclass
class SynthesisMetadata:
    """Metadata about the synthesis process."""
    total_agents: int
    successful_agents: int
    failed_agents: int
    conflicts_identified: int
    conflicts_resolved: int
    synthesis_strategy: str
    confidence_score: float
    sources_integrated: int


@dataclass
class SynthesisResult:
    """Result of the synthesis process."""
    final_answer: str
    generation_summary: str
    agent_contributions: Dict[int, str]  # agent_id -> contribution summary
    conflicts_found: List[ConflictIdentification]
    metadata: SynthesisMetadata
    success: bool
    error_message: Optional[str] = None


class SynthesisAgent:
    """
    Synthesis agent that combines multiple agent responses into a 
    comprehensive, coherent final answer.
    
    Responsibilities:
    1. Analyze all agent responses for quality and relevance
    2. Identify conflicts and inconsistencies between responses
    3. Develop resolution strategies for conflicts
    4. Synthesize information into a unified, comprehensive answer
    5. Provide metadata about the synthesis process
    """
    
    def __init__(self, model_config: Dict[str, Any]):
        """
        Initialize the synthesis agent.
        
        Args:
            model_config: Configuration for the LLM model to use
        """
        self.model_config = model_config
        self.model = get_model("synthesis_agent", model_config)
        
    async def synthesize_responses(
        self,
        original_question: str,
        agent_results: List[AgentResult],
        synthesis_config: Optional[Dict[str, Any]] = None
    ) -> SynthesisResult:
        """
        Synthesize multiple agent responses into a comprehensive final answer.
        
        Args:
            original_question: The original research question
            agent_results: Results from all agents
            synthesis_config: Optional configuration for synthesis process
            
        Returns:
            SynthesisResult with final answer and metadata
        """
        
        logger.info(f"Starting synthesis of {len(agent_results)} agent responses")
        
        try:
            # Filter successful agent results
            successful_results = [r for r in agent_results if r.success]
            failed_results = [r for r in agent_results if not r.success]
            
            if not successful_results:
                return self._create_failed_synthesis(
                    "No successful agent responses to synthesize",
                    agent_results
                )
            
            # Step 1: Analyze agent responses
            response_analysis = await self._analyze_agent_responses(successful_results)
            
            # Step 2: Identify conflicts
            conflicts = await self._identify_conflicts(successful_results)
            
            # Step 3: Develop synthesis strategy
            synthesis_strategy = self._determine_synthesis_strategy(
                successful_results, conflicts, synthesis_config
            )
            
            # Step 4: Generate final answer
            final_answer = await self._generate_final_answer(
                original_question,
                successful_results,
                conflicts,
                synthesis_strategy
            )
            
            # Step 5: Create synthesis metadata
            metadata = self._create_synthesis_metadata(
                agent_results, successful_results, failed_results,
                conflicts, synthesis_strategy
            )
            
            # Step 6: Generate summary
            generation_summary = self._generate_synthesis_summary(
                successful_results, conflicts, metadata
            )
            
            return SynthesisResult(
                final_answer=final_answer,
                generation_summary=generation_summary,
                agent_contributions=self._extract_agent_contributions(successful_results),
                conflicts_found=conflicts,
                metadata=metadata,
                success=True
            )
            
        except Exception as e:
            logger.error(f"Synthesis failed: {e}")
            return self._create_failed_synthesis(str(e), agent_results)
    
    async def _analyze_agent_responses(
        self, 
        agent_results: List[AgentResult]
    ) -> Dict[str, Any]:
        """Analyze the quality and characteristics of agent responses."""
        
        analysis = {
            "response_lengths": [],
            "source_counts": [],
            "agent_types": {},
            "quality_scores": {}
        }
        
        for result in agent_results:
            # Basic metrics
            analysis["response_lengths"].append(len(result.response.split()))
            analysis["source_counts"].append(len(result.sources_gathered))
            
            # Agent type distribution
            agent_type = result.agent_type.value
            if agent_type not in analysis["agent_types"]:
                analysis["agent_types"][agent_type] = 0
            analysis["agent_types"][agent_type] += 1
            
            # Simple quality scoring based on response length and sources
            quality_score = min(1.0, len(result.response.split()) / 200) * 0.7
            quality_score += min(1.0, len(result.sources_gathered) / 10) * 0.3
            analysis["quality_scores"][result.agent_id] = quality_score
        
        return analysis
    
    async def _identify_conflicts(
        self, 
        agent_results: List[AgentResult]
    ) -> List[ConflictIdentification]:
        """Identify conflicts and inconsistencies between agent responses."""
        
        if len(agent_results) < 2:
            return []
        
        # Use LLM to identify conflicts
        conflict_prompt = self._build_conflict_identification_prompt(agent_results)
        
        try:
            response = await self._call_model(conflict_prompt)
            conflicts = self._parse_conflict_response(response)
            return conflicts
        except Exception as e:
            logger.warning(f"Conflict identification failed: {e}")
            return []
    
    def _build_conflict_identification_prompt(
        self, 
        agent_results: List[AgentResult]
    ) -> str:
        """Build prompt for conflict identification."""
        
        agent_responses = []
        for result in agent_results:
            specialization = get_agent_specialization(result.agent_type)
            agent_responses.append(
                f"**Agent {result.agent_id} ({specialization.name})**:\n{result.response}"
            )
        
        responses_text = "\n\n---\n\n".join(agent_responses)
        
        return f"""You are a Conflict Analysis Agent. Your task is to identify conflicts, contradictions, or inconsistencies between different agent responses.

Agent Responses:
{responses_text}

Please analyze these responses and identify any conflicts. Look for:
1. **Factual Conflicts**: Direct contradictions about facts, data, or findings
2. **Methodological Conflicts**: Disagreements about research methods or validity
3. **Interpretative Conflicts**: Different interpretations of the same evidence

For each conflict found, provide:
- Type: factual/methodological/interpretative
- Agents involved: List of agent IDs
- Conflicting claims: The specific contradictory statements
- Severity: low/medium/high based on impact on final answer

Output your analysis as JSON:
{{
    "conflicts": [
        {{
            "type": "factual|methodological|interpretative",
            "agents_involved": [1, 2],
            "conflicting_claims": ["claim 1", "claim 2"],
            "severity": "low|medium|high"
        }}
    ],
    "analysis_summary": "Brief summary of conflict analysis"
}}

If no conflicts are found, return an empty conflicts array."""
    
    def _parse_conflict_response(self, response: str) -> List[ConflictIdentification]:
        """Parse the conflict identification response."""
        
        try:
            data = json.loads(response.strip())
            conflicts = []
            
            for conflict_data in data.get("conflicts", []):
                conflict = ConflictIdentification(
                    conflict_type=conflict_data.get("type", "unknown"),
                    agents_involved=conflict_data.get("agents_involved", []),
                    conflicting_claims=conflict_data.get("conflicting_claims", []),
                    severity=conflict_data.get("severity", "medium"),
                    resolution_strategy=self._determine_conflict_resolution_strategy(
                        conflict_data.get("type", "unknown"),
                        conflict_data.get("severity", "medium")
                    )
                )
                conflicts.append(conflict)
            
            return conflicts
            
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to parse conflict response: {e}")
            return []
    
    def _determine_conflict_resolution_strategy(
        self, 
        conflict_type: str, 
        severity: str
    ) -> str:
        """Determine strategy for resolving a specific conflict."""
        
        if conflict_type == "factual":
            if severity == "high":
                return "evidence_based_arbitration"
            else:
                return "source_credibility_weighting"
        elif conflict_type == "methodological":
            return "methodological_transparency"
        elif conflict_type == "interpretative":
            return "perspective_integration"
        else:
            return "balanced_presentation"
    
    def _determine_synthesis_strategy(
        self,
        agent_results: List[AgentResult],
        conflicts: List[ConflictIdentification],
        synthesis_config: Optional[Dict[str, Any]]
    ) -> str:
        """Determine the overall synthesis strategy."""
        
        config = synthesis_config or {}
        
        # Check for user-specified strategy
        if "strategy" in config:
            return config["strategy"]
        
        # Determine strategy based on results and conflicts
        if len(conflicts) == 0:
            return "consensus_integration"
        elif len(conflicts) <= 2 and all(c.severity in ["low", "medium"] for c in conflicts):
            return "weighted_consensus"
        elif len(conflicts) > 2 or any(c.severity == "high" for c in conflicts):
            return "evidence_based_arbitration"
        else:
            return "perspective_synthesis"
    
    async def _generate_final_answer(
        self,
        original_question: str,
        agent_results: List[AgentResult],
        conflicts: List[ConflictIdentification],
        synthesis_strategy: str
    ) -> str:
        """Generate the final synthesized answer."""
        
        synthesis_prompt = self._build_synthesis_prompt(
            original_question, agent_results, conflicts, synthesis_strategy
        )
        
        response = await self._call_model(synthesis_prompt)
        return response
    
    def _build_synthesis_prompt(
        self,
        original_question: str,
        agent_results: List[AgentResult],
        conflicts: List[ConflictIdentification],
        synthesis_strategy: str
    ) -> str:
        """Build the main synthesis prompt."""
        
        # Build agent responses section
        agent_responses = []
        for result in agent_results:
            specialization = get_agent_specialization(result.agent_type)
            agent_responses.append(
                f"=== {specialization.name} (Agent {result.agent_id}) ===\n"
                f"Research Question: {result.question}\n"
                f"Response: {result.response}\n"
                f"Sources: {len(result.sources_gathered)} sources found"
            )
        
        responses_text = "\n\n".join(agent_responses)
        
        # Build conflicts section
        conflicts_text = ""
        if conflicts:
            conflict_descriptions = []
            for i, conflict in enumerate(conflicts):
                conflict_descriptions.append(
                    f"Conflict {i+1} ({conflict.conflict_type}, {conflict.severity} severity):\n"
                    f"- Agents involved: {conflict.agents_involved}\n"
                    f"- Conflicting claims: {conflict.conflicting_claims}\n"
                    f"- Resolution strategy: {conflict.resolution_strategy}"
                )
            conflicts_text = "\n\n".join(conflict_descriptions)
        
        # Build strategy instructions
        strategy_instructions = self._get_strategy_instructions(synthesis_strategy)
        
        return f"""You are a Synthesis Agent responsible for creating a comprehensive final answer by combining multiple specialized research perspectives.

Original Research Question: {original_question}

Agent Responses:
{responses_text}

{"Identified Conflicts:" if conflicts else "No conflicts identified."}
{conflicts_text}

Synthesis Strategy: {synthesis_strategy}
{strategy_instructions}

Instructions:
1. Create a comprehensive answer that addresses the original research question
2. Integrate insights from all agent perspectives where possible
3. Address any conflicts using the specified resolution strategies
4. Maintain academic rigor and cite evidence appropriately
5. Provide a balanced, well-structured response
6. If conflicts cannot be resolved, present multiple perspectives clearly

Your final answer should be thorough, coherent, and demonstrate the value of the multi-agent approach by incorporating diverse perspectives into a unified response.

Final Answer:"""
    
    def _get_strategy_instructions(self, strategy: str) -> str:
        """Get specific instructions for the synthesis strategy."""
        
        instructions = {
            "consensus_integration": """
- Integrate all agent perspectives into a unified narrative
- Emphasize areas of agreement and consensus
- Build upon complementary insights from different agents
            """,
            
            "weighted_consensus": """
- Weight agent contributions based on their expertise and evidence quality
- Resolve minor conflicts by favoring more credible or better-supported claims
- Integrate perspectives with appropriate emphasis on stronger evidence
            """,
            
            "evidence_based_arbitration": """
- Carefully evaluate conflicting claims based on evidence quality
- Prioritize peer-reviewed sources and authoritative research
- When conflicts cannot be resolved, present multiple perspectives with their evidence
- Be transparent about uncertainties and limitations
            """,
            
            "perspective_synthesis": """
- Present the research question from multiple analytical angles
- Showcase how different approaches complement each other
- Integrate insights while preserving the unique value of each perspective
- Create a comprehensive view that is richer than any single perspective
            """
        }
        
        return instructions.get(strategy, instructions["perspective_synthesis"])
    
    async def _call_model(self, prompt: str) -> str:
        """Call the LLM model with the given prompt."""
        
        try:
            # Fix model invocation - use messages and system_prompt instead of prompt
            messages = [{"role": "user", "content": prompt}]
            response = self.model.invoke(
                messages=messages,
                system_prompt="You are a research synthesis agent that combines multiple research perspectives into comprehensive analyses.",
                schema=None
            )
            # ModelClient.invoke() returns a string directly, not an object with .content
            return response
        except Exception as e:
            logger.error(f"Model call failed: {e}")
            raise
    
    def _create_synthesis_metadata(
        self,
        all_results: List[AgentResult],
        successful_results: List[AgentResult],
        failed_results: List[AgentResult],
        conflicts: List[ConflictIdentification],
        synthesis_strategy: str
    ) -> SynthesisMetadata:
        """Create metadata about the synthesis process."""
        
        # Calculate confidence score
        confidence_factors = []
        
        # Success rate factor
        success_rate = len(successful_results) / len(all_results) if all_results else 0
        confidence_factors.append(success_rate)
        
        # Conflict resolution factor
        if conflicts:
            resolved_conflicts = len([c for c in conflicts if c.severity in ["low", "medium"]])
            conflict_factor = resolved_conflicts / len(conflicts)
        else:
            conflict_factor = 1.0
        confidence_factors.append(conflict_factor)
        
        # Source diversity factor
        total_sources = sum(len(r.sources_gathered) for r in successful_results)
        source_factor = min(1.0, total_sources / (len(successful_results) * 5))
        confidence_factors.append(source_factor)
        
        confidence_score = sum(confidence_factors) / len(confidence_factors)
        
        return SynthesisMetadata(
            total_agents=len(all_results),
            successful_agents=len(successful_results),
            failed_agents=len(failed_results),
            conflicts_identified=len(conflicts),
            conflicts_resolved=len([c for c in conflicts if c.severity in ["low", "medium"]]),
            synthesis_strategy=synthesis_strategy,
            confidence_score=confidence_score,
            sources_integrated=total_sources
        )
    
    def _generate_synthesis_summary(
        self,
        successful_results: List[AgentResult],
        conflicts: List[ConflictIdentification],
        metadata: SynthesisMetadata
    ) -> str:
        """Generate a summary of the synthesis process."""
        
        summary_parts = []
        
        # Basic statistics
        summary_parts.append(
            f"Synthesized responses from {metadata.successful_agents} specialized agents "
            f"using {metadata.synthesis_strategy} strategy."
        )
        
        # Agent types involved
        agent_types = [get_agent_specialization(r.agent_type).name for r in successful_results]
        unique_types = list(set(agent_types))
        summary_parts.append(f"Agent specializations: {', '.join(unique_types)}.")
        
        # Conflict handling
        if conflicts:
            summary_parts.append(
                f"Identified and addressed {len(conflicts)} conflict(s) between agent perspectives."
            )
        else:
            summary_parts.append("No conflicts identified between agent responses.")
        
        # Source integration
        summary_parts.append(f"Integrated evidence from {metadata.sources_integrated} sources.")
        
        # Confidence assessment
        confidence_level = "high" if metadata.confidence_score > 0.8 else "medium" if metadata.confidence_score > 0.6 else "moderate"
        summary_parts.append(f"Synthesis confidence: {confidence_level}.")
        
        return " ".join(summary_parts)
    
    def _extract_agent_contributions(
        self, 
        agent_results: List[AgentResult]
    ) -> Dict[int, str]:
        """Extract a summary of each agent's contribution."""
        
        contributions = {}
        
        for result in agent_results:
            specialization = get_agent_specialization(result.agent_type)
            
            # Create a brief summary of the agent's contribution
            contribution = (
                f"{specialization.name} provided {specialization.description.lower()} "
                f"with {len(result.sources_gathered)} sources. "
                f"Focus: {result.metadata.get('specialization_focus', 'General research')}."
            )
            
            contributions[result.agent_id] = contribution
        
        return contributions
    
    def _create_failed_synthesis(
        self, 
        error_message: str, 
        agent_results: List[AgentResult]
    ) -> SynthesisResult:
        """Create a failed synthesis result."""
        
        # Try to provide some fallback answer from successful agents
        successful_results = [r for r in agent_results if r.success]
        
        if successful_results:
            # Simple concatenation fallback
            fallback_parts = []
            for result in successful_results:
                specialization = get_agent_specialization(result.agent_type)
                fallback_parts.append(f"**{specialization.name}**: {result.response}")
            
            fallback_answer = "\n\n".join(fallback_parts)
            fallback_summary = f"Synthesis failed ({error_message}). Providing individual agent responses."
        else:
            fallback_answer = f"All agents failed to provide responses. Error: {error_message}"
            fallback_summary = "Complete synthesis failure - no agent responses available."
        
        metadata = SynthesisMetadata(
            total_agents=len(agent_results),
            successful_agents=len(successful_results),
            failed_agents=len(agent_results) - len(successful_results),
            conflicts_identified=0,
            conflicts_resolved=0,
            synthesis_strategy="fallback",
            confidence_score=0.0,
            sources_integrated=sum(len(r.sources_gathered) for r in successful_results)
        )
        
        return SynthesisResult(
            final_answer=fallback_answer,
            generation_summary=fallback_summary,
            agent_contributions=self._extract_agent_contributions(successful_results),
            conflicts_found=[],
            metadata=metadata,
            success=False,
            error_message=error_message
        ) 