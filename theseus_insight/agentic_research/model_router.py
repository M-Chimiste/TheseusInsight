"""
Research Agent Model Router

Implements FR-8, FR-9, FR-10: Model configuration management and routing for Research Agent.
- Loads boss/worker model configurations from settings
- Routes all LLM calls through existing LLMModelFactory
- Records model selection decisions in trace logs
"""

import json
import time
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum

from ..data_model.data_handling import PaperDatabase
from ..inference.llm import LLMModelFactory
from ..api.models import ModelConfig


class ModelRole(Enum):
    """Roles that models can play in the Research Agent."""
    BOSS = "boss"           # Main coordinating model
    WORKER = "worker"       # Task-specific worker models
    SUMMARY = "summary"     # Specialized for summarization
    ANALYSIS = "analysis"   # Specialized for analysis
    SEARCH = "search"       # Specialized for search query generation


@dataclass
class ModelInvocation:
    """Record of a model invocation for trace logging."""
    timestamp: str
    model_role: str
    model_name: str
    model_type: str
    task_description: str
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    duration_ms: Optional[float] = None
    success: bool = True
    error_message: Optional[str] = None


class ResearchAgentModelConfig:
    """
    Configuration container for Research Agent models.
    Implements FR-8: declarative model_config listing boss and worker models.
    """
    
    def __init__(self, config_dict: Dict[str, Any]):
        """
        Initialize from configuration dictionary.
        
        Expected format:
        {
            "boss_model": ModelConfig,
            "worker_models": {
                "summary": ModelConfig,
                "analysis": ModelConfig,
                "search": ModelConfig
            },
            "default_worker": "summary",  # Fallback worker model
            "max_retries": 3,
            "timeout_seconds": 30
        }
        """
        self.boss_model = ModelConfig(**config_dict["boss_model"])
        self.worker_models = {
            role: ModelConfig(**config) 
            for role, config in config_dict.get("worker_models", {}).items()
        }
        self.default_worker = config_dict.get("default_worker", "summary")
        self.max_retries = config_dict.get("max_retries", 3)
        self.timeout_seconds = config_dict.get("timeout_seconds", 30)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "boss_model": self.boss_model.dict(),
            "worker_models": {
                role: config.dict() 
                for role, config in self.worker_models.items()
            },
            "default_worker": self.default_worker,
            "max_retries": self.max_retries,
            "timeout_seconds": self.timeout_seconds
        }
    
    def get_model_for_role(self, role: ModelRole) -> ModelConfig:
        """Get the appropriate model configuration for a given role."""
        if role == ModelRole.BOSS:
            return self.boss_model
        
        # For worker roles, use specific model if available, else default
        role_name = role.value
        if role_name in self.worker_models:
            return self.worker_models[role_name]
        elif self.default_worker in self.worker_models:
            return self.worker_models[self.default_worker]
        else:
            # Fallback to boss model if no workers configured
            return self.boss_model


