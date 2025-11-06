"""Data access layer for inference server management (Ollama, LMStudio)."""

from typing import List, Optional, Dict, Any
from datetime import datetime
from ..db import get_cursor
import asyncio
import json


class InferenceServer:
    """Represents an inference server configuration (Ollama or LMStudio)."""

    def __init__(
        self,
        id: int,
        name: str,
        url: str,
        provider: str = "ollama",
        enabled: bool = True,
        config_json: Optional[Dict[str, Any]] = None,
        model_name: Optional[str] = None,
        model_config: Optional[Dict[str, Any]] = None,
        notes: Optional[str] = None,
        last_tested_at: Optional[datetime] = None,
        last_test_latency_ms: Optional[int] = None,
        last_test_ok: Optional[bool] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None
    ):
        self.id = id
        self.name = name
        self.url = url
        self.provider = provider
        self.enabled = enabled
        self.config_json = config_json or {}
        self.model_name = model_name
        self.model_config = model_config or {}
        self.notes = notes
        self.last_tested_at = last_tested_at
        self.last_test_latency_ms = last_test_latency_ms
        self.last_test_ok = last_test_ok
        self.created_at = created_at
        self.updated_at = updated_at

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'InferenceServer':
        """Create an InferenceServer instance from a dictionary."""
        # Handle config_json which might be a string from DB
        config_json = data.get('config_json', {})
        if isinstance(config_json, str):
            try:
                config_json = json.loads(config_json)
            except (json.JSONDecodeError, TypeError):
                config_json = {}

        # Handle model_config which might be a string from DB
        model_config = data.get('model_config', {})
        if isinstance(model_config, str):
            try:
                model_config = json.loads(model_config)
            except (json.JSONDecodeError, TypeError):
                model_config = {}

        return cls(
            id=data['id'],
            name=data['name'],
            url=data['url'],
            provider=data.get('provider', 'ollama'),
            enabled=data.get('enabled', True),
            config_json=config_json,
            model_name=data.get('model_name'),
            model_config=model_config,
            notes=data.get('notes'),
            last_tested_at=data.get('last_tested_at'),
            last_test_latency_ms=data.get('last_test_latency_ms'),
            last_test_ok=data.get('last_test_ok'),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at')
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'id': self.id,
            'name': self.name,
            'url': self.url,
            'provider': self.provider,
            'enabled': self.enabled,
            'config_json': self.config_json,
            'model_name': self.model_name,
            'model_config': self.model_config,
            'notes': self.notes,
            'last_tested_at': self.last_tested_at.isoformat() if self.last_tested_at else None,
            'last_test_latency_ms': self.last_test_latency_ms,
            'last_test_ok': self.last_test_ok,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class InferenceServersRepository:
    """Repository for managing inference server configurations (Ollama, LMStudio)."""

    @staticmethod
    def get_all() -> List[InferenceServer]:
        """Get all inference servers."""
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT id, name, url, provider, enabled, config_json, model_name, model_config, notes,
                       last_tested_at, last_test_latency_ms, last_test_ok,
                       created_at, updated_at
                FROM inference_servers
                ORDER BY provider, name
            """)
            rows = cursor.fetchall()
            return [InferenceServer.from_dict(dict(row)) for row in rows]

    @staticmethod
    def get_enabled(provider: Optional[str] = None) -> List[InferenceServer]:
        """
        Get all enabled inference servers, optionally filtered by provider.

        Args:
            provider: Filter by provider ('ollama', 'lmstudio', or None for all)
        """
        with get_cursor() as cursor:
            if provider:
                cursor.execute("""
                    SELECT id, name, url, provider, enabled, config_json, model_name, model_config, notes,
                           last_tested_at, last_test_latency_ms, last_test_ok,
                           created_at, updated_at
                    FROM inference_servers
                    WHERE enabled = TRUE AND provider = %s
                    ORDER BY name
                """, (provider,))
            else:
                cursor.execute("""
                    SELECT id, name, url, provider, enabled, config_json, model_name, model_config, notes,
                           last_tested_at, last_test_latency_ms, last_test_ok,
                           created_at, updated_at
                    FROM inference_servers
                    WHERE enabled = TRUE
                    ORDER BY provider, name
                """)
            rows = cursor.fetchall()
            return [InferenceServer.from_dict(dict(row)) for row in rows]

    @staticmethod
    def get_by_provider(provider: str) -> List[InferenceServer]:
        """Get all servers for a specific provider."""
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT id, name, url, provider, enabled, config_json, model_name, model_config, notes,
                       last_tested_at, last_test_latency_ms, last_test_ok,
                       created_at, updated_at
                FROM inference_servers
                WHERE provider = %s
                ORDER BY name
            """, (provider,))
            rows = cursor.fetchall()
            return [InferenceServer.from_dict(dict(row)) for row in rows]

    @staticmethod
    def get_by_id(server_id: int) -> Optional[InferenceServer]:
        """Get an inference server by ID."""
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT id, name, url, provider, enabled, config_json, model_name, model_config, notes,
                       last_tested_at, last_test_latency_ms, last_test_ok,
                       created_at, updated_at
                FROM inference_servers
                WHERE id = %s
            """, (server_id,))
            row = cursor.fetchone()
            return InferenceServer.from_dict(dict(row)) if row else None

    @staticmethod
    def get_by_url(url: str, provider: Optional[str] = None) -> Optional[InferenceServer]:
        """Get an inference server by URL, optionally filtered by provider."""
        with get_cursor() as cursor:
            if provider:
                cursor.execute("""
                    SELECT id, name, url, provider, enabled, config_json, model_name, model_config, notes,
                           last_tested_at, last_test_latency_ms, last_test_ok,
                           created_at, updated_at
                    FROM inference_servers
                    WHERE url = %s AND provider = %s
                """, (url, provider))
            else:
                cursor.execute("""
                    SELECT id, name, url, provider, enabled, config_json, model_name, model_config, notes,
                           last_tested_at, last_test_latency_ms, last_test_ok,
                           created_at, updated_at
                    FROM inference_servers
                    WHERE url = %s
                """, (url,))
            row = cursor.fetchone()
            return InferenceServer.from_dict(dict(row)) if row else None

    @staticmethod
    def create(
        name: str,
        url: str,
        provider: str = "ollama",
        enabled: bool = True,
        config_json: Optional[Dict[str, Any]] = None,
        model_name: Optional[str] = None,
        model_config: Optional[Dict[str, Any]] = None,
        notes: Optional[str] = None
    ) -> InferenceServer:
        """Create a new inference server."""
        config_json = config_json or {}
        model_config = model_config or {}
        with get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO inference_servers (name, url, provider, enabled, config_json, model_name, model_config, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, name, url, provider, enabled, config_json, model_name, model_config, notes,
                          last_tested_at, last_test_latency_ms, last_test_ok,
                          created_at, updated_at
            """, (name, url, provider, enabled, json.dumps(config_json), model_name, json.dumps(model_config), notes))
            row = cursor.fetchone()
            return InferenceServer.from_dict(dict(row))

    @staticmethod
    def update(
        server_id: int,
        name: str,
        url: str,
        provider: str,
        enabled: bool,
        config_json: Optional[Dict[str, Any]] = None,
        model_name: Optional[str] = None,
        model_config: Optional[Dict[str, Any]] = None,
        notes: Optional[str] = None
    ) -> Optional[InferenceServer]:
        """Update an inference server."""
        config_json = config_json or {}
        model_config = model_config or {}
        with get_cursor() as cursor:
            cursor.execute("""
                UPDATE inference_servers
                SET name = %s, url = %s, provider = %s, enabled = %s,
                    config_json = %s, model_name = %s, model_config = %s, notes = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                RETURNING id, name, url, provider, enabled, config_json, model_name, model_config, notes,
                          last_tested_at, last_test_latency_ms, last_test_ok,
                          created_at, updated_at
            """, (name, url, provider, enabled, json.dumps(config_json), model_name, json.dumps(model_config), notes, server_id))
            row = cursor.fetchone()
            return InferenceServer.from_dict(dict(row)) if row else None

    @staticmethod
    def delete(server_id: int) -> bool:
        """Delete an inference server."""
        with get_cursor() as cursor:
            cursor.execute("DELETE FROM inference_servers WHERE id = %s", (server_id,))
            return cursor.rowcount > 0

    @staticmethod
    def update_test_result(server_id: int, latency_ms: Optional[int], success: bool) -> bool:
        """Update the test result for an inference server."""
        with get_cursor() as cursor:
            cursor.execute("""
                UPDATE inference_servers
                SET last_tested_at = CURRENT_TIMESTAMP,
                    last_test_latency_ms = %s,
                    last_test_ok = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (latency_ms, success, server_id))
            return cursor.rowcount > 0

    @staticmethod
    def toggle_enabled(server_id: int) -> Optional[InferenceServer]:
        """Toggle the enabled status of an inference server."""
        with get_cursor() as cursor:
            cursor.execute("""
                UPDATE inference_servers
                SET enabled = NOT enabled, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                RETURNING id, name, url, provider, enabled, config_json, model_name, model_config, notes,
                          last_tested_at, last_test_latency_ms, last_test_ok,
                          created_at, updated_at
            """, (server_id,))
            row = cursor.fetchone()
            return InferenceServer.from_dict(dict(row)) if row else None

    @staticmethod
    def get_enabled_urls(provider: Optional[str] = None) -> List[str]:
        """Get list of URLs for enabled servers, optionally filtered by provider."""
        with get_cursor() as cursor:
            if provider:
                cursor.execute("""
                    SELECT url FROM inference_servers
                    WHERE enabled = TRUE AND provider = %s
                    ORDER BY name
                """, (provider,))
            else:
                cursor.execute("""
                    SELECT url FROM inference_servers
                    WHERE enabled = TRUE
                    ORDER BY provider, name
                """)
            rows = cursor.fetchall()
            return [row['url'] for row in rows]

    @staticmethod
    def get_server_health_stats(provider: Optional[str] = None) -> Dict[str, Any]:
        """Get health statistics for servers, optionally filtered by provider."""
        with get_cursor() as cursor:
            if provider:
                cursor.execute("""
                    SELECT
                        COUNT(*) as total_servers,
                        COUNT(*) FILTER (WHERE enabled = TRUE) as enabled_servers,
                        COUNT(*) FILTER (WHERE last_test_ok = TRUE) as healthy_servers,
                        AVG(last_test_latency_ms) FILTER (WHERE last_test_ok = TRUE) as avg_latency
                    FROM inference_servers
                    WHERE provider = %s
                """, (provider,))
            else:
                cursor.execute("""
                    SELECT
                        COUNT(*) as total_servers,
                        COUNT(*) FILTER (WHERE enabled = TRUE) as enabled_servers,
                        COUNT(*) FILTER (WHERE last_test_ok = TRUE) as healthy_servers,
                        AVG(last_test_latency_ms) FILTER (WHERE last_test_ok = TRUE) as avg_latency
                    FROM inference_servers
                """)
            row = cursor.fetchone()
            return dict(row) if row else {}


# Backward compatibility aliases
OllamaServer = InferenceServer
OllamaServersRepository = InferenceServersRepository
