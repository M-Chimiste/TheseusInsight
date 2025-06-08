from __future__ import annotations
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import date, timedelta

# Basic domain entities
class Model(BaseModel):
    id: str
    name: str
    provider: str

class ModelCreate(BaseModel):
    provider_id: int
    name: str
    config_json: dict

class Paper(BaseModel):
    id: int
    title: str
    abstract: str
    score: float
    date: str  # ISO 8601
    url: str

class Run(BaseModel):
    id: int
    date: str  # ISO 8601
    pipeline_type: str
    status: str
    duration: float
    artifact_path: Optional[str] = None
    artifact_size: Optional[int] = None

# Settings models
class VisualizerSettings(BaseModel):
    resolution: tuple = (1920, 1080)
    fps: int = 30
    matrix_count: int = 200
    matrix_head_color: str = "#e0ffe7"
    matrix_tail_color: str = "0x00b000"
    matrix_char_size: int = 24
    head_step_time: float = 0.25
    random_x_jitter: float = 2.0
    fade_time: float = 3.0
    head_glow_passes: int = 3
    head_glow_alpha_decay: int = 50
    head_spawn_delay_range: tuple = (1.0, 3.0)
    head_saw_period: float = 1.5
    wave_color: str = "#d703fc"
    trail_colors: List[str] = ["#fc03b6", "#ba03fc", "#ce6bf2"]
    glow_passes: int = 3
    glow_alpha_decay: int = 40
    line_width: int = 6

    class Config:
        json_schema_extra = {
            "example": {
                "theme": "dark",
                "font_size": 12,
                "node_color": "#1f77b4",
                "edge_color": "#aec7e8",
                "show_labels": True,
                "layout_type": "force-directed"
            }
        }

class ModelConfig(BaseModel):
    model_name: str
    model_type: str # This refers to the provider name e.g., "ollama", "openai"
    max_new_tokens: Optional[int] = Field(None, example=2048)
    temperature: Optional[float] = Field(None, example=0.7)
    num_ctx: Optional[int] = Field(None, example=4096) # Context window size
    trust_remote_code: Optional[bool] = Field(None, example=False)
    # Any other model-specific parameters can be added here or in a Dict[str, Any]

class TTSModelConfig(BaseModel):
    tts_provider: str
    tts_model_name: str
    speaker_1_voice: str
    speaker_1_speed: float = Field(..., ge=0.5, le=3.5)
    speaker_2_voice: str
    speaker_2_speed: float = Field(..., ge=0.5, le=3.5)

    class Config:
        json_schema_extra = {
            "example": {
                "tts_provider": "openai",
                "tts_model_name": "tts-1",
                "speaker_1_voice": "sage",
                "speaker_1_speed": 1.0,
                "speaker_2_voice": "ash",
                "speaker_2_speed": 1.0
            }
        }

class OrchestrationConfig(BaseModel):
    embedding_model: ModelConfig = Field(..., example={"model_name": "Alibaba-NLP/gte-modernbert-base", "model_type": "sentence-transformers", "trust_remote_code": True})
    judge_model: ModelConfig = Field(..., example={"model_name": "phi4-mini:3.8b-q8_0", "model_type": "ollama", "max_new_tokens": 512, "temperature": 0.1, "num_ctx": 4096})
    content_extraction_model: ModelConfig = Field(..., example={"model_name": "gemma3:27b-it-qat", "model_type": "ollama", "max_new_tokens": 4096, "temperature": 0.1, "num_ctx": 131072})
    newsletter_sections_model: ModelConfig = Field(..., example={"model_name": "gemma3:27b-it-qat", "model_type": "ollama", "max_new_tokens": 4096, "temperature": 0.1, "num_ctx": 131072})
    newsletter_intro_model: ModelConfig = Field(..., example={"model_name": "gemini-2.0-flash", "model_type": "gemini", "max_new_tokens": 4096, "temperature": 0.1, "num_ctx": 131072})
    podcast_model: Optional[ModelConfig] = Field(None, example={"model_name": "gemini-2.0-flash", "model_type": "gemini", "max_new_tokens": 8192, "temperature": 0.1, "num_ctx": 131072})
    tts_model: Optional[TTSModelConfig] = Field(None, example={"tts_provider": "openai", "tts_model_name": "tts-1", "speaker_1_voice": "sage", "speaker_1_speed": 1.0, "speaker_2_voice": "ash", "speaker_2_speed": 1.0})
    research_agent_model_config: Optional[ResearchAgentModelConfigApi] = Field(None, description="Research Agent model configuration for automated literature review")
    # Add other orchestration settings as needed

