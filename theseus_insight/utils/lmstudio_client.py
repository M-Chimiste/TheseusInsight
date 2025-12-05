"""
LMStudio client cache utility.

The LMStudio SDK uses a singleton pattern for its default client, which can only
be configured once per process. This module provides a caching layer to reuse
LMStudio inference clients across the application, avoiding the 
"Default client is already created" error.
"""

import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Module-level cache for LMStudio inference clients
# Key: (host, model_name) tuple
# Value: LMStudioInference instance
_lmstudio_client_cache: Dict[tuple, Any] = {}

# Track the configured host (LMStudio only allows one default client per process)
_configured_host: Optional[str] = None


def get_lmstudio_client(
    model_name: str,
    max_new_tokens: int = 512,
    temperature: float = 0.1,
    host: str = "localhost:1234",
    context_length: Optional[int] = None,
    **kwargs
):
    """
    Get or create an LMStudio inference client.
    
    This function caches clients to avoid the singleton error when the LMStudio
    SDK tries to reconfigure the default client.
    
    Args:
        model_name: Name of the model to use
        max_new_tokens: Maximum tokens to generate
        temperature: Sampling temperature
        host: LMStudio server host (e.g., "localhost:1234")
        context_length: Optional context length
        **kwargs: Additional arguments passed to LLMModelFactory
        
    Returns:
        LMStudioInference instance (cached if available)
        
    Raises:
        ValueError: If trying to use a different host than previously configured
    """
    global _configured_host
    
    cache_key = (host, model_name)
    
    # Check if we have a cached client for this exact configuration
    if cache_key in _lmstudio_client_cache:
        logger.debug(f"Reusing cached LMStudio client for {model_name}@{host}")
        return _lmstudio_client_cache[cache_key]
    
    # Check if we're trying to use a different host than previously configured
    if _configured_host is not None and _configured_host != host:
        # LMStudio SDK limitation: can't change host after initial configuration
        # Try to find any cached client for the same host
        for (cached_host, cached_model), client in _lmstudio_client_cache.items():
            if cached_host == _configured_host:
                logger.warning(
                    f"LMStudio only supports one host per process. "
                    f"Requested host '{host}' differs from configured host '{_configured_host}'. "
                    f"Returning cached client for {cached_model}@{cached_host}"
                )
                return client
        
        raise ValueError(
            f"LMStudio SDK limitation: Cannot change host from '{_configured_host}' to '{host}'. "
            f"Restart the application to use a different host."
        )
    
    # Create new client
    from LLMFactory import LLMModelFactory
    
    create_kwargs = {
        'model_type': 'lmstudio',
        'model_name': model_name,
        'max_new_tokens': max_new_tokens,
        'temperature': temperature,
        'host': host,
        **kwargs
    }
    
    if context_length is not None:
        create_kwargs['context_length'] = context_length
    
    try:
        client = LLMModelFactory.create_model(**create_kwargs)
        _lmstudio_client_cache[cache_key] = client
        _configured_host = host
        logger.info(f"Created LMStudio client for {model_name}@{host}")
        return client
    except Exception as e:
        # Handle the case where default client already exists (race condition or previous error)
        if "already created" in str(e).lower():
            logger.warning(f"LMStudio default client already exists, checking cache...")
            # Return any cached client for this host
            for (cached_host, cached_model), cached_client in _lmstudio_client_cache.items():
                if cached_host == host:
                    logger.info(f"Found cached client for {cached_model}@{cached_host}")
                    _lmstudio_client_cache[cache_key] = cached_client
                    return cached_client
        raise


def clear_lmstudio_cache():
    """
    Clear the LMStudio client cache.
    
    Note: This doesn't reset the LMStudio SDK's internal state. 
    The configured host will still be locked until process restart.
    """
    global _lmstudio_client_cache, _configured_host
    _lmstudio_client_cache.clear()
    # Note: We intentionally don't reset _configured_host because
    # the LMStudio SDK's default client is still configured
    logger.info("LMStudio client cache cleared")


def get_configured_host() -> Optional[str]:
    """Get the currently configured LMStudio host, if any."""
    return _configured_host


def verify_model_loaded(host: str = "localhost:1234", model_name: Optional[str] = None) -> bool:
    """
    Verify that the LM Studio server has models loaded.
    
    This can help detect when LM Studio has auto-unloaded models after
    extended periods of inactivity.
    
    Args:
        host: LM Studio server host
        model_name: Optional specific model name to check for
        
    Returns:
        True if models are loaded (and optionally the specific model), False otherwise
    """
    import requests
    
    try:
        # LM Studio's API endpoint to list models
        url = f"http://{host}/v1/models"
        response = requests.get(url, timeout=5)
        
        if response.status_code != 200:
            logger.warning(f"LM Studio models endpoint returned status {response.status_code}")
            return False
        
        data = response.json()
        models = data.get('data', [])
        
        if not models:
            logger.warning("LM Studio reports no models loaded (totalLoadedModels: 0)")
            return False
        
        if model_name:
            # Check if the specific model is loaded
            loaded_model_ids = [m.get('id', '') for m in models]
            if model_name not in loaded_model_ids:
                logger.warning(f"Model '{model_name}' not found in loaded models: {loaded_model_ids}")
                return False
        
        logger.debug(f"LM Studio has {len(models)} model(s) loaded")
        return True
        
    except requests.exceptions.RequestException as e:
        logger.warning(f"Failed to verify LM Studio models: {e}")
        return False
    except Exception as e:
        logger.warning(f"Error checking LM Studio models: {e}")
        return False

