"""
Pydantic Schemas for Research Agent LLM Responses

This module defines structured response schemas for all research agent nodes
to ensure consistent and parseable LLM outputs using JSON format.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class QueryPlanningResponse(BaseModel):
    """Schema for query planning node responses."""
    sub_queries: List[str] = Field(
        description="List of focused sub-queries derived from the main research question",
        min_items=3,
        max_items=10
    )
    planning_rationale: str = Field(
        description="Brief explanation of the query planning strategy and coverage approach"
    )
    estimated_difficulty: str = Field(
        description="Assessment of research difficulty: 'low', 'medium', 'high'",
        pattern="^(low|medium|high)$"
    )


class EvidenceAssessment(BaseModel):
    """Schema for individual evidence assessment."""
    source_id: str = Field(description="Unique identifier for the source")
    quality_score: float = Field(
        description="Quality score from 0.0 to 1.0",
        ge=0.0,
        le=1.0
    )
    relevance_score: float = Field(
        description="Relevance score (typically 0.0 to 1.0, but may exceed 1.0 for some algorithms)", 
        ge=0.0
    )
    key_findings: List[str] = Field(
        description="Key findings or insights from this source",
        max_items=5
    )
    include_in_synthesis: bool = Field(
        description="Whether this source should be included in final synthesis"
    )


class SufficiencyAssessment(BaseModel):
    """Schema for evidence sufficiency evaluation."""
    is_sufficient: bool = Field(
        description="Whether the current evidence is sufficient for comprehensive answer"
    )
    coverage_score: float = Field(
        description="Coverage score from 0.0 to 1.0 indicating how well the question is covered",
        ge=0.0,
        le=1.0
    )
    well_covered_aspects: List[str] = Field(
        description="Aspects of the research question that are well covered"
    )
    missing_aspects: List[str] = Field(
        description="Aspects that need additional evidence"
    )
    confidence_level: str = Field(
        description="Confidence in the sufficiency assessment: 'low', 'medium', 'high'",
        pattern="^(low|medium|high)$"
    )
    recommendation: str = Field(
        description="Recommendation: 'proceed', 'search_more', 'refine_question'"
    )


class EvidenceSelectionResponse(BaseModel):
    """Schema for evidence selection node responses."""
    evidence_assessments: List[EvidenceAssessment] = Field(
        description="Assessment of each evidence source"
    )
    sufficiency_assessment: SufficiencyAssessment = Field(
        description="Overall assessment of evidence sufficiency"
    )
    selection_summary: str = Field(
        description="Summary of the evidence selection process and key decisions"
    )


class CompressionResponse(BaseModel):
    """Schema for evidence compression node responses."""
    compressed_content: str = Field(
        description="Compressed version of the evidence maintaining key information"
    )
    compression_ratio: float = Field(
        description="Actual compression ratio achieved (0.0 to 1.0)",
        ge=0.0,
        le=1.0
    )
    preserved_citations: List[str] = Field(
        description="List of preserved citation identifiers"
    )
    key_points_preserved: List[str] = Field(
        description="Summary of key points that were preserved in compression"
    )
    compression_notes: str = Field(
        description="Notes about the compression process and any trade-offs made"
    )


class Citation(BaseModel):
    """Schema for individual citations."""
    id: str = Field(description="Citation identifier")
    title: str = Field(description="Title of the source")
    url: Optional[str] = Field(description="URL if available")
    source_type: str = Field(description="Type of source (e.g., 'arxiv', 'local', 'external')")
    relevance_score: float = Field(
        description="Relevance score (typically 0.0 to 1.0, but may exceed 1.0 for some algorithms)",
        ge=0.0
    )


class ThematicFinding(BaseModel):
    """Schema for individual thematic findings."""
    theme: str = Field(description="Name of the major theme or trend")
    description: str = Field(description="Detailed explanation of this theme with key insights")
    supporting_evidence: List[str] = Field(
        description="Key evidence points supporting this theme",
        max_items=8
    )


class AnswerGenerationResponse(BaseModel):
    """Schema for answer generation node responses."""
    executive_summary: str = Field(
        description="Concise executive summary highlighting key insights and implications (2-3 paragraphs)"
    )
    thematic_findings: List[ThematicFinding] = Field(
        description="Major themes/trends identified in the analysis",
        min_items=3,
        max_items=5
    )
    detailed_analysis: str = Field(
        description="Comprehensive analytical discussion (800-1200 words) organized by themes with deep synthesis"
    )
    implications_analysis: str = Field(
        description="Analysis of broader implications for the field and future research directions"
    )
    citations_used: List[Citation] = Field(
        description="List of citations used in the answer",
        default=[]
    )
    confidence_score: float = Field(
        description="Confidence in the answer quality from 0.0 to 1.0",
        ge=0.0,
        le=1.0,
        default=0.8
    )
    limitations: List[str] = Field(
        description="Limitations of the analysis and recommendations for further research",
        default=["Analysis based on available sources", "May not include most recent developments"]
    )
    methodology_notes: str = Field(
        description="Brief notes on the research methodology used",
        default="Systematic thematic analysis with cross-source synthesis"
    )


class StructuredParsingHelper:
    """Helper class for parsing structured responses with fallbacks."""
    
    @staticmethod
    def parse_with_fallback(response_text: str, schema_class: BaseModel, logger=None) -> Optional[BaseModel]:
        """
        Parse LLM response with json_repair fallback.
        
        Args:
            response_text: Raw LLM response text
            schema_class: Pydantic model class to parse into
            logger: Optional logger for error reporting
            
        Returns:
            Parsed Pydantic model instance or None if parsing fails
        """
        import json
        try:
            import json_repair
        except ImportError:
            if logger:
                logger.error("json_repair not available for structured parsing")
            return None
            
        # First try direct JSON parsing
        try:
            # Look for JSON content in the response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_text = response_text[json_start:json_end]
                data = json.loads(json_text)
                
                # Handle missing required fields by adding defaults
                if schema_class == AnswerGenerationResponse:
                    if "confidence_score" not in data:
                        data["confidence_score"] = 0.8
                    if "limitations" not in data:
                        data["limitations"] = ["Analysis based on available sources", "May not include most recent developments"]
                    if "methodology_notes" not in data:
                        data["methodology_notes"] = "Systematic search and synthesis of academic sources"
                    if "citations_used" not in data:
                        data["citations_used"] = []
                
                return schema_class(**data)
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            if logger:
                logger.debug(f"Direct JSON parsing failed: {e}")
        
        # Try with json_repair
        try:
            # Extract potential JSON from the response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_text = response_text[json_start:json_end]
                repaired_json = json_repair.repair_json(json_text)
                data = json.loads(repaired_json)
                
                # Handle missing required fields by adding defaults
                if schema_class == AnswerGenerationResponse:
                    # Ensure required fields have values
                    if "confidence_score" not in data:
                        data["confidence_score"] = 0.8
                    if "limitations" not in data:
                        data["limitations"] = ["Analysis based on available sources", "May not include most recent developments"]
                    if "methodology_notes" not in data:
                        data["methodology_notes"] = "Systematic search and synthesis of academic sources"
                    if "citations_used" not in data:
                        data["citations_used"] = []
                
                return schema_class(**data)
            else:
                # Try to repair the entire response
                repaired_json = json_repair.repair_json(response_text)
                data = json.loads(repaired_json)
                
                # Handle missing required fields by adding defaults
                if schema_class == AnswerGenerationResponse:
                    if "confidence_score" not in data:
                        data["confidence_score"] = 0.8
                    if "limitations" not in data:
                        data["limitations"] = ["Analysis based on available sources", "May not include most recent developments"]
                    if "methodology_notes" not in data:
                        data["methodology_notes"] = "Systematic search and synthesis of academic sources"
                    if "citations_used" not in data:
                        data["citations_used"] = []
                
                return schema_class(**data)
                
        except Exception as e:
            if logger:
                logger.warning(f"Structured parsing failed with json_repair: {e}")
            return None
    
    @staticmethod
    def create_fallback_response(schema_class: BaseModel, error_message: str = "Parsing failed") -> BaseModel:
        """
        Create a minimal fallback response for a given schema class.
        
        Args:
            schema_class: Pydantic model class
            error_message: Error message to include
            
        Returns:
            Minimal valid instance of the schema class
        """
        if schema_class == QueryPlanningResponse:
            return QueryPlanningResponse(
                sub_queries=["What are the main aspects of this research topic?",
                           "What are the current findings in this area?",
                           "What are the methodological approaches used?"],
                planning_rationale=f"Fallback query generation due to: {error_message}",
                estimated_difficulty="medium"
            )
        elif schema_class == EvidenceSelectionResponse:
            return EvidenceSelectionResponse(
                evidence_assessments=[],
                sufficiency_assessment=SufficiencyAssessment(
                    is_sufficient=False,
                    coverage_score=0.0,
                    well_covered_aspects=[],
                    missing_aspects=["Unable to assess due to parsing error"],
                    confidence_level="low",
                    recommendation="search_more"
                ),
                selection_summary=f"Evidence selection failed: {error_message}"
            )
        elif schema_class == CompressionResponse:
            return CompressionResponse(
                compressed_content="Compression failed - using original content",
                compression_ratio=1.0,
                preserved_citations=[],
                key_points_preserved=[],
                compression_notes=f"Compression parsing failed: {error_message}"
            )
        elif schema_class == AnswerGenerationResponse:
            return AnswerGenerationResponse(
                executive_summary="Answer generation failed due to parsing error",
                thematic_findings=[
                    ThematicFinding(
                        theme="Error in Analysis", 
                        description="Could not generate proper thematic analysis", 
                        supporting_evidence=["Parsing error occurred"]
                    )
                ],
                detailed_analysis=f"Analysis could not be completed: {error_message}",
                implications_analysis="Unable to analyze implications due to parsing error"
                # Other fields will use their defaults
            )
        else:
            raise ValueError(f"No fallback available for schema class: {schema_class}") 