class ModelProvider(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True

# Pagination
class PaginatedResponse(BaseModel):
    items: List[Any]  # Can be List[Paper], List[Run], etc.
    total_items: int
    total_pages: int
    current_page: int
    nextPage: Optional[int] = None # Kept for compatibility, but might be derived

# Newsletter/Podcast config models
class DateRange(BaseModel):
    from_date: str = Field(..., alias="from")
    to: str

class PodcastConfig(BaseModel):
    scriptModel: str
    ttsModel: str
    addVisualization: bool = False
    visualizerConfig: Optional[Dict] = None

# WebSocket status models
class NodeStatus(BaseModel):
    nodeId: str
    status: str  # 'pending' | 'processing' | 'completed' | 'failed'
    message: str
    progress: float  # 0-100
    timestamp: str  # ISO 8601

class RunStatus(BaseModel):
    """Combined status model used by WebSocket clients."""

    taskId: str
    nodes: List[NodeStatus]
    overallStatus: str  # 'pending' | 'processing' | 'completed' | 'failed'
    currentStep: Optional[str] = None
    progress: Optional[float] = None  # 0-100
    message: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

# Settings for ArXiv
class ArxivCategoriesConfig(BaseModel):
    main_category: str = Field(..., example="cs")
    filter_categories: List[str] = Field(..., example=["cs.ai", "cs.cl", "cs.lg"])

# Settings for Newsletter Generation
class NewsletterConfig(BaseModel):
    start_date: date
    end_date: date
    research_summary_model: ModelConfig
    title_generation_model: ModelConfig
    intro_generation_model: ModelConfig
    layout_optimization_model: ModelConfig
    # Additional fields like template_path, max_papers, etc.
    max_papers_to_select: int = Field(10, gt=0)
    min_score_threshold: float = Field(0.5, ge=0, le=1)
    search_query: Optional[str] = None
    send_email: bool = False
    intro_music_path: Optional[str] = None # Path to intro music file if any

# If you have other specific setting structures, define them here
# e.g., EmailRecipients, ResearchInterests (if more complex than simple list/string)

class EmailRecipients(BaseModel):
    recipients: List[str] = Field(..., example=["test@example.com", "user@example.org"])

class ResearchInterests(BaseModel):
    interests: str = Field(..., example="Large language models, reinforcement learning, and generative AI.")

# Ensure this is at the end or handled correctly if models refer to each other.
# This is a placeholder for now, actual model definitions will be used from above.
# Model.update_forward_refs()
# ModelConfig.update_forward_refs()
# OrchestrationConfig.update_forward_refs()
# NewsletterConfig.update_forward_refs()

# --- Podcast Generation Specific Models --- #

class PodcastVisualizerParams(BaseModel):
    """Detailed parameters for the podcast video visualizer."""
    matrix_count: int
    matrix_head_color: str
    matrix_tail_color: str
    matrix_char_size: int
    head_step_time: float
    random_x_jitter: float
    fade_time: float
    head_glow_passes: int
    head_glow_alpha_decay: int
    head_spawn_delay_range_min: float
    head_spawn_delay_range_max: float
    head_saw_period: float
    line_width: int
    wave_color: str
    trail_color_1: str
    trail_color_2: str
    trail_color_3: str
    glow_passes: int
    glow_alpha_decay: int
    font_path: str
    resolution_width: int
    resolution_height: int
    fps: int

class PodcastGenerationParams(BaseModel):
    """Parameters for initiating a podcast generation task."""
    input_type: str = Field(..., description="Input type, either 'urls' or 'pdfs'.")
    urls: Optional[List[str]] = Field(None, description="List of URLs if input_type is 'urls'.")
    # PDF files will be handled as UploadFile list directly in the endpoint, not part of this JSON body.
    podcast_model_config: ModelConfig
    tts_model_config: TTSModelConfig
    create_visualization: bool
    visualizer_params: Optional[PodcastVisualizerParams] = None
    # Intro music file will also be handled as UploadFile directly in the endpoint.

# New models for Podcast History
class PodcastScriptItem(BaseModel):
    text: str
    speaker: str
    segment_label: Optional[str] = None

class PodcastDetailResponse(BaseModel):
    id: int
    title: str
    date: str
    description: str
    script: List[PodcastScriptItem]

class PodcastListItemResponse(BaseModel):
    id: int
    title: str
    date: str
    description_snippet: str

# --- Pydantic Model for Newsletter Run Pipeline ---
class NewsletterRunParams(BaseModel):
    start_date: str = Field(..., example=date.today().strftime("%Y-%m-%d"))
    end_date: str = Field(..., example=(date.today() - timedelta(days=6)).strftime("%Y-%m-%d"))
    email_recipients: List[str] = Field(default_factory=list, example=["test@example.com"])
    research_interests: str = Field(..., example="AI in healthcare")
    generate_podcast_run: bool = Field(False, description="Whether to generate a podcast as part of this run.")

# Models for Papers Page
class PaperApiResponse(BaseModel):
    id: int
    title: str
    abstract: str
    date: str
    date_run: str
    score: float # Or int, needs to match db/model
    rationale: str
    related: bool
    cosine_similarity: float
    url: str
    embedding_model: str
    similarity_score: Optional[float] = Field(default=None, description="Semantic similarity score when returned from similarity search")
    semantic_score: Optional[float] = Field(default=None, description="Semantic similarity score in hybrid search")
    keyword_score: Optional[float] = Field(default=None, description="Keyword matching score in hybrid search")
    hybrid_score: Optional[float] = Field(default=None, description="Combined hybrid search score")

class PaginatedPapersResponse(PaginatedResponse): # Inherit from existing PaginatedResponse
    items: List[PaperApiResponse]
    # total_items, total_pages, current_page, nextPage are inherited

class SimilaritySearchResponse(BaseModel):
    query_text: str
    results: List[PaperApiResponse]
    total_results: int

class SimilaritySearchRequest(BaseModel):
    query_text: str = Field(..., description="Text to search for semantically similar papers")
    limit: Optional[int] = Field(10, description="Maximum number of results to return")
    similarity_threshold: Optional[float] = Field(0.7, description="Minimum similarity score (0-1)")

class SimilarPapersRequest(BaseModel):
    limit: Optional[int] = Field(10, description="Maximum number of similar papers to return")
    similarity_threshold: Optional[float] = Field(0.7, description="Minimum similarity score (0-1)")

class SimilarPapersResponse(BaseModel):
    reference_paper: PaperApiResponse
    similar_papers: List[PaperApiResponse]
    total_similar: int

class HybridSearchRequest(BaseModel):
    query_text: str = Field(..., description="Search query text")
    page: int = Field(1, gt=0, description="Page number")
    page_size: int = Field(10, gt=0, le=100, description="Number of results per page")
    semantic_weight: float = Field(0.6, ge=0.0, le=1.0, description="Weight for semantic similarity")
    keyword_weight: float = Field(0.4, ge=0.0, le=1.0, description="Weight for keyword matching")
    similarity_threshold: float = Field(0.3, ge=0.0, le=1.0, description="Minimum semantic similarity threshold")
    min_score: Optional[float] = Field(None, description="Minimum paper score filter")
    max_score: Optional[float] = Field(None, description="Maximum paper score filter")
    from_date: Optional[str] = Field(None, description="Start date filter (YYYY-MM-DD)")
    to_date: Optional[str] = Field(None, description="End date filter (YYYY-MM-DD)")

class HybridSearchResponse(BaseModel):
    query_text: str
    results: List[PaperApiResponse]
    total_results: int
    total_pages: int
    current_page: int
    semantic_weight: float
    keyword_weight: float

# Research Agent Model Configuration
class ResearchAgentModelConfigApi(BaseModel):
    """API model for Research Agent model configuration using LangGraph workflow."""
    
    # LangGraph workflow configuration
    reasoning_model: Optional[ModelConfig] = Field(None, description="Primary reasoning model for query generation, reflection, and synthesis")
    query_generator_model: Optional[ModelConfig] = Field(None, description="Model for generating search queries")
    reflection_model: Optional[ModelConfig] = Field(None, description="Model for reflecting on search results")
    answer_model: Optional[ModelConfig] = Field(None, description="Model for final answer generation")
    
    # Research workflow configuration
    max_research_loops: Optional[int] = Field(10, ge=1, le=50, description="Maximum research iteration loops")
    initial_search_query_count: Optional[int] = Field(3, ge=1, le=10, description="Number of initial search queries")
    local_search_limit: Optional[int] = Field(10, ge=1, le=50, description="Papers per local search operation")
    external_search_limit: Optional[int] = Field(5, ge=1, le=20, description="Papers per external search operation")
    
    # Search strategy configuration
    search_config: Optional[Dict[str, Any]] = Field(
        default_factory=lambda: {
            "semantic_weight": 0.6,
            "keyword_weight": 0.4,
            "similarity_threshold": 0.3,
            "enable_pdf_download": True,
            "external_search_delay": 2.0
        },
        description="Search strategy parameters for hybrid local/external search"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "reasoning_model": {
                    "model_name": "gemini-2.0-flash",
                    "model_type": "gemini",
                    "max_new_tokens": 4096,
                    "temperature": 0.1,
                    "num_ctx": 131072
                },
                "max_research_loops": 10,
                "initial_search_query_count": 3,
                "local_search_limit": 10,
                "external_search_limit": 5,
                "search_config": {
                    "semantic_weight": 0.6,
                    "keyword_weight": 0.4,
                    "similarity_threshold": 0.3,
                    "enable_pdf_download": True
                }
            }
        }