class AgentModelRouter:
    """
    Model router for Research Agent that implements dynamic model selection.
    
    Implements:
    - FR-9: All LLM calls route through existing LLMModelFactory
    - FR-10: Dynamic model selection with trace recording
    """
    
    def __init__(self, db: PaperDatabase, config: ResearchAgentModelConfig):
        """
        Initialize the model router.
        
        Args:
            db: Database instance for accessing settings
            config: Research Agent model configuration
        """
        self.db = db
        self.config = config
        self.model_factory = LLMModelFactory()
        self.model_cache: Dict[str, Any] = {}  # Cache loaded models
        self.trace_log: List[ModelInvocation] = []
    
    def invoke(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str,
        role: ModelRole = ModelRole.BOSS,
        task_description: str = "",
        **kwargs
    ) -> str:
        """
        Invoke a model with the given role and parameters.
        
        Implements FR-9: Routes through LLMModelFactory.invoke()
        Implements FR-10: Records decision in trace_json
        
        Args:
            messages: Conversation messages
            system_prompt: System prompt for the model
            role: Model role to use for selection
            task_description: Description for trace logging
            **kwargs: Additional model parameters
            
        Returns:
            Model response string
        """
        start_time = time.time()
        model_config = self.config.get_model_for_role(role)
        
        # Create cache key for this model configuration
        cache_key = f"{model_config.model_type}:{model_config.model_name}"
        
        try:
            # Get or create model instance
            if cache_key not in self.model_cache:
                model_instance = self.model_factory.create_model(
                    model_config.model_type,
                    model_name=model_config.model_name,
                    max_new_tokens=model_config.max_new_tokens or 4096,
                    temperature=model_config.temperature or 0.1,
                    num_ctx=model_config.num_ctx or 131072,
                    trust_remote_code=model_config.trust_remote_code or False
                )
                self.model_cache[cache_key] = model_instance
            else:
                model_instance = self.model_cache[cache_key]
            
            # Prepare parameters, merging config defaults with kwargs
            invoke_params = {
                "messages": messages,
                "system_prompt": system_prompt,
                "streaming": kwargs.get("streaming", False),
                "max_tokens": kwargs.get("max_tokens", model_config.max_new_tokens),
                "temperature": kwargs.get("temperature", model_config.temperature),
            }
            
            # Add model-specific parameters
            if hasattr(model_instance, 'invoke'):
                if model_config.model_type == "ollama":
                    invoke_params["num_ctx"] = kwargs.get("num_ctx", model_config.num_ctx)
                elif model_config.model_type in ["openai", "anthropic", "gemini"]:
                    invoke_params["model_name"] = kwargs.get("model_name", model_config.model_name)
            
            # Invoke the model
            response = model_instance.invoke(**invoke_params)
            
            # Calculate duration and log success
            duration_ms = (time.time() - start_time) * 1000
            self._log_invocation(
                model_config, role, task_description, 
                duration_ms=duration_ms, success=True
            )
            
            return response
            
        except Exception as e:
            # Log failure
            duration_ms = (time.time() - start_time) * 1000
            self._log_invocation(
                model_config, role, task_description,
                duration_ms=duration_ms, success=False, error_message=str(e)
            )
            raise
    
    def _log_invocation(
        self,
        model_config: ModelConfig,
        role: ModelRole,
        task_description: str,
        duration_ms: float = 0,
        success: bool = True,
        error_message: Optional[str] = None
    ):
        """Log a model invocation for trace recording."""
        invocation = ModelInvocation(
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            model_role=role.value,
            model_name=model_config.model_name,
            model_type=model_config.model_type,
            task_description=task_description,
            duration_ms=duration_ms,
            success=success,
            error_message=error_message
        )
        self.trace_log.append(invocation)
    
    def get_trace_log(self) -> List[Dict[str, Any]]:
        """Get the trace log as a list of dictionaries."""
        return [asdict(invocation) for invocation in self.trace_log]
    
    def clear_trace_log(self):
        """Clear the trace log."""
        self.trace_log.clear()
    
    def select_worker_model(self, task_type: str) -> ModelRole:
        """
        Dynamically select the best worker model for a task type.
        
        Implements FR-10: Dynamic model selection during runs.
        
        Args:
            task_type: Type of task ("summary", "analysis", "search", etc.)
            
        Returns:
            Selected model role
        """
        # Map task types to model roles
        task_role_mapping = {
            "summary": ModelRole.SUMMARY,
            "summarize": ModelRole.SUMMARY,
            "analyze": ModelRole.ANALYSIS,
            "analysis": ModelRole.ANALYSIS,
            "search": ModelRole.SEARCH,
            "query": ModelRole.SEARCH,
            "worker": ModelRole.WORKER,
        }
        
        # Select role based on task type
        selected_role = task_role_mapping.get(task_type.lower(), ModelRole.WORKER)
        
        # Verify the selected role has a configured model
        if selected_role != ModelRole.BOSS:
            # Check if we have a specific model for this role
            if selected_role.value not in self.config.worker_models:
                # Fall back to default worker
                if self.config.default_worker in self.config.worker_models:
                    selected_role = ModelRole(self.config.default_worker)
                else:
                    # Ultimate fallback to boss model
                    selected_role = ModelRole.BOSS
        
        return selected_role
    
    def get_available_models(self) -> Dict[str, Dict[str, Any]]:
        """Get information about all available models."""
        models = {"boss": self.config.boss_model.dict()}
        for role, config in self.config.worker_models.items():
            models[role] = config.dict()
        return models


def load_research_agent_model_config(db: PaperDatabase) -> ResearchAgentModelConfig:
    """
    Load Research Agent model configuration from database settings.
    
    Implements FR-8: Loading declarative model_config.
    
    Args:
        db: Database instance
        
    Returns:
        ResearchAgentModelConfig instance
    """
    # Try to load from settings
    config_json = db.get_setting("research_agent_model_config")
    
    if config_json:
        try:
            config_dict = json.loads(config_json)
            return ResearchAgentModelConfig(config_dict)
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Warning: Invalid research agent model config: {e}")
    
    # Default configuration if none exists
    default_config = {
        "boss_model": {
            "model_name": "gemini-2.0-flash",
            "model_type": "gemini",
            "max_new_tokens": 4096,
            "temperature": 0.1,
            "num_ctx": 131072
        },
        "worker_models": {
            "summary": {
                "model_name": "gemma3:27b-it-qat",
                "model_type": "ollama",
                "max_new_tokens": 4096,
                "temperature": 0.1,
                "num_ctx": 131072
            },
            "analysis": {
                "model_name": "phi4-mini:3.8b-q8_0",
                "model_type": "ollama",
                "max_new_tokens": 2048,
                "temperature": 0.1,
                "num_ctx": 4096
            },
            "search": {
                "model_name": "phi4-mini:3.8b-q8_0",
                "model_type": "ollama",
                "max_new_tokens": 512,
                "temperature": 0.3,
                "num_ctx": 4096
            }
        },
        "default_worker": "summary",
        "max_retries": 3,
        "timeout_seconds": 30
    }
    
    # Save default config to database
    config = ResearchAgentModelConfig(default_config)
    save_research_agent_model_config(db, config)
    
    return config


def save_research_agent_model_config(db: PaperDatabase, config: ResearchAgentModelConfig):
    """
    Save Research Agent model configuration to database settings.
    
    Implements FR-17: Persist configuration in settings.
    
    Args:
        db: Database instance
        config: Configuration to save
    """
    config_json = json.dumps(config.to_dict(), indent=2)
    db.set_setting("research_agent_model_config", config_json) 