"""Ollama Server Management API endpoints."""

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional, Dict, Any
from datetime import datetime
import asyncio
import httpx
import time

from ...data_access.ollama_servers import OllamaServersRepository, OllamaServer
from ...data_access.settings import SettingsRepository

router = APIRouter(prefix="/api/settings/ollama-servers", tags=["ollama-servers"])


# Request/Response Models
class OllamaServerCreate(BaseModel):
    """Request model for creating a new Ollama server."""
    name: str = Field(..., min_length=1, max_length=100, description="Server name")
    url: str = Field(..., description="Server URL (e.g., http://localhost:11434)")
    notes: Optional[str] = Field(None, description="Optional notes about the server")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Local Ollama",
                "url": "http://localhost:11434",
                "notes": "Default local Ollama installation"
            }
        }


class OllamaServerUpdate(BaseModel):
    """Request model for updating an Ollama server."""
    name: str = Field(..., min_length=1, max_length=100, description="Server name")
    url: str = Field(..., description="Server URL")
    enabled: bool = Field(True, description="Whether the server is enabled")
    notes: Optional[str] = Field(None, description="Optional notes about the server")


class OllamaServerResponse(BaseModel):
    """Response model for Ollama server data."""
    id: int
    name: str
    url: str
    enabled: bool
    notes: Optional[str] = None
    last_tested_at: Optional[str] = None
    last_test_latency_ms: Optional[int] = None
    last_test_ok: Optional[bool] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ServerTestResult(BaseModel):
    """Response model for server connectivity test."""
    success: bool
    latency_ms: Optional[int] = None
    error: Optional[str] = None
    version: Optional[str] = None
    models_available: Optional[List[str]] = None


class ServerTestRequest(BaseModel):
    """Request model for testing server connectivity."""
    url: str = Field(..., description="Server URL to test")
    timeout_seconds: int = Field(60, ge=1, le=300, description="Test timeout in seconds (default 60s for large models)")


class GlobalDefaultsUpdate(BaseModel):
    """Request model for updating global Ollama defaults."""
    request_timeout_sec: int = Field(30, ge=5, le=300, description="Default request timeout")
    max_retries: int = Field(3, ge=0, le=10, description="Default max retries")
    circuit_breaker_threshold: int = Field(5, ge=1, le=20, description="Circuit breaker threshold")


class GlobalDefaultsResponse(BaseModel):
    """Response model for global Ollama defaults."""
    request_timeout_sec: int = 30
    max_retries: int = 3
    circuit_breaker_threshold: int = 5


# Global repository instance
repo = OllamaServersRepository()


@router.get("/", response_model=List[OllamaServerResponse])
async def list_servers(
    enabled_only: bool = Query(False, description="Return only enabled servers")
):
    """List all Ollama servers."""
    try:
        if enabled_only:
            servers = repo.get_enabled()
        else:
            servers = repo.get_all()

        return [server.to_dict() for server in servers]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list servers: {str(e)}")


@router.post("/", response_model=OllamaServerResponse, status_code=201)
async def create_server(server: OllamaServerCreate):
    """Create a new Ollama server."""
    try:
        # Check if URL already exists
        existing = repo.get_by_url(server.url)
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Server with URL '{server.url}' already exists"
            )

        created_server = repo.create(server.name, server.url, server.notes)
        return created_server.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create server: {str(e)}")