# Research Agent Request/Response models
class ConversationMessage(BaseModel):
    """Individual message in a conversation history."""
    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")

class ResearchAgentRunRequest(BaseModel):
    """Request model for starting an enhanced research agent run with LangGraph workflow (FR-18)."""
    research_question: str = Field(..., min_length=10, description="Research question to investigate")
    num_papers_target: int = Field(5, ge=1, le=20, description="Target number of papers to collect")
    max_steps: int = Field(10, ge=1, le=50, description="Maximum agent iteration steps")
    model_config_override: Optional[ResearchAgentModelConfigApi] = Field(
        None, description="Optional model configuration override"
    )
    conversation_history: List[ConversationMessage] = Field(
        default_factory=list, description="Previous conversation messages for multi-turn research"
    )

class ResearchAgentRunResponse(BaseModel):
    """Response model for research agent run initiation."""
    task_id: str = Field(..., description="Unique task identifier")
    message: str = Field(..., description="Status message")

# Literature Review result models
class LiteratureReviewSummary(BaseModel):
    """Summary of a literature review result."""
    paper_id: int
    title: str
    summary: str
    rationale: str
    relevance_score: float

class LiteratureReviewResult(BaseModel):
    """Complete literature review result."""
    id: int
    research_question: str
    summaries: List[LiteratureReviewSummary]
    created_ts: str
    total_papers: int
    trace_log: List[Dict[str, Any]] = Field(default_factory=list)
    report_text: Optional[str] = Field(None, description="Full markdown report generated by the research agent")
    short_summary: Optional[str] = Field(None, description="Concise few-word summary for the research library")
    activity_log: Optional[List[Dict[str, Any]]] = Field(None, description="Detailed activity timeline from the research process")

