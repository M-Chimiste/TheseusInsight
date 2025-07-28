"""
Question generation system for multi-agent research orchestration.

This module provides AI-powered question decomposition that takes a user's research
question and generates specialized sub-questions tailored for different agent types,
following the make-it-heavy methodology.
"""

import json
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from pydantic import BaseModel, Field, ValidationError

from .agent_types import AgentType, get_agent_specialization
from .model_router import get_model, supports_structured_output

logger = logging.getLogger(__name__)


@dataclass
class GeneratedQuestion:
    """A generated question for a specific agent."""
    agent_id: int
    agent_type: AgentType
    question: str
    specialization_focus: str
    search_strategy: str


@dataclass
class QuestionGenerationResult:
    """Result of question generation process."""
    original_question: str
    generated_questions: List[GeneratedQuestion]
    generation_reasoning: str
    success: bool
    error_message: Optional[str] = None


# -------------------- Structured Output Schemas --------------------

# These Pydantic models describe the expected JSON shape when the model
# supports direct structured output (e.g., Ollama / LlamaCPP).

class _QItem(BaseModel):
    agent_type: str
    question: str
    focus: str


class _QResponse(BaseModel):
    reasoning: str
    questions: List[_QItem]


class QuestionGenerator:
    """
    AI-powered question generation for multi-agent research orchestration.
    
    Takes a user's research question and decomposes it into specialized questions
    tailored for different agent types (research, analysis, verification, alternative).
    """
    
    def __init__(self, model_config: Dict[str, Any]):
        """
        Initialize the question generator.
        
        Args:
            model_config: Configuration for the LLM model to use
        """
        self.model_config = model_config
        self.model = get_model("question_generator", model_config)
        
    async def generate_questions(
        self, 
        research_question: str, 
        agent_types: List[AgentType],
        context: Optional[Dict[str, Any]] = None
    ) -> QuestionGenerationResult:
        """
        Generate specialized questions for each agent type.
        
        Args:
            research_question: The original user research question
            agent_types: List of agent types to generate questions for
            context: Optional context about the research domain or constraints
            
        Returns:
            QuestionGenerationResult with generated questions and metadata
        """
        try:
            # Build the prompt for question generation
            system_prompt = self._build_question_generation_prompt(agent_types, context)
            user_prompt = self._build_user_prompt(research_question, agent_types)
            
            # Generate questions using the LLM - fix model invocation
            messages = [{"role": "user", "content": user_prompt}]

            # Decide whether to request structured output directly
            schema_to_use = _QResponse if supports_structured_output(self.model.provider) else None
            response = self.model.invoke(
                messages=messages,
                system_prompt=system_prompt,
                schema=schema_to_use
            )

            # -----------------------------------------------------------------
            # Handle structured or unstructured response
            # -----------------------------------------------------------------
            if isinstance(response, BaseModel):
                response_content: Dict[str, Any] = response.model_dump()
                questions = self._parse_question_response_dict(response_content, agent_types)
            else:
                # Parse the response string
                questions = self._parse_question_response_str(str(response), agent_types)

            return QuestionGenerationResult(
                original_question=research_question,
                generated_questions=questions,
                generation_reasoning="Successfully generated specialized questions for multi-agent research",
                success=True
            )
            
        except Exception as e:
            logger.error(f"Error generating questions: {e}")
            
            # Fallback to default question generation
            fallback_questions = self._generate_fallback_questions(research_question, agent_types)
            
            return QuestionGenerationResult(
                original_question=research_question,
                generated_questions=fallback_questions,
                generation_reasoning=f"Used fallback question generation due to error: {str(e)}",
                success=False,
                error_message=str(e)
            )
    
    def _build_question_generation_prompt(
        self, 
        agent_types: List[AgentType], 
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Build the system prompt for question generation."""
        
        # Get agent specialization descriptions
        agent_descriptions = []
        for agent_type in set(agent_types):  # Remove duplicates
            spec = get_agent_specialization(agent_type)
            agent_descriptions.append(f"- **{spec.name}**: {spec.description}")
        
        agent_descriptions_text = "\n".join(agent_descriptions)
        
        prompt = f"""You are a Question Generation Agent for multi-agent research orchestration.

Your role is to decompose a user's research question into {len(agent_types)} specialized sub-questions, each tailored for a specific type of research agent.

Available Agent Types:
{agent_descriptions_text}

Guidelines for Question Generation:
1. **Maintain Coherence**: All questions should contribute to answering the original research question
2. **Leverage Specializations**: Tailor each question to the specific agent's expertise and focus areas
3. **Avoid Overlap**: Ensure questions are complementary rather than redundant
4. **Appropriate Scope**: Each question should be substantial enough for meaningful research
5. **Clear Direction**: Questions should be specific and actionable for the assigned agent type

Context Considerations:
- Consider the complexity and scope of the original question
- Ensure questions can be researched using academic papers and scientific literature
- Balance breadth (comprehensive coverage) with depth (detailed analysis)
- Consider interdisciplinary perspectives where relevant

Output Format:
Provide your response as a JSON object with the following structure:
{{
    "reasoning": "Brief explanation of your question decomposition strategy",
    "questions": [
        {{
            "agent_type": "research|analysis|verification|alternative",
            "question": "The specific question for this agent",
            "focus": "Brief description of what this agent should focus on"
        }}
    ]
}}"""

        return prompt
    
    def _build_user_prompt(self, research_question: str, agent_types: List[AgentType]) -> str:
        """Build the user prompt with the specific research question."""
        
        agent_assignments = []
        for i, agent_type in enumerate(agent_types):
            spec = get_agent_specialization(agent_type)
            agent_assignments.append(f"Agent {i+1}: {spec.name} ({agent_type.value})")
        
        assignments_text = "\n".join(agent_assignments)
        
        return f"""Original Research Question: "{research_question}"

Generate {len(agent_types)} specialized questions for the following agent configuration:
{assignments_text}

Please create questions that will enable these agents to work together effectively to provide a comprehensive answer to the original research question."""
    
    # ---------------------------------------------------------------------
    # Response Parsing Helpers
    # ---------------------------------------------------------------------

    def _parse_question_response_dict(
        self,
        response_data: Dict[str, Any],
        agent_types: List[AgentType]
    ) -> List[GeneratedQuestion]:
        """Parse already-structured dict response."""
        questions = []
        for i, question_data in enumerate(response_data.get("questions", [])):
            if i >= len(agent_types):
                break
            try:
                agent_type = AgentType(question_data["agent_type"])
            except Exception:
                agent_type = agent_types[i]
            spec = get_agent_specialization(agent_type)
            questions.append(
                GeneratedQuestion(
                    agent_id=i,
                    agent_type=agent_type,
                    question=question_data["question"],
                    specialization_focus=question_data.get("focus", spec.description),
                    search_strategy=spec.search_strategy,
                )
            )
        return questions

    def _parse_question_response_str(
        self, 
        response_content: str, 
        agent_types: List[AgentType]
    ) -> List[GeneratedQuestion]:
        """Parse the LLM response and extract generated questions."""
        
        lines = response_content.strip().split('\n')
        questions = []
        
        current_question = ""
        question_count = 0
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Look for question patterns
            if any(marker in line.lower() for marker in ['question', 'agent', '1.', '2.', '3.', '4.', '5.', '6.']):
                if current_question and question_count < len(agent_types):
                    # Save previous question
                    agent_type = agent_types[question_count]
                    spec = get_agent_specialization(agent_type)
                    
                    question = GeneratedQuestion(
                        agent_id=question_count,
                        agent_type=agent_type,
                        question=current_question.strip(),
                        specialization_focus=spec.description,
                        search_strategy=spec.search_strategy
                    )
                    questions.append(question)
                    question_count += 1
                
                current_question = line
            else:
                current_question += " " + line
        
        # Don't forget the last question
        if current_question and question_count < len(agent_types):
            agent_type = agent_types[question_count]
            spec = get_agent_specialization(agent_type)
            
            question = GeneratedQuestion(
                agent_id=question_count,
                agent_type=agent_type,
                question=current_question.strip(),
                specialization_focus=spec.description,
                search_strategy=spec.search_strategy
            )
            questions.append(question)
        
        return questions
    
    def _generate_fallback_questions(
        self, 
        research_question: str, 
        agent_types: List[AgentType]
    ) -> List[GeneratedQuestion]:
        """Generate fallback questions when AI generation fails."""
        
        fallback_questions = []
        
        for i, agent_type in enumerate(agent_types):
            spec = get_agent_specialization(agent_type)
            
            # Create agent-specific variations of the original question
            if agent_type == AgentType.RESEARCH:
                question_text = f"Conduct comprehensive research on: {research_question}"
            elif agent_type == AgentType.ANALYSIS:
                question_text = f"Analyze patterns, trends, and insights related to: {research_question}"
            elif agent_type == AgentType.VERIFICATION:
                question_text = f"Verify and validate key claims and findings about: {research_question}"
            elif agent_type == AgentType.ALTERNATIVE:
                question_text = f"Explore alternative perspectives and contrarian views on: {research_question}"
            else:
                question_text = f"Research the following topic from a {agent_type.value} perspective: {research_question}"
            
            question = GeneratedQuestion(
                agent_id=i,
                agent_type=agent_type,
                question=question_text,
                specialization_focus=spec.description,
                search_strategy=spec.search_strategy
            )
            fallback_questions.append(question)
        
        return fallback_questions
    
    def validate_questions(self, questions: List[GeneratedQuestion]) -> Dict[str, Any]:
        """
        Validate the quality and appropriateness of generated questions.
        
        Args:
            questions: List of generated questions to validate
            
        Returns:
            Validation results with quality metrics and suggestions
        """
        validation_results = {
            "valid": True,
            "issues": [],
            "suggestions": [],
            "quality_score": 0.0
        }
        
        # Check for minimum number of questions
        if len(questions) < 2:
            validation_results["valid"] = False
            validation_results["issues"].append("Insufficient number of questions generated")
        
        # Check for question length and substance
        for question in questions:
            if len(question.question.split()) < 5:
                validation_results["issues"].append(f"Question {question.agent_id} may be too short")
            
            if len(question.question.split()) > 50:
                validation_results["issues"].append(f"Question {question.agent_id} may be too long")
        
        # Check for diversity in agent types
        agent_types_used = set(q.agent_type for q in questions)
        if len(agent_types_used) < min(2, len(questions)):
            validation_results["issues"].append("Insufficient diversity in agent specializations")
        
        # Calculate quality score
        quality_factors = []
        quality_factors.append(min(1.0, len(questions) / 4))  # Optimal around 4 questions
        quality_factors.append(len(agent_types_used) / len(questions))  # Diversity score
        quality_factors.append(1.0 if len(validation_results["issues"]) == 0 else 0.5)  # Issue penalty
        
        validation_results["quality_score"] = sum(quality_factors) / len(quality_factors)
        
        if validation_results["quality_score"] < 0.7:
            validation_results["suggestions"].append("Consider regenerating questions for better quality")
        
        return validation_results 