@router.get("/defaults", response_model=GlobalDefaultsResponse)
async def get_global_defaults():
    """Get global Ollama server defaults."""
    try:
        # Get defaults from settings, with fallbacks
        timeout = SettingsRepository.get_int("ollama_request_timeout_sec", 30)
        retries = SettingsRepository.get_int("ollama_max_retries", 3)
        circuit_threshold = SettingsRepository.get_int("ollama_circuit_breaker_threshold", 5)

        return GlobalDefaultsResponse(
            request_timeout_sec=timeout,
            max_retries=retries,
            circuit_breaker_threshold=circuit_threshold
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get global defaults: {str(e)}")


@router.put("/defaults", response_model=GlobalDefaultsResponse)
async def update_global_defaults(defaults: GlobalDefaultsUpdate):
    """Update global Ollama server defaults."""
    try:
        # Store in settings
        SettingsRepository.set("ollama_request_timeout_sec", str(defaults.request_timeout_sec))
        SettingsRepository.set("ollama_max_retries", str(defaults.max_retries))
        SettingsRepository.set("ollama_circuit_breaker_threshold", str(defaults.circuit_breaker_threshold))

        return defaults
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update global defaults: {str(e)}")


@router.get("/health/overview")
async def get_servers_health_overview():
    """Get a health overview of all servers."""
    try:
        servers = repo.get_all()
        stats = repo.get_health_stats()

        server_health = []
        for server in servers:
            health_status = "unknown"
            if server.last_test_ok is not None:
                health_status = "healthy" if server.last_test_ok else "unhealthy"
            elif not server.enabled:
                health_status = "disabled"

            server_health.append({
                "id": server.id,
                "name": server.name,
                "url": server.url,
                "enabled": server.enabled,
                "status": health_status,
                "last_tested": server.last_tested_at.isoformat() if server.last_tested_at else None,
                "latency_ms": server.last_test_latency_ms
            })

        return {
            "servers": server_health,
            "summary": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get health overview: {str(e)}")


@router.post("/test-url", response_model=ServerTestResult)
async def test_server_url(request: ServerTestRequest):
    """Test connectivity to any Ollama server URL."""
    try:
        return await _test_server_connectivity(request.url, request.timeout_seconds)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to test server: {str(e)}")


@router.get("/{server_id}", response_model=OllamaServerResponse)
async def get_server(server_id: int):
    """Get a specific Ollama server by ID."""
    try:
        server = repo.get_by_id(server_id)
        if not server:
            raise HTTPException(status_code=404, detail="Server not found")
        return server.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get server: {str(e)}")


@router.put("/{server_id}", response_model=OllamaServerResponse)
async def update_server(server_id: int, server_update: OllamaServerUpdate):
    """Update an Ollama server."""
    try:
        # Check if server exists
        existing = repo.get_by_id(server_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Server not found")

        # Check if new URL conflicts with another server
        if server_update.url != existing.url:
            conflicting = repo.get_by_url(server_update.url)
            if conflicting and conflicting.id != server_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"Server with URL '{server_update.url}' already exists"
                )

        updated_server = repo.update(
            server_id,
            server_update.name,
            server_update.url,
            server_update.enabled,
            server_update.notes
        )

        if not updated_server:
            raise HTTPException(status_code=404, detail="Server not found")

        return updated_server.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update server: {str(e)}")


@router.delete("/{server_id}")
async def delete_server(server_id: int):
    """Delete an Ollama server."""
    try:
        # Check if server exists
        existing = repo.get_by_id(server_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Server not found")

        success = repo.delete(server_id)
        if not success:
            raise HTTPException(status_code=404, detail="Server not found")

        return {"message": f"Server '{existing.name}' deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete server: {str(e)}")


@router.post("/{server_id}/test", response_model=ServerTestResult)
async def test_server_connectivity(server_id: int):
    """Test connectivity to a specific Ollama server."""
    try:
        server = repo.get_by_id(server_id)
        if not server:
            raise HTTPException(status_code=404, detail="Server not found")

        return await _test_server_connectivity(server.url)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to test server: {str(e)}")


@router.post("/{server_id}/toggle")
async def toggle_server(server_id: int):
    """Toggle the enabled status of a server."""
    try:
        server = repo.get_by_id(server_id)
        if not server:
            raise HTTPException(status_code=404, detail="Server not found")

        updated_server = repo.toggle_enabled(server_id)
        if not updated_server:
            raise HTTPException(status_code=404, detail="Server not found")

        status = "enabled" if updated_server.enabled else "disabled"
        return {
            "message": f"Server '{updated_server.name}' {status} successfully",
            "enabled": updated_server.enabled
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to toggle server: {str(e)}")


async def _test_server_connectivity(url: str, timeout_seconds: int = 60) -> ServerTestResult:
    """Test connectivity to an Ollama server."""
    start_time = time.time()

    try:
        # Remove trailing slash if present
        base_url = url.rstrip('/')

        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            # Test basic connectivity with version endpoint
            version_url = f"{base_url}/api/version"
            response = await client.get(version_url)

            latency_ms = int((time.time() - start_time) * 1000)

            if response.status_code == 200:
                version_data = response.json()
                version = version_data.get('version', 'unknown')

                # Try to get available models
                try:
                    models_url = f"{base_url}/api/tags"
                    models_response = await client.get(models_url)

                    models_available = []
                    if models_response.status_code == 200:
                        models_data = models_response.json()
                        models_available = [model['name'] for model in models_data.get('models', [])]
                except Exception:
                    models_available = None

                # Update server test result in database
                server = repo.get_by_url(url)
                if server:
                    repo.update_test_result(server.id, latency_ms, True)

                return ServerTestResult(
                    success=True,
                    latency_ms=latency_ms,
                    version=version,
                    models_available=models_available
                )
            else:
                latency_ms = int((time.time() - start_time) * 1000)

                # Update server test result in database
                server = repo.get_by_url(url)
                if server:
                    repo.update_test_result(server.id, latency_ms, False)

                return ServerTestResult(
                    success=False,
                    latency_ms=latency_ms,
                    error=f"HTTP {response.status_code}: {response.text[:200]}"
                )

    except httpx.TimeoutException:
        latency_ms = int((time.time() - start_time) * 1000)
        error = f"Connection timeout after {timeout_seconds} seconds"

    except httpx.ConnectError:
        latency_ms = int((time.time() - start_time) * 1000)
        error = "Connection refused - server not reachable"

    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        error = f"Connection error: {str(e)}"

    # Update server test result in database
    server = repo.get_by_url(url)
    if server:
        repo.update_test_result(server.id, latency_ms if latency_ms > 0 else None, False)

    return ServerTestResult(
        success=False,
        latency_ms=latency_ms if latency_ms > 0 else None,
        error=error
    )
