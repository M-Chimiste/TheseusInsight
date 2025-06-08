from pydantic import BaseModel, Field
from typing import List


class QueryRefinement(BaseModel):
    """Schema for query refinement and clarification."""
    needs_clarification: bool = Field(description="Whether the query needs clarification")
    clarifying_questions: List[str] = Field(description="List of clarifying questions to ask the user")
    refined_query: str = Field(description="Refined version of the query if no clarification needed")
    original_query: str = Field(description="The original query as provided")


class SearchQueryList(BaseModel):
    """Schema for the query generation output."""
    rationale: str = Field(description="Brief explanation of why these queries are relevant")
    query: List[str] = Field(description="List of search queries")


class Reflection(BaseModel):
    """Schema for reflection output to assess research completeness."""
    is_sufficient: bool = Field(description="Whether the current research is sufficient")
    knowledge_gap: str = Field(description="Description of what information is missing")
    follow_up_queries: List[str] = Field(description="Specific follow-up queries to address gaps") 