"""Helpers shared by the harvest-and-judge utility scripts.

Extracted verbatim from utils/harvest_and_judge.py and
utils/paperswithcode_harvest_and_judge.py, which each carried identical
copies. The checkpoint format ({stage}.pkl holding
{'data', 'timestamp', 'stage'}) is a frozen contract — resumable runs
written by older versions must keep loading.

Note: the per-script existence checkers (check_paper_exists,
check_existing_papers_parallel) intentionally stay in their scripts —
the arXiv variant uses bulk in-memory sets while the PapersWithCode
variant queries the repository per row.
"""
import os
import pickle
import time
from pathlib import Path
from typing import Any, Dict

from LLMFactory import LLMModelFactory
from LLMFactory.providers import (
    AnthropicInference, GeminiInference, OllamaInference, OpenAIInference
)

from ..data_access import PaperRepository
from .common_utils import purge_ollama_cache

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")


def get_paper_count() -> int:
    """Get the total number of papers in the database (-1 on error)."""
    try:
        papers = PaperRepository.get_all()
        return len(papers)
    except Exception:
        return -1  # Return -1 to indicate error/unknown


def should_skip_database_checks(verbose: bool = True) -> bool:
    """Skip existence checks when the database is empty or tiny."""
    try:
        paper_count = get_paper_count()

        if paper_count == 0:
            if verbose:
                print("📊 Database is empty - skipping existence checks")
            return True
        elif paper_count < 100:
            if verbose:
                print(f"📊 Database has only {paper_count} papers - skipping existence checks for speed")
            return True
        else:
            if verbose:
                print(f"📊 Database has {paper_count} papers - performing existence checks")
            return False

    except Exception as e:
        if verbose:
            print(f"⚠️ Could not check database size: {e} - performing existence checks")
        return False


def _checkpoint_path(checkpoint_dir: str, stage: str) -> Path:
    return Path(checkpoint_dir) / f"{stage}.pkl"


def save_checkpoint(checkpoint_dir: str, stage: str, data: Any, verbose: bool = True) -> None:
    Path(checkpoint_dir).mkdir(parents=True, exist_ok=True)
    cp = {
        "data": data,
        "timestamp": time.time(),
        "stage": stage,
    }
    with open(_checkpoint_path(checkpoint_dir, stage), "wb") as f:
        pickle.dump(cp, f)
    if verbose:
        print(f"✅ Checkpoint saved: {stage}")


def load_checkpoint(checkpoint_dir: str, stage: str, verbose: bool = True):
    path = _checkpoint_path(checkpoint_dir, stage)
    if path.exists():
        with open(path, "rb") as f:
            cp = pickle.load(f)
        if verbose:
            print(f"📂 Loaded checkpoint '{stage}' from {time.ctime(cp['timestamp'])}")
        return cp["data"]
    return None


def load_inference_model(cfg: Dict[str, Any], verbose: bool = True):
    """Load an inference model (ollama/openai/anthropic/gemini/lmstudio)."""
    model_type = cfg.get("model_type")
    model_name = cfg.get("model_name")
    max_new_tokens = cfg.get("max_new_tokens", 4096)
    temperature = cfg.get("temperature", 0.1)
    num_ctx = cfg.get("num_ctx")

    if verbose:
        print(f"🤖 Loading {model_type} model: {model_name}")

    if model_type == "ollama":
        kwargs = {
            "model_name": model_name,
            "max_new_tokens": max_new_tokens,
            "temperature": temperature,
            "url": OLLAMA_URL,
        }
        if num_ctx is not None:
            kwargs["num_ctx"] = num_ctx
        return OllamaInference(**kwargs)
    if model_type == "openai":
        return OpenAIInference(model_name, max_new_tokens, temperature)
    if model_type == "anthropic":
        return AnthropicInference(model_name, max_new_tokens, temperature)
    if model_type == "gemini":
        return GeminiInference(model_name, max_new_tokens, temperature)
    if model_type == "lmstudio":
        # LMStudio needs host parameter instead of url
        host = cfg.get('host')
        if not host:
            host = os.getenv('LMSTUDIO_HOST', 'localhost:1234')
        kwargs = {
            'model_type': 'lmstudio',
            'model_name': model_name,
            'max_new_tokens': max_new_tokens,
            'temperature': temperature,
            'host': host
        }
        if num_ctx is not None:
            kwargs['context_length'] = num_ctx
        return LLMModelFactory.create_model(**kwargs)
    raise ValueError(f"Unsupported model type: {model_type}")


def clear_judge_cache(inference, model_name: str, verbose: bool = True):
    """Purge the Ollama cache for a judge model (no-op for other providers)."""
    try:
        if hasattr(inference, "provider") and inference.provider == "ollama":
            if verbose:
                print(f"🧹 Clearing Ollama cache for {model_name}")
            purge_ollama_cache(OLLAMA_URL, model_name)
    except Exception as e:
        if verbose:
            print(f"⚠️ Failed to purge cache for {model_name}: {e}")
