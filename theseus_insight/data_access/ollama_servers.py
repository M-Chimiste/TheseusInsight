"""Data access layer for Ollama server management."""

from typing import List, Optional, Dict, Any
from datetime import datetime
from ..db import get_cursor
import asyncio


class OllamaServer:
    """Represents an Ollama server configuration."""

    def __init__(
        self,
        id: int,
        name: str,
        url: str,
        enabled: bool = True,
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
        self.enabled = enabled
        self.notes = notes
        self.last_tested_at = last_tested_at
        self.last_test_latency_ms = last_test_latency_ms
        self.last_test_ok = last_test_ok
        self.created_at = created_at
        self.updated_at = updated_at

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OllamaServer':
        """Create an OllamaServer instance from a dictionary."""
        return cls(
            id=data['id'],
            name=data['name'],
            url=data['url'],
            enabled=data.get('enabled', True),
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
            'enabled': self.enabled,
            'notes': self.notes,
            'last_tested_at': self.last_tested_at.isoformat() if self.last_tested_at else None,
            'last_test_latency_ms': self.last_test_latency_ms,
            'last_test_ok': self.last_test_ok,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class OllamaServersRepository:
    """Repository for managing Ollama server configurations."""

    @staticmethod
    def get_all() -> List[OllamaServer]:
        """Get all Ollama servers."""
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT id, name, url, enabled, notes, last_tested_at,
                       last_test_latency_ms, last_test_ok, created_at, updated_at
                FROM ollama_servers
                ORDER BY name
            """)
            rows = cursor.fetchall()
            return [OllamaServer.from_dict(dict(row)) for row in rows]

    @staticmethod
    def get_enabled() -> List[OllamaServer]:
        """Get all enabled Ollama servers."""
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT id, name, url, enabled, notes, last_tested_at,
                       last_test_latency_ms, last_test_ok, created_at, updated_at
                FROM ollama_servers
                WHERE enabled = TRUE
                ORDER BY name
            """)
            rows = cursor.fetchall()
            return [OllamaServer.from_dict(dict(row)) for row in rows]

    @staticmethod
    def get_by_id(server_id: int) -> Optional[OllamaServer]:
        """Get an Ollama server by ID."""
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT id, name, url, enabled, notes, last_tested_at,
                       last_test_latency_ms, last_test_ok, created_at, updated_at
                FROM ollama_servers
                WHERE id = %s
            """, (server_id,))
            row = cursor.fetchone()
            return OllamaServer.from_dict(dict(row)) if row else None

    @staticmethod
    def get_by_url(url: str) -> Optional[OllamaServer]:
        """Get an Ollama server by URL."""
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT id, name, url, enabled, notes, last_tested_at,
                       last_test_latency_ms, last_test_ok, created_at, updated_at
                FROM ollama_servers
                WHERE url = %s
            """, (url,))
            row = cursor.fetchone()
            return OllamaServer.from_dict(dict(row)) if row else None

    @staticmethod
    def create(name: str, url: str, notes: Optional[str] = None) -> OllamaServer:
        """Create a new Ollama server."""
        with get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO ollama_servers (name, url, notes)
                VALUES (%s, %s, %s)
                RETURNING id, name, url, enabled, notes, last_tested_at,
                          last_test_latency_ms, last_test_ok, created_at, updated_at
            """, (name, url, notes))
            row = cursor.fetchone()
            return OllamaServer.from_dict(dict(row))

    @staticmethod
    def update(server_id: int, name: str, url: str, enabled: bool, notes: Optional[str] = None) -> Optional[OllamaServer]:
        """Update an Ollama server."""
        with get_cursor() as cursor:
            cursor.execute("""
                UPDATE ollama_servers
                SET name = %s, url = %s, enabled = %s, notes = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                RETURNING id, name, url, enabled, notes, last_tested_at,
                          last_test_latency_ms, last_test_ok, created_at, updated_at
            """, (name, url, enabled, notes, server_id))
            row = cursor.fetchone()
            return OllamaServer.from_dict(dict(row)) if row else None

    @staticmethod
    def delete(server_id: int) -> bool:
        """Delete an Ollama server."""
        with get_cursor() as cursor:
            cursor.execute("DELETE FROM ollama_servers WHERE id = %s", (server_id,))
            return cursor.rowcount > 0

    @staticmethod
    def update_test_result(server_id: int, latency_ms: Optional[int], success: bool) -> bool:
        """Update the test result for an Ollama server."""
        with get_cursor() as cursor:
            cursor.execute("""
                UPDATE ollama_servers
                SET last_tested_at = CURRENT_TIMESTAMP,
                    last_test_latency_ms = %s,
                    last_test_ok = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (latency_ms, success, server_id))
            return cursor.rowcount > 0

    @staticmethod
    def toggle_enabled(server_id: int) -> Optional[OllamaServer]:
        """Toggle the enabled status of an Ollama server."""
        with get_cursor() as cursor:
            cursor.execute("""
                UPDATE ollama_servers
                SET enabled = NOT enabled, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                RETURNING id, name, url, enabled, notes, last_tested_at,
                          last_test_latency_ms, last_test_ok, created_at, updated_at
            """, (server_id,))
            row = cursor.fetchone()
            return OllamaServer.from_dict(dict(row)) if row else None

    @staticmethod
    def get_enabled_urls() -> List[str]:
        """Get list of URLs for enabled servers."""
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT url FROM ollama_servers WHERE enabled = TRUE ORDER BY name
            """)
            rows = cursor.fetchall()
            return [row['url'] for row in rows]

    @staticmethod
    def get_server_health_stats() -> Dict[str, Any]:
        """Get health statistics for all servers."""
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT
                    COUNT(*) as total_servers,
                    COUNT(*) FILTER (WHERE enabled = TRUE) as enabled_servers,
                    COUNT(*) FILTER (WHERE last_test_ok = TRUE) as healthy_servers,
                    AVG(last_test_latency_ms) FILTER (WHERE last_test_ok = TRUE) as avg_latency
                FROM ollama_servers
            """)
            row = cursor.fetchone()
            return dict(row) if row else {}
