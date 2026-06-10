"""Central access to the orchestration configuration (B10).

The stored format is unchanged: a JSON string under the 'orchestration'
key in the settings table, seeded from config/orchestration.json at
startup. ~20 call sites used to inline the fetch+json.loads; they now go
through these two functions. Per-site behavior when the config is
missing (404/500/defaults/file fallback) intentionally stays at the
call sites.

Deliberately NOT cached: the Settings UI updates the stored config at
runtime and consumers expect the next read to see it. A cached accessor
would need invalidation plumbing — out of scope for a
behavior-preserving refactor.
"""
import json
from pathlib import Path
from typing import Any, Dict, Optional

from .data_access.settings import SettingsRepository


def load_orchestration_config() -> Optional[Dict[str, Any]]:
    """Parse the stored orchestration config; None when unset."""
    raw = SettingsRepository.get("orchestration")
    if raw:
        return json.loads(raw)
    return None


def get_orchestration_config(verbose: bool = False) -> Dict[str, Any]:
    """Orchestration config with fallback hierarchy: DB -> config file -> {}."""
    config = load_orchestration_config()
    if config is not None:
        if verbose:
            print("📊 Using orchestration config from database settings")
        return config

    try:
        config_path = Path(__file__).resolve().parent.parent / "config" / "orchestration.json"
        config = json.loads(config_path.read_text())
        if verbose:
            print("📊 Using orchestration config from config file")
        return config
    except Exception as e:
        print(f"Warning: Could not load orchestration config from file: {e}")
        if verbose:
            print("📊 Using empty orchestration config (defaults only)")
        return {}
