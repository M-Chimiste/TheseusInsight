from pydantic import BaseModel, Field
from typing import List, Optional, Union, Dict
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

class OrchestrationConfig(BaseModel):
    embedding_model: Dict[str, Union[str, bool]] = {
        "model_name": "Alibaba-NLP/gte-modernbert-base",
        "model_type": "sentence-transformers",
        "trust_remote_code": True
    }
    judge_model: Dict[str, Union[str, int, float]] = {
        "model_name": "phi4-mini:3.8b-q8_0",
        "model_type": "ollama",
        "max_new_tokens": 512,
        "temperature": 0.1,
        "num_ctx": 4096
    }
    newsletter_model: Dict[str, Union[str, int, float]] = {
        "model_name": "gemma3:27b-it-qat",
        "model_type": "ollama",
        "max_new_tokens": 4096,
        "temperature": 0.1,
        "num_ctx": 131072
    }
    content_extraction_model: Dict[str, Union[str, int, float]] = {
        "model_name": "gemma3:27b-it-qat",
        "model_type": "ollama",
        "max_new_tokens": 4096,
        "temperature": 0.1,
        "num_ctx": 131072
    }
    newsletter_sections_model: Dict[str, Union[str, int, float]] = {
        "model_name": "gemma3:27b-it-qat",
        "model_type": "ollama",
        "max_new_tokens": 4096,
        "temperature": 0.1,
        "num_ctx": 131072
    }
    newsletter_intro_model: Dict[str, Union[str, int, float]] = {
        "model_name": "gemini-2.0-flash",
        "model_type": "gemini",
        "max_new_tokens": 4096,
        "temperature": 0.1,
        "num_ctx": 131072
    }
    podcast_script_model: Dict[str, Union[str, int, float]] = {
        "model_name": "gemini-2.0-flash",
        "model_type": "gemini",
        "max_new_tokens": 4096,
        "temperature": 0.1,
        "num_ctx": 131072
    }
    arxiv_search_categories: Dict[str, Union[str, List[str]]] = {
        "main_category": "cs.AI",
        "filter_categories": ["cs.LG", "cs.CL", "cs.CV"]
    }

# Pagination
class PaginatedResponse(BaseModel):
    items: List[Union[Paper, Run]]
    nextPage: Optional[int]

# Newsletter/Podcast config models
class DateRange(BaseModel):
    from_date: str = Field(..., alias="from")
    to: str

class PodcastConfig(BaseModel):
    scriptModel: str
    ttsModel: str
    addVisualization: bool = False
    visualizerConfig: Optional[Dict] = None

class NewsletterConfig(BaseModel):
    dateRange: DateRange
    topics: List[str]
    judgeModel: str
    newsletterModel: str
    podcastConfig: Optional[PodcastConfig] = None

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