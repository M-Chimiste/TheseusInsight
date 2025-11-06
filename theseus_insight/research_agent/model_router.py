"""
Model Router for Research Agent

This module provides model instances for different research agent nodes
based on the configuration settings using the unified LLMModelFactory.
Enhanced to support both single-agent workflow and multi-agent orchestration.
"""

import logging
import os
import time
import asyncio
import threading
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from LLMFactory import LLMModelFactory
from LLMFactory.providers import InferenceModel

logger = logging.getLogger(__name__)


def resolve_host_for_provider(
    provider: str,
    configured_host: Optional[str] = None
) -> Optional[str]:
    """
    Resolve the host for a given provider with priority handling.

    Priority:
    1. configured_host (from ModelConfig.host) - highest priority
    2. Environment variable (OLLAMA_URL, LMSTUDIO_HOST)
    3. None (let provider use its default)

    Args:
        provider: Provider type ('ollama', 'lmstudio', 'custom-oai')
        configured_host: Host from ModelConfig (highest priority)

    Returns:
        Resolved host string or None for default
    """
    # Priority 1: Explicit configuration
    if configured_host:
        logger.info(f"Using configured host for {provider}: {configured_host}")
        return configured_host

    # Priority 2: Environment variables
    if provider.lower() == 'ollama':
        env_url = os.getenv('OLLAMA_URL')
        if env_url:
            logger.info(f"Using OLLAMA_URL from environment: {env_url}")
            return env_url
    elif provider.lower() == 'lmstudio':
        env_host = os.getenv('LMSTUDIO_HOST')
        if env_host:
            logger.info(f"Using LMSTUDIO_HOST from environment: {env_host}")
            return env_host
    elif provider.lower() == 'custom-oai':
        # Custom-OAI typically passes base_url directly
        pass

    # Priority 3: Use provider defaults (return None)
    logger.debug(f"Using default host for {provider}")
    return None


def normalize_ollama_url(host: str) -> str:
    """
    Normalize Ollama URL to ensure it has http:// prefix.

    Args:
        host: Host string (may or may not have http:// prefix)

    Returns:
        Normalized URL with http:// prefix
    """
    if not host:
        return "http://127.0.0.1:11434"

    # Add http:// if not present
    if not host.startswith(('http://', 'https://')):
        host = f"http://{host}"

    return host


# Rate limiting for local models to prevent throttling
LOCAL_MODEL_RATE_LIMITER = {
    'last_call_time': 0,
    'min_interval': 1.0,  # Minimum 1 second between calls for local models
    # Use a standard threading lock for cross-thread serialization
    'lock': threading.Lock()
}


@dataclass
class ModelClient:
    """Wrapper for model clients with rate limiting for local models."""
    
    def __init__(self, provider: str, model_name: str, **config):
        self.provider = provider
        self.model_name = model_name
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Resolve host with priority handling (configured host > env variable > default)
        configured_host = config.pop('host', None)
        resolved_host = resolve_host_for_provider(provider, configured_host)

        # Apply resolved host to appropriate provider parameter
        if resolved_host:
            if provider.lower() == 'ollama':
                config['url'] = normalize_ollama_url(resolved_host)
                self.logger.info(f"Ollama using resolved URL: {config['url']}")
            elif provider.lower() == 'lmstudio':
                config['host'] = resolved_host
                self.logger.info(f"LMStudio using resolved host: {resolved_host}")
            elif provider.lower() == 'custom-oai':
                config['base_url'] = resolved_host
                self.logger.info(f"Custom-OAI using resolved base_url: {resolved_host}")

        # Create the actual model client
        self._client = LLMModelFactory.create_model(
            model_type=provider,
            model_name=model_name,
            **config
        )

        # Determine if this is a local model that needs rate limiting
        self.is_local_model = provider.lower() in ['ollama', 'llamacpp', 'local', 'lmstudio']
    
    def invoke(self, messages: List[Dict[str, str]], system_prompt: str = "", schema: Any = None) -> str:
        """Invoke the model with rate limiting for local models."""
        if self.is_local_model:
            with LOCAL_MODEL_RATE_LIMITER['lock']:
                # Inside lock: enforce spacing between sequential local invocations
                self._apply_rate_limiting()
                result = self._safe_invoke(messages, system_prompt, schema)
                return result
        else:
            return self._safe_invoke(messages, system_prompt, schema)

    # ------------------------------------------------------------------
    # Internal helper to wrap the actual client invocation
    # ------------------------------------------------------------------
    def _safe_invoke(self, messages: List[Dict[str, str]], system_prompt: str, schema: Any):
        try:
            if schema:
                return self._client.invoke(messages, system_prompt, schema=schema)
            return self._client.invoke(messages, system_prompt)
        except Exception as e:
            self.logger.error(f"Model invocation failed for {self.provider}/{self.model_name}: {e}")
            # Additional back-off for local models
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
    # Providers that support structured JSON output
    structured_providers = {
        "ollama", "lmstudio", "llamacpp",  # Local providers
        "custom-oai", "openai", "gemini"    # Cloud providers with structured output support
    }
    return model_type.lower() in structured_providers


