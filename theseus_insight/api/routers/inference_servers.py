"""Inference Server Management API endpoints (Ollama, LMStudio)."""

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional, Dict, Any
from datetime import datetime
import asyncio
import httpx
import time

from ...data_access.inference_servers import InferenceServersRepository, InferenceServer
from ...data_access.settings import SettingsRepository

router = APIRouter(prefix="/api/settings/inference-servers", tags=["inference-servers"])


# Request/Response Models
class InferenceServerCreate(BaseModel):
    """Request model for creating a new inference server."""
    name: str = Field(..., min_length=1, max_length=100, description="Server name")
    url: str = Field(..., description="Server URL/host (e.g., http://localhost:11434 or localhost:1234)")
    provider: str = Field("ollama", description="Provider type: ollama or lmstudio")
    enabled: bool = Field(True, description="Whether the server is enabled")
    config_json: Optional[Dict[str, Any]] = Field(None, description="Provider-specific configuration")
    model_name: Optional[str] = Field(None, description="Override model name for this server (e.g., phi4:latest)")
    model_configuration: Optional[Dict[str, Any]] = Field(None, description="Override model config for this server (e.g., temperature, max_new_tokens)", serialization_alias="model_config", validation_alias="model_config")
    notes: Optional[str] = Field(None, description="Optional notes about the server")

    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {
            "example": {
                "name": "Local Ollama",
                "url": "http://localhost:11434",
                "provider": "ollama",
                "enabled": True,
                "config_json": {},
                "model_name": "phi4:latest",
                "model_config": {"temperature": 0.2, "max_new_tokens": 1024},
                "notes": "Default local Ollama installation"
            }
        }
    }


class InferenceServerUpdate(BaseModel):
    """Request model for updating an inference server."""
    name: str = Field(..., min_length=1, max_length=100, description="Server name")
    url: str = Field(..., description="Server URL/host")
    provider: str = Field(..., description="Provider type: ollama or lmstudio")
    enabled: bool = Field(True, description="Whether the server is enabled")
    config_json: Optional[Dict[str, Any]] = Field(None, description="Provider-specific configuration")
    model_name: Optional[str] = Field(None, description="Override model name for this server (e.g., phi4:latest)")
    model_configuration: Optional[Dict[str, Any]] = Field(None, description="Override model config for this server (e.g., temperature, max_new_tokens)", serialization_alias="model_config", validation_alias="model_config")
    notes: Optional[str] = Field(None, description="Optional notes about the server")
    
    model_config = {"populate_by_name": True}


class InferenceServerResponse(BaseModel):
    """Response model for inference server data."""
    id: int
    name: str
    url: str
    provider: str
    enabled: bool
    config_json: Optional[Dict[str, Any]] = None
    model_name: Optional[str] = None
    model_configuration: Optional[Dict[str, Any]] = Field(None, serialization_alias="model_config", validation_alias="model_config")
    notes: Optional[str] = None
    last_tested_at: Optional[str] = None
    last_test_latency_ms: Optional[int] = None
    last_test_ok: Optional[bool] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    model_config = {"populate_by_name": True}


class ServerTestResult(BaseModel):
    """Response model for server connectivity test."""
    success: bool
    latency_ms: Optional[int] = None
    error: Optional[str] = None
    version: Optional[str] = None
    models_available: Optional[List[str]] = None
    provider: Optional[str] = None


class ServerTestRequest(BaseModel):
    """Request model for testing server connectivity."""
    url: str = Field(..., description="Server URL/host to test")
    provider: str = Field("ollama", description="Provider type: ollama or lmstudio")
    timeout_seconds: int = Field(60, ge=1, le=300, description="Test timeout in seconds")


class GlobalDefaults(BaseModel):
    """Global defaults for inference server operations."""
    request_timeout_sec: int = Field(30, ge=1, le=600, description="Request timeout in seconds")
    max_retries: int = Field(3, ge=0, le=10, description="Maximum number of retries")
    circuit_breaker_threshold: int = Field(5, ge=1, le=20, description="Circuit breaker failure threshold")