# Research Library API Models
class ResearchLibrarySearchRequest(BaseModel):
    """Request model for searching the research library."""
    query: Optional[str] = Field(None, description="Search query to match against research questions, summaries, and reports")
    page: int = Field(1, ge=1, description="Page number (1-based)")
    page_size: int = Field(20, ge=1, le=100, description="Number of results per page")
    from_date: Optional[str] = Field(None, description="Filter results from this date (YYYY-MM-DD)")
    to_date: Optional[str] = Field(None, description="Filter results to this date (YYYY-MM-DD)")

class ResearchLibraryItem(BaseModel):
    """Individual item in the research library."""
    id: int
    research_question: str
    short_summary: str
    created_ts: str
    sources_count: int = Field(description="Number of sources found in this research")
    has_report: bool = Field(description="Whether a full report is available")
    themes: List[str] = Field(default_factory=list, description="Extracted themes/categories")

class ResearchLibraryResponse(BaseModel):
    """Response model for research library searches."""
    results: List[ResearchLibraryItem]
    total_count: int
    total_pages: int
    current_page: int
    page_size: int
    has_next: bool
    has_previous: bool

# Model Catalog API Models
class ModelCatalogEntry(BaseModel):
    """Model catalog entry for storing reusable model configurations."""
    id: Optional[int] = Field(None, description="Auto-generated ID")
    alias: str = Field(..., min_length=1, max_length=100, description="Display name/alias for the model")
    model_string: str = Field(..., min_length=1, description="Actual model identifier (e.g., phi4-mini:3.8b-q8_0)")
    provider_name: str = Field(..., description="Provider name (ollama, openai, etc.)")
    model_type: str = Field(..., description="Type of model (chat, embedding, completion)")
    description: Optional[str] = Field(None, description="Markdown description of the model")
    max_new_tokens: Optional[int] = Field(None, ge=1, le=100000, description="Default maximum tokens")
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0, description="Default temperature")
    num_ctx: Optional[int] = Field(None, ge=1, le=1000000, description="Context window size")
    trust_remote_code: Optional[bool] = Field(False, description="Trust remote code (for embedding models)")
    tags: Optional[List[str]] = Field(default_factory=list, description="Tags for categorization")
    is_favorite: Optional[bool] = Field(False, description="Mark as favorite model")
    created_at: Optional[str] = Field(None, description="Creation timestamp")
    updated_at: Optional[str] = Field(None, description="Last update timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "alias": "Phi-4 Mini",
                "model_string": "phi4-mini:3.8b-q8_0",
                "provider_name": "ollama",
                "model_type": "chat",
                "description": "# Phi-4 Mini\n\nA small but capable language model optimized for reasoning tasks.",
                "max_new_tokens": 4096,
                "temperature": 0.1,
                "num_ctx": 131072,
                "trust_remote_code": False,
                "tags": ["reasoning", "small", "fast"],
                "is_favorite": True
            }
        }