def get_model(node_name: str, config: Dict[str, Any]) -> ModelClient:
    """
    Unified model retrieval function supporting both single-agent workflow nodes
    and multi-agent specialized agents.
    
    Args:
        node_name: Name of the node/agent requesting the model
        config: Configuration dictionary containing model settings
        
    Returns:
        Configured ModelClient instance
    """
    
    # For backward compatibility, delegate to get_model_for_node for workflow nodes
    workflow_nodes = {
        "query_planner", "evidence_selector", "scratchpad_compress", 
        "answer_generator", "full_text_summarizer"
    }
    
    if node_name in workflow_nodes:
        return get_model_for_node(node_name, config)
    
    # For multi-agent specialized agents and new components
    multi_agent_components = {
        "question_generator", "synthesis_agent", "research", "analysis", 
        "verification", "alternative"
    }
    
    if node_name in multi_agent_components:
        return get_model_for_multi_agent(node_name, config)
    
    # Fallback to workflow node handling for unknown nodes
    logger.warning(f"Unknown node '{node_name}', falling back to workflow node handling")
    return get_model_for_node(node_name, config)


def get_model_for_multi_agent(agent_name: str, config: Dict[str, Any]) -> ModelClient:
    """
    Get model for multi-agent orchestration components.
    
    Args:
        agent_name: Name of the multi-agent component
        config: Configuration dictionary containing model settings
        
    Returns:
        Configured ModelClient instance
    """
    try:
        # Check for multi-agent configuration first
        multi_agent_config = config.get("multi_agent_config", {})
        
        if multi_agent_config:
            # Look for specialized model configuration
            specialized_models = multi_agent_config.get("specialized_models", {})
            agent_config = specialized_models.get(agent_name)
            
            # If no specialized config, use boss model
            if not agent_config:
                agent_config = multi_agent_config.get("boss_model")
            
            if agent_config:
                return _create_model_client_from_config(agent_config, agent_name)
        
        # Fallback to single-agent configuration
        research_config = config.get("research_agent_model_config", {})
        if research_config:
            # Map multi-agent component names to single-agent equivalents
            single_agent_mapping = {
                "question_generator": "query_planner_model",
                "synthesis_agent": "answer_generator_model",
                "research": "boss_model",
                "analysis": "boss_model", 
                "verification": "evidence_selector_model",
                "alternative": "boss_model"
            }
            
            mapped_node = single_agent_mapping.get(agent_name, "boss_model")
            agent_config = research_config.get(mapped_node) or research_config.get("boss_model")
            
            if agent_config:
                return _create_model_client_from_config(agent_config, agent_name)
        
        # Final fallback - require configuration
        logger.error(f"No model configuration found for multi-agent component '{agent_name}'")
        raise ValueError(f"No model configuration found for '{agent_name}'. Please configure research agent models in Settings.")
        
    except Exception as e:
        logger.error(f"Error creating model for multi-agent component {agent_name}: {str(e)}")
        raise ValueError(f"Failed to create model for {agent_name}: {str(e)}. Please check your model configuration.")