# Global repository instance
repo = InferenceServersRepository()


@router.get("/", response_model=List[InferenceServerResponse])
async def list_servers(
    enabled_only: bool = Query(False, description="Return only enabled servers"),
    provider: Optional[str] = Query(None, description="Filter by provider (ollama, lmstudio)")
):
    """List all inference servers, optionally filtered by provider."""
    try:
        if enabled_only:
            servers = repo.get_enabled(provider=provider)
        elif provider:
            servers = repo.get_by_provider(provider)
        else:
            servers = repo.get_all()

        return [server.to_dict() for server in servers]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list servers: {str(e)}")


@router.post("/", response_model=InferenceServerResponse, status_code=201)
async def create_server(server: InferenceServerCreate):
    """Create a new inference server."""
    try:
        # Validate provider
        if server.provider not in ['ollama', 'lmstudio']:
            raise HTTPException(
                status_code=400,
                detail="Provider must be 'ollama' or 'lmstudio'"
            )

        # Validate LMStudio config if provided
        if server.provider == 'lmstudio' and server.config_json:
            valid_keys = ['context_length', 'gpu_offload']
            for key in server.config_json.keys():
                if key not in valid_keys:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid config key '{key}' for LMStudio. Valid keys: {valid_keys}"
                    )

        # Check if URL already exists for this provider
        existing = repo.get_by_url(server.url, provider=server.provider)
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"{server.provider.title()} server with URL '{server.url}' already exists"
            )

        created_server = repo.create(
            name=server.name,
            url=server.url,
            provider=server.provider,
            enabled=server.enabled,
            config_json=server.config_json,
            model_name=server.model_name,
            model_config=server.model_configuration,
            notes=server.notes
        )
        return created_server.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create server: {str(e)}")


@router.get("/health/overview")
async def get_servers_health_overview(
    provider: Optional[str] = Query(None, description="Filter by provider")
):
    """Get a health overview of all servers, optionally filtered by provider."""
    try:
        if provider:
            servers = repo.get_by_provider(provider)
            stats = repo.get_server_health_stats(provider=provider)
        else:
            servers = repo.get_all()
            stats = repo.get_server_health_stats()

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
                "provider": server.provider,
                "enabled": server.enabled,
                "status": health_status,
                "last_tested": server.last_tested_at.isoformat() if server.last_tested_at else None,
                "latency_ms": server.last_test_latency_ms,
                "config_json": server.config_json,
                "model_name": server.model_name,
                "model_config": server.model_configuration
            })

        return {
            "servers": server_health,
            "summary": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get health overview: {str(e)}")


@router.post("/test-url", response_model=ServerTestResult)
async def test_server_url(request: ServerTestRequest):
    """Test connectivity to any inference server URL."""
    try:
        if request.provider == 'ollama':
            return await _test_ollama_connectivity(request.url, request.timeout_seconds)
        elif request.provider == 'lmstudio':
            return await _test_lmstudio_connectivity(request.url, request.timeout_seconds)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown provider: {request.provider}"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to test server: {str(e)}")


