import os
from pydantic import BaseModel, Field
from typing import Any, Optional

from langchain_core.runnables import RunnableConfig


class AgentConfiguration(BaseModel):
    """Configuration for the research agent workflow."""

    query_generator_model: str = Field(
        default="hermes3",
        metadata={
            "description": "The name of the language model to use for query generation."
        },
    )

    reflection_model: str = Field(
        default="hermes3",
        metadata={
            "description": "The name of the language model to use for reflection."
        },
    )

    answer_model: str = Field(
        default="hermes3", 
        metadata={
            "description": "The name of the language model to use for the final answer."
        },
    )

    number_of_initial_queries: int = Field(
        default=3,
        metadata={"description": "The number of initial search queries to generate."},
    )

    max_research_loops: int = Field(
        default=2,
        metadata={"description": "The maximum number of research loops to perform."},
    )

    semantic_weight: float = Field(
        default=0.5,
        metadata={"description": "Weight for semantic similarity in hybrid search."},
    )

    keyword_weight: float = Field(
        default=0.5,
        metadata={"description": "Weight for keyword similarity in hybrid search."},
    )

    local_search_limit: int = Field(
        default=5,
        metadata={"description": "Number of papers to return from local search."},
    )

    external_search_limit: int = Field(
        default=5,
        metadata={"description": "Number of papers to return from external search."},
    )

    enable_pdf_download: bool = Field(
        default=True,
        metadata={"description": "Enable automatic PDF download and processing."},
    )

    similarity_threshold: float = Field(
        default=0.3,
        metadata={"description": "Minimum similarity threshold for search results."},
    )

    @classmethod
    def from_runnable_config(
        cls, config: Optional[RunnableConfig] = None
    ) -> "AgentConfiguration":
        """Create a Configuration instance from a RunnableConfig."""
        configurable = (
            config["configurable"] if config and "configurable" in config else {}
        )

        # Get raw values from environment or config
        raw_values: dict[str, Any] = {
            name: os.environ.get(name.upper(), configurable.get(name))
            for name in cls.model_fields.keys()
        }

        # Filter out None values
        values = {k: v for k, v in raw_values.items() if v is not None}

        return cls(**values) 