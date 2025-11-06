from __future__ import annotations

from typing import List, Dict

from ..db import get_cursor

# Initial providers that should be available in the system
INITIAL_PROVIDERS = [
    {"id": 1, "name": "ollama"},
    {"id": 2, "name": "gemini"},
    {"id": 3, "name": "openai"},
    {"id": 4, "name": "sentence-transformers"},
    {"id": 5, "name": "llamacpp"},
    {"id": 6, "name": "anthropic"},
    {"id": 7, "name": "ollama-embed"},
    {"id": 8, "name": "custom-oai"},
    {"id": 9, "name": "lmstudio"},
]


class ModelProviderRepository:
    """CRUD for `model_providers` table."""

    @staticmethod
    def all() -> List[Dict[str, str]]:
        with get_cursor() as cur:
            cur.execute("SELECT id, name FROM model_providers ORDER BY id")
            return cur.fetchall()

    @staticmethod
    def add(provider_id: int, name: str) -> None:
        with get_cursor() as cur:
            cur.execute(
                "INSERT INTO model_providers (id, name) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (provider_id, name),
            )

    @staticmethod
    def delete(provider_id: int) -> None:
        with get_cursor() as cur:
            cur.execute("DELETE FROM model_providers WHERE id = %s", (provider_id,))

    @staticmethod
    def count() -> int:
        """Get the total number of model providers."""
        with get_cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM model_providers")
            result = cur.fetchone()
            return result["count"] if result else 0

    @staticmethod
    def initialize_default_providers() -> None:
        """Initialize the default model providers if the table is empty."""
        current_count = ModelProviderRepository.count()
        
        if current_count == 0:
            print("INFO:     No model providers found. Initializing default providers...")
            for provider in INITIAL_PROVIDERS:
                ModelProviderRepository.add(provider["id"], provider["name"])
            print(f"INFO:     Initialized {len(INITIAL_PROVIDERS)} default model providers")
        else:
            print(f"INFO:     Found {current_count} existing model providers")

    @staticmethod
    def ensure_providers_exist() -> None:
        """Ensure that all required providers exist, adding any missing ones."""
        existing_providers = {p["name"] for p in ModelProviderRepository.all()}
        
        missing_providers = []
        for provider in INITIAL_PROVIDERS:
            if provider["name"] not in existing_providers:
                missing_providers.append(provider)
        
        if missing_providers:
            print(f"INFO:     Adding {len(missing_providers)} missing model providers...")
            for provider in missing_providers:
                ModelProviderRepository.add(provider["id"], provider["name"])
            print(f"INFO:     Added missing providers: {[p['name'] for p in missing_providers]}") 