class ModelCatalogCreateRequest(BaseModel):
    """Request model for creating a new model catalog entry."""
    alias: str = Field(..., min_length=1, max_length=100)
    model_string: str = Field(..., min_length=1)
    provider_name: str
    model_type: str
    description: Optional[str] = None
    max_new_tokens: Optional[int] = Field(None, ge=1, le=100000)
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    num_ctx: Optional[int] = Field(None, ge=1, le=1000000)
    trust_remote_code: Optional[bool] = False
    tags: Optional[List[str]] = Field(default_factory=list)
    is_favorite: Optional[bool] = False

class ModelCatalogUpdateRequest(BaseModel):
    """Request model for updating an existing model catalog entry."""
    alias: Optional[str] = Field(None, min_length=1, max_length=100)
    model_string: Optional[str] = Field(None, min_length=1)
    provider_name: Optional[str] = None
    model_type: Optional[str] = None
    description: Optional[str] = None
    max_new_tokens: Optional[int] = Field(None, ge=1, le=100000)
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    num_ctx: Optional[int] = Field(None, ge=1, le=1000000)
    trust_remote_code: Optional[bool] = None
    tags: Optional[List[str]] = None
    is_favorite: Optional[bool] = None

class ModelCatalogSearchRequest(BaseModel):
    """Request model for searching the model catalog."""
    provider_name: Optional[str] = Field(None, description="Filter by provider")
    model_type: Optional[str] = Field(None, description="Filter by model type")
    is_favorite: Optional[bool] = Field(None, description="Filter by favorite status")
    search: Optional[str] = Field(None, description="Search in alias, model_string, and description")
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(20, ge=1, le=100, description="Items per page")

class ModelCatalogResponse(BaseModel):
    """Response model for model catalog operations."""
    models: List[ModelCatalogEntry]
    total_count: int
    total_pages: int
    current_page: int
    page_size: int
