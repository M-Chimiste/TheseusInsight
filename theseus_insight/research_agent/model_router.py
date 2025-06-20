"""
Model Router for Research Agent

This module provides model instances for different research agent nodes
based on the configuration settings using the unified LLMModelFactory.
"""

import logging
import time
import asyncio
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from ..inference.llm import LLMModelFactory, InferenceModel

logger = logging.getLogger(__name__)


# Rate limiting for local models to prevent throttling
LOCAL_MODEL_RATE_LIMITER = {
    'last_call_time': 0,
    'min_interval': 1.0,  # Minimum 1 second between calls for local models
    'lock': asyncio.Lock() if hasattr(asyncio, 'Lock') else None
}


@dataclass
class ModelClient:
    """Wrapper for model clients with rate limiting for local models."""
    
    def __init__(self, provider: str, model_name: str, **config):
        self.provider = provider
        self.model_name = model_name
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Create the actual model client
        self._client = LLMModelFactory.create_model(
            model_type=provider,
            model_name=model_name,
            **config
        )
        
        # Determine if this is a local model that needs rate limiting
        self.is_local_model = provider.lower() in ['ollama', 'llamacpp', 'local']
    
    def invoke(self, messages: List[Dict[str, str]], system_prompt: str = "", schema: Any = None) -> str:
        """Invoke the model with rate limiting for local models."""
        if self.is_local_model:
            self._apply_rate_limiting()
        
        try:
            if schema:
                # Structured output
                return self._client.invoke(messages, system_prompt, schema=schema)
            else:
                # Regular text output
                return self._client.invoke(messages, system_prompt)
        except Exception as e:
            self.logger.error(f"Model invocation failed for {self.provider}/{self.model_name}: {e}")
            # Add extra delay for local models on error
            if self.is_local_model:
                time.sleep(2.0)
            raise
    
    def _apply_rate_limiting(self):
        """Apply rate limiting for local models."""
        current_time = time.time()
        time_since_last_call = current_time - LOCAL_MODEL_RATE_LIMITER['last_call_time']
        
        if time_since_last_call < LOCAL_MODEL_RATE_LIMITER['min_interval']:
            sleep_time = LOCAL_MODEL_RATE_LIMITER['min_interval'] - time_since_last_call
            self.logger.info(f"Rate limiting local model: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)
        
        LOCAL_MODEL_RATE_LIMITER['last_call_time'] = time.time()


def supports_structured_output(model_type: str) -> bool:
    """
    Check if a model type supports structured JSON output.
    
    Args:
        model_type: The model type to check
        
    Returns:
        True if the model supports structured output
    """
    # Only local models and custom-oai support structured output to avoid OpenAI API errors
    structured_providers = {
        "ollama", "custom-oai", "llamacpp"
    }
    return model_type.lower() in structured_providers


def get_model_for_node(node_name: str, config: Dict[str, Any]) -> ModelClient:
    """
    Get the appropriate model instance for a specific node using the unified LLMModelFactory.
    
    Args:
        node_name: Name of the node requesting the model
        config: Configuration dictionary containing model settings
        
    Returns:
        Configured ModelClient instance
    """
    try:
        # Get node-specific model config or fall back to default
        node_config = config.get(f"{node_name}_model", config.get("default_model", {}))
        
        # Special handling for full_text_summarizer - use answer_generator config as fallback
        if not node_config and node_name == "full_text_summarizer":
            node_config = config.get("answer_generator_model", {})
        
        # If no specific config, use research agent model config
        if not node_config:
            research_config = config.get("research_agent_model_config", {})
            if "boss_model" in research_config:
                node_config = research_config["boss_model"]
            else:
                # NO HARDCODED FALLBACK - Require proper configuration
                logger.error(f"No model configuration found for node {node_name}. Please configure models in Settings.tsx")
                raise ValueError(f"No model configuration found for node {node_name}. Please configure research agent models in Settings.")
        
        model_type = node_config.get("model_type")
        model_name = node_config.get("model_name")
        
        if not model_type or not model_name:
            logger.error(f"Invalid model configuration for {node_name}: missing model_type or model_name")
            raise ValueError(f"Invalid model configuration for {node_name}: missing model_type or model_name")
        
        model_type = model_type.lower()
        temperature = node_config.get("temperature", 0.1)
        max_tokens = node_config.get("max_new_tokens", 4096)
        
        logger.info(f"Creating {model_type} model for {node_name}: {model_name}")
        
        # Prepare model kwargs based on type - NOTE: Remove model_name from kwargs to avoid duplicate
        model_kwargs = {
            "temperature": temperature,
            "max_new_tokens": max_tokens
        }
        
        # Add type-specific parameters
        if model_type == "ollama":
            model_kwargs["num_ctx"] = node_config.get("num_ctx", 131072)
            if "url" in node_config:
                model_kwargs["url"] = node_config["url"]
        elif model_type == "custom-oai":
            if "base_url" in node_config:
                model_kwargs["base_url"] = node_config["base_url"]
            if "api_key" in node_config:
                model_kwargs["api_key"] = node_config["api_key"]
        elif model_type == "llamacpp":
            model_kwargs["num_ctx"] = node_config.get("num_ctx", 131072)
            model_kwargs["n_gpu_layers"] = node_config.get("n_gpu_layers", -1)
        
        # Create model using the factory - model_name passed as positional argument only
        return ModelClient(model_type, model_name, **model_kwargs)
            
    except Exception as e:
        logger.error(f"Error creating model for {node_name}: {str(e)}")
        # DO NOT provide hardcoded fallback - let the error propagate
        raise ValueError(f"Failed to create model for {node_name}: {str(e)}. Please check your model configuration in Settings.")


def get_embedding_model(config: Dict[str, Any]) -> InferenceModel:
    """
    Get the embedding model for vector operations using the unified LLMModelFactory.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Configured embedding model instance
    """
    try:
        embedding_config = config.get("embedding_model", {})
        
        # Default to sentence-transformers if no config
        if not embedding_config:
            embedding_config = {
                "model_type": "sentence-transformer",
                "model_name": "Alibaba-NLP/gte-large-en-v1.5"
            }
        
        model_type = embedding_config.get("model_type", "sentence-transformer").lower()
        
        # Handle both singular and plural forms for backwards compatibility
        if model_type == "sentence-transformers":
            model_type = "sentence-transformer"
        
        model_name = embedding_config.get("model_name", "Alibaba-NLP/gte-large-en-v1.5")
        
        logger.info(f"Creating embedding model: {model_type} - {model_name}")
        
        # Prepare model kwargs
        model_kwargs = {"model_name": model_name}
        
        # Add type-specific parameters
        if model_type == "sentence-transformer":
            # Handle both trust_remote_code and remote_code for compatibility
            if "trust_remote_code" in embedding_config:
                model_kwargs["remote_code"] = embedding_config["trust_remote_code"]
            elif "remote_code" in embedding_config:
                model_kwargs["remote_code"] = embedding_config["remote_code"]
            if "device" in embedding_config:
                model_kwargs["device"] = embedding_config["device"]
        elif model_type == "ollama-embed":
            if "url" in embedding_config:
                model_kwargs["url"] = embedding_config["url"]
        
        # Create model using the factory
        return LLMModelFactory.create_model(model_type, **model_kwargs)
            
    except Exception as e:
        logger.error(f"Error creating embedding model: {str(e)}")
        # DO NOT provide hardcoded fallback - let the error propagate
        raise ValueError(f"Failed to create embedding model: {str(e)}. Please check your embedding model configuration in Settings.")


def validate_model_config(config: Dict[str, Any]) -> bool:
    """
    Validate that the model configuration is properly set up.
    
    Args:
        config: Configuration dictionary to validate
        
    Returns:
        True if configuration is valid, False otherwise
    """
    try:
        # Check if we have at least one model configuration
        has_default = "default_model" in config
        has_research_config = "research_agent_model_config" in config
        
        if not (has_default or has_research_config):
            logger.warning("No model configuration found")
            return False
        
        # If we have research agent config, validate it
        if has_research_config:
            research_config = config["research_agent_model_config"]
            if "boss_model" not in research_config:
                logger.warning("Research agent config missing boss_model")
                return False
        
        return True
        
    except Exception as e:
        logger.error(f"Error validating model config: {str(e)}")
        return False


def get_available_models() -> Dict[str, list]:
    """
    Get a list of available models by provider supported by LLMModelFactory.
    
    Returns:
        Dictionary mapping provider names to lists of available models
    """
    return {
        "openai": [
            "gpt-4",
            "gpt-4-turbo",
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-3.5-turbo",
            "gpt-3.5-turbo-16k"
        ],
        "anthropic": [
            "claude-3-5-sonnet-20241022",
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307",
            "claude-2.1",
            "claude-2.0"
        ],
        "ollama": [
            "llama3.2",
            "llama3.1",
            "llama2",
            "mistral",
            "mixtral",
            "codellama",
            "hermes3",
            "qwen2.5"
        ],
        "gemini": [
            "gemini-1.5-flash",
            "gemini-1.5-pro",
            "gemini-pro"
        ],
        "custom-oai": [
            "custom-model"  # Placeholder - actual models depend on the custom endpoint
        ],
        "llamacpp": [
            "local-gguf-model"  # Placeholder - actual models depend on local GGUF files
        ],
        "sentence-transformer": [
            "Alibaba-NLP/gte-large-en-v1.5",
            "sentence-transformers/all-MiniLM-L6-v2",
            "sentence-transformers/all-mpnet-base-v2",
            "BAAI/bge-large-en-v1.5"
        ],
        "ollama-embed": [
            "nomic-embed-text",
            "mxbai-embed-large"
        ]
    } 