def get_model_for_node(node_name: str, config: Dict[str, Any]) -> ModelClient:
    """
    Get the appropriate model instance for a specific workflow node using the unified LLMModelFactory.
    
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
        
        return _create_model_client_from_config(node_config, node_name)
            
    except Exception as e:
        logger.error(f"Error creating model for {node_name}: {str(e)}")
        # DO NOT provide hardcoded fallback - let the error propagate
        raise ValueError(f"Failed to create model for {node_name}: {str(e)}. Please check your model configuration in Settings.")


def _create_model_client_from_config(node_config: Dict[str, Any], node_name: str) -> ModelClient:
    """
    Create a ModelClient from a configuration dictionary.
    
    Args:
        node_config: Model configuration dictionary
        node_name: Name of the node/agent for logging
        
    Returns:
        Configured ModelClient instance
    """
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

    # Add host parameter if specified (works for Ollama, LMStudio, Custom-OAI)
    if "host" in node_config and node_config["host"]:
        model_kwargs["host"] = node_config["host"]
        logger.info(f"Using configured host for {node_name}: {node_config['host']}")

    # Add type-specific parameters
    if model_type == "ollama":
        model_kwargs["num_ctx"] = node_config.get("num_ctx", 131072)
        # NOTE: url is deprecated in favor of host, but keep for backward compatibility
        if "url" in node_config and "host" not in model_kwargs:
            model_kwargs["url"] = node_config["url"]
    elif model_type == "lmstudio":
        # LMStudio-specific parameters
        if "context_length" in node_config:
            model_kwargs["context_length"] = node_config["context_length"]
        if "gpu_offload" in node_config:
            model_kwargs["gpu_offload"] = node_config["gpu_offload"]
    elif model_type == "custom-oai":
        # NOTE: base_url is deprecated in favor of host, but keep for backward compatibility
        if "base_url" in node_config and "host" not in model_kwargs:
            model_kwargs["base_url"] = node_config["base_url"]
        if "api_key" in node_config:
            model_kwargs["api_key"] = node_config["api_key"]
    elif model_type == "llamacpp":
        model_kwargs["num_ctx"] = node_config.get("num_ctx", 131072)
        model_kwargs["n_gpu_layers"] = node_config.get("n_gpu_layers", -1)

    # Create model using the factory - model_name passed as positional argument only
    return ModelClient(model_type, model_name, **model_kwargs)


def get_research_agent_mode(config: Dict[str, Any]) -> str:
    """
    Determine the current research agent mode from configuration.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        "single" or "multi" based on configuration
    """
    # Check for explicit mode setting
    mode = config.get("research_agent_mode")
    if mode in ["single", "multi"]:
        return mode
    
    # Infer mode from configuration presence
    if "multi_agent_config" in config:
        return "multi"
    elif "research_agent_model_config" in config:
        return "single"
    else:
        # Default to single mode
        return "single"


def validate_dual_mode_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate dual-mode research agent configuration.
    
    Args:
        config: Configuration dictionary to validate
        
    Returns:
        Dictionary with validation results
    """
    validation_results = {
        "valid": True,
        "issues": [],
        "mode": None,
        "single_agent_valid": False,
        "multi_agent_valid": False
    }
    
    try:
        mode = get_research_agent_mode(config)
        validation_results["mode"] = mode
        
        # Validate single-agent configuration
        single_config = config.get("research_agent_model_config", {})
        if single_config and "boss_model" in single_config:
            boss_model = single_config["boss_model"]
            if boss_model.get("model_type") and boss_model.get("model_name"):
                validation_results["single_agent_valid"] = True
            else:
                validation_results["issues"].append("Single-agent boss_model missing model_type or model_name")
        else:
            validation_results["issues"].append("Single-agent configuration missing or incomplete")
        
        # Validate multi-agent configuration
        multi_config = config.get("multi_agent_config", {})
        if multi_config:
            boss_model = multi_config.get("boss_model", {})
            if boss_model.get("model_type") and boss_model.get("model_name"):
                validation_results["multi_agent_valid"] = True
                
                # Check specialized models
                specialized = multi_config.get("specialized_models", {})
                for agent_name, agent_config in specialized.items():
                    if not (agent_config.get("model_type") and agent_config.get("model_name")):
                        validation_results["issues"].append(f"Multi-agent {agent_name} missing model_type or model_name")
            else:
                validation_results["issues"].append("Multi-agent boss_model missing model_type or model_name")
        else:
            validation_results["issues"].append("Multi-agent configuration missing")
        
        # Overall validation
        if mode == "single" and not validation_results["single_agent_valid"]:
            validation_results["valid"] = False
        elif mode == "multi" and not validation_results["multi_agent_valid"]:
            validation_results["valid"] = False
        elif not validation_results["single_agent_valid"] and not validation_results["multi_agent_valid"]:
            validation_results["valid"] = False
        
        return validation_results
        
    except Exception as e:
        validation_results["valid"] = False
        validation_results["issues"].append(f"Validation error: {str(e)}")
        return validation_results


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
        # Use the enhanced dual-mode validation
        validation_results = validate_dual_mode_config(config)
        return validation_results["valid"]
        
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


def create_default_dual_mode_config() -> Dict[str, Any]:
    """
    Create a default dual-mode configuration for research agent.
    
    Returns:
        Default configuration dictionary supporting both single and multi-agent modes
    """
    # Default model configuration
    default_model = {
        "model_type": "openai",
        "model_name": "gpt-4o-mini",
        "temperature": 0.1,
        "max_new_tokens": 4096
    }
    
    return {
        "research_agent_mode": "single",
        "single_agent_config": {
            "model_config": {
                "boss_model": default_model.copy(),
                "query_planner_model": default_model.copy(),
                "evidence_selector_model": default_model.copy(),
                "compression_model": default_model.copy(),
                "answer_generator_model": default_model.copy()
            },
            "max_research_loops": 3,
            "max_research_context_tokens": 15000,
            "compress_to_ratio": 0.2,
            "search_config": {
                "local_limit": 20,
                "external_limit": 15
            }
        },
        "multi_agent_config": {
            "parallel_agents": 4,
            "task_timeout": 300,
            "boss_model": default_model.copy(),
            "specialized_models": {
                "question_generator": default_model.copy(),
                "research_agent": default_model.copy(),
                "analysis_agent": default_model.copy(),
                "verification_agent": default_model.copy(),
                "synthesis_agent": default_model.copy()
            },
            "search_config": {
                "local_limit": 25,
                "external_limit": 20
            },
            "synthesis_config": {
                "conflict_resolution": "weighted_consensus",
                "citation_strategy": "comprehensive"
            }
        },
        "embedding_model": {
            "model_type": "sentence-transformer",
            "model_name": "Alibaba-NLP/gte-large-en-v1.5",
            "trust_remote_code": True
        }
    } 