@router.get("/defaults", response_model=GlobalDefaults)
async def get_global_defaults():
    """Get global defaults for inference server operations."""
    try:
        # Retrieve settings with fallback to defaults
        request_timeout = SettingsRepository.get_int("inference_request_timeout_sec", 30)
        max_retries = SettingsRepository.get_int("inference_max_retries", 3)
        circuit_breaker = SettingsRepository.get_int("inference_circuit_breaker_threshold", 5)

        return GlobalDefaults(
            request_timeout_sec=request_timeout,
            max_retries=max_retries,
            circuit_breaker_threshold=circuit_breaker
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get global defaults: {str(e)}")


@router.put("/defaults", response_model=GlobalDefaults)
async def update_global_defaults(defaults: GlobalDefaults):
    """Update global defaults for inference server operations."""
    try:
        # Update settings in database
        SettingsRepository.set("inference_request_timeout_sec", str(defaults.request_timeout_sec))
        SettingsRepository.set("inference_max_retries", str(defaults.max_retries))
        SettingsRepository.set("inference_circuit_breaker_threshold", str(defaults.circuit_breaker_threshold))

        return defaults
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update global defaults: {str(e)}")


@router.get("/{server_id}", response_model=InferenceServerResponse)
async def get_server(server_id: int):
    """Get a specific inference server by ID."""
    try:
        server = repo.get_by_id(server_id)
        if not server:
            raise HTTPException(status_code=404, detail="Server not found")
        return server.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get server: {str(e)}")


@router.put("/{server_id}", response_model=InferenceServerResponse)
async def update_server(server_id: int, server_update: InferenceServerUpdate):
    """Update an inference server."""
    try:
        # Validate provider
        if server_update.provider not in ['ollama', 'lmstudio']:
            raise HTTPException(
                status_code=400,
                detail="Provider must be 'ollama' or 'lmstudio'"
            )

        # Check if server exists
        existing = repo.get_by_id(server_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Server not found")

        # Check if new URL conflicts with another server of same provider
        if server_update.url != existing.url or server_update.provider != existing.provider:
            conflicting = repo.get_by_url(server_update.url, provider=server_update.provider)
            if conflicting and conflicting.id != server_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"{server_update.provider.title()} server with URL '{server_update.url}' already exists"
                )

        updated_server = repo.update(
            server_id=server_id,
            name=server_update.name,
            url=server_update.url,
            provider=server_update.provider,
            enabled=server_update.enabled,
            config_json=server_update.config_json,
            model_name=server_update.model_name,
            model_config=server_update.model_configuration,
            notes=server_update.notes
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
    """Delete an inference server."""
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
    """Test connectivity to a specific inference server."""
    try:
        server = repo.get_by_id(server_id)
        if not server:
            raise HTTPException(status_code=404, detail="Server not found")

        if server.provider == 'ollama':
            result = await _test_ollama_connectivity(server.url)
        elif server.provider == 'lmstudio':
            result = await _test_lmstudio_connectivity(server.url, config_json=server.config_json)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown provider: {server.provider}"
            )

        # Update test results in database
        repo.update_test_result(
            server_id=server.id,
            latency_ms=result.latency_ms,
            success=result.success
        )

        return result
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


async def _test_ollama_connectivity(url: str, timeout_seconds: int = 60) -> ServerTestResult:
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

                return ServerTestResult(
                    success=True,
                    latency_ms=latency_ms,
                    version=version,
                    models_available=models_available,
                    provider='ollama'
                )
            else:
                latency_ms = int((time.time() - start_time) * 1000)

                return ServerTestResult(
                    success=False,
                    latency_ms=latency_ms,
                    error=f"HTTP {response.status_code}: {response.text[:200]}",
                    provider='ollama'
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

    return ServerTestResult(
        success=False,
        latency_ms=latency_ms if latency_ms > 0 else None,
        error=error,
        provider='ollama'
    )


async def _test_lmstudio_connectivity(
    url: str,
    timeout_seconds: int = 60,
    config_json: Optional[Dict[str, Any]] = None
) -> ServerTestResult:
    """Test connectivity to an LMStudio server."""
    start_time = time.time()

    try:
        # LMStudio uses OpenAI-compatible API
        # Format: host:port (no http://)
        if url.startswith('http://') or url.startswith('https://'):
            base_url = url.rstrip('/')
        else:
            base_url = f"http://{url}".rstrip('/')

        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            # Test with OpenAI-compatible models endpoint
            models_url = f"{base_url}/v1/models"
            response = await client.get(models_url)

            latency_ms = int((time.time() - start_time) * 1000)

            if response.status_code == 200:
                models_data = response.json()
                models_available = [model['id'] for model in models_data.get('data', [])]

                # LMStudio doesn't have a version endpoint, so we use connectivity as success
                return ServerTestResult(
                    success=True,
                    latency_ms=latency_ms,
                    version="LMStudio (OpenAI-compatible)",
                    models_available=models_available,
                    provider='lmstudio'
                )
            else:
                latency_ms = int((time.time() - start_time) * 1000)

                return ServerTestResult(
                    success=False,
                    latency_ms=latency_ms,
                    error=f"HTTP {response.status_code}: {response.text[:200]}",
                    provider='lmstudio'
                )

    except httpx.TimeoutException:
        latency_ms = int((time.time() - start_time) * 1000)
        error = f"Connection timeout after {timeout_seconds} seconds"

    except httpx.ConnectError:
        latency_ms = int((time.time() - start_time) * 1000)
        error = "Connection refused - LMStudio server not reachable"

    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        error = f"Connection error: {str(e)}"

    return ServerTestResult(
        success=False,
        latency_ms=latency_ms if latency_ms > 0 else None,
        error=error,
        provider='lmstudio'
    )


@router.post("/{server_id}/validate-model")
async def validate_server_model_config(
    server_id: int,
    model_name: Optional[str] = None,
    model_config: Optional[Dict[str, Any]] = None
):
    """
    Validate that a model configuration works with a specific server.
    Tests connectivity and model availability if model_name is provided.
    """
    try:
        # Get server
        server = repo.get_by_id(server_id)
        if not server:
            raise HTTPException(status_code=404, detail="Server not found")

        # Validate model_config structure if provided
        if model_config:
            valid_keys = ['temperature', 'max_new_tokens', 'num_ctx', 'context_length', 'gpu_offload']
            invalid_keys = [k for k in model_config.keys() if k not in valid_keys]
            if invalid_keys:
                return {
                    "valid": False,
                    "error": f"Invalid config keys: {', '.join(invalid_keys)}. Valid keys: {', '.join(valid_keys)}"
                }

            # Validate value types
            for key, value in model_config.items():
                if key in ['temperature'] and not isinstance(value, (int, float)):
                    return {"valid": False, "error": f"{key} must be a number"}
                if key in ['max_new_tokens', 'num_ctx', 'context_length'] and not isinstance(value, int):
                    return {"valid": False, "error": f"{key} must be an integer"}
                if key == 'gpu_offload' and not isinstance(value, (str, int, float)):
                    return {"valid": False, "error": "gpu_offload must be 'max', 'off', or a number between 0 and 1"}

        # If model_name provided, test if model is available on server
        if model_name:
            if server.provider == 'ollama':
                try:
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        response = await client.get(f"{server.url}/api/tags")
                        if response.status_code == 200:
                            models_data = response.json()
                            available_models = [m.get('name', '') for m in models_data.get('models', [])]

                            if model_name not in available_models:
                                return {
                                    "valid": False,
                                    "warning": f"Model '{model_name}' not found on server. Available models: {', '.join(available_models[:10])}"
                                }
                except Exception as e:
                    return {
                        "valid": False,
                        "error": f"Could not verify model availability: {str(e)}"
                    }
            elif server.provider == 'lmstudio':
                try:
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        response = await client.get(f"{server.url}/v1/models")
                        if response.status_code == 200:
                            models_data = response.json()
                            available_models = [m.get('id', '') for m in models_data.get('data', [])]

                            if model_name not in available_models:
                                return {
                                    "valid": False,
                                    "warning": f"Model '{model_name}' not found on server. Available models: {', '.join(available_models)}"
                                }
                except Exception as e:
                    return {
                        "valid": False,
                        "error": f"Could not verify model availability: {str(e)}"
                    }

        return {
            "valid": True,
            "message": "Configuration is valid"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")


# Backward compatibility: Keep old route prefix as alias
router_legacy = APIRouter(prefix="/api/settings/ollama-servers", tags=["ollama-servers"])

# Re-register all routes under legacy prefix
for route in router.routes:
    router_legacy.routes.append(route)
