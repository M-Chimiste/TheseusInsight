from pydantic import BaseModel, Field
from typing import List, Optional, Union, Dict, Any
from datetime import date, datetime

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
        schema_extra = {
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
        schema_extra = {
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
    # Add other orchestration settings as needed

class ModelProvider(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True

# Pagination
class PaginatedResponse(BaseModel):
    items: List[Any]  # Can be List[Paper], List[Run], etc.
    nextPage: Optional[int] = None

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
    taskId: str
    nodes: List[NodeStatus]
    overallStatus: str  # 'pending' | 'processing' | 'completed' | 'failed'
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

# General Run Status
class RunStatus(BaseModel):
    taskId: str
    overallStatus: str  # e.g., "PENDING", "RUNNING", "COMPLETED", "FAILED"
    currentStep: Optional[str] = None
    progress: Optional[float] = None  # e.g., 0.0 to 1.0
    message: Optional[str] = None
    result: Optional[Dict[str, Any]] = None # To store final results like file paths or content
    error: Optional[str] = None

# If you have other specific setting structures, define them here
# e.g., EmailRecipients, ResearchInterests (if more complex than simple list/string)

class EmailRecipients(BaseModel):
    recipients: List[str] = Field(..., example=["test@example.com", "user@example.org"])

class ResearchInterests(BaseModel):
    interests: str = Field(..., example="Large language models, reinforcement learning, and generative AI.")

# Ensure this is at the end or handled correctly if models refer to each other.
# This is a placeholder for now, actual model definitions will be used from above.
Model.update_forward_refs()
ModelConfig.update_forward_refs()
OrchestrationConfig.update_forward_refs()
NewsletterConfig.update_forward_refs()

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

# Removed the conflicting/simpler NodeStatus definition that was here.
# class NodeStatus(BaseModel):
#     id: str 
#     status: str 
#     message: Optional[str] = None 