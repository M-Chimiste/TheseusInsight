"""Inference-model loading for the pipelines (extracted from
TheseusInsight in B8).

Providers are imported lazily so importing this module stays cheap; API
keys are read from the environment at call time, matching the original
behavior (the god class read module-level constants captured at import,
but those were themselves os.getenv reads).
"""
import os


def load_inference_model(
    model_type,
    model_name,
    max_new_tokens,
    temperature,
    num_ctx=None,
    host=None,
    request_timeout_sec=None,
):
    """Load the appropriate inference model based on model type."""
    if model_type == "anthropic":
        if os.getenv("ANTHROPIC_API_KEY") is None:
            raise ValueError("Anthropic API key is not set.")
        from LLMFactory.providers import AnthropicInference
        return AnthropicInference(model_name, max_new_tokens, temperature)

    elif model_type == "openai":
        if os.getenv("OPENAI_API_KEY") is None:
            raise ValueError("OpenAI API key is not set.")
        from LLMFactory.providers import OpenAIInference
        return OpenAIInference(model_name, max_new_tokens, temperature)

    elif model_type == "gemini":
        if os.getenv("GOOGLE_API_KEY") is None:
            raise ValueError("Google API key is not set.")
        from LLMFactory.providers import GeminiInference
        return GeminiInference(model_name, max_new_tokens, temperature)

    elif model_type == "ollama":
        from LLMFactory.providers import OllamaInference
        ollama_url = host or os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
        kwargs = {
            'model_name': model_name,
            'max_new_tokens': max_new_tokens,
            'temperature': temperature,
            'url': ollama_url
        }
        if num_ctx is not None:
            kwargs['num_ctx'] = num_ctx
        return OllamaInference(**kwargs)

    elif model_type == "lmstudio":
        from theseus_insight.utils.lmstudio_client import get_lmstudio_client
        # LMStudio needs host parameter instead of url
        # Respect explicit config first, then env, then localhost default
        lmstudio_host = host or os.getenv('LMSTUDIO_HOST', 'localhost:1234')
        return get_lmstudio_client(
            model_name=model_name,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            host=lmstudio_host,
            context_length=num_ctx,
            request_timeout_sec=request_timeout_sec,
        )

    else:
        raise ValueError(f"Invalid model type: {model_type}")
