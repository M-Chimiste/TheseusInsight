from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional

from ..dependencies import db
from ..models import (
    ModelCatalogEntry, ModelCatalogCreateRequest, ModelCatalogUpdateRequest,
    ModelCatalogSearchRequest, ModelCatalogResponse
)

router = APIRouter(prefix="/api/model-catalog", tags=["model-catalog"])

@router.post("/", response_model=ModelCatalogEntry)
async def create_model(request: ModelCatalogCreateRequest):
    """Create a new model in the catalog."""
    try:
        model_id = db.insert_model_catalog_entry(
            alias=request.alias,
            model_string=request.model_string,
            provider_name=request.provider_name,
            model_type=request.model_type,
            description=request.description,
            max_new_tokens=request.max_new_tokens,
            temperature=request.temperature,
            num_ctx=request.num_ctx,
            trust_remote_code=request.trust_remote_code,
            tags=request.tags,
            is_favorite=request.is_favorite
        )
        
        # Return the created model
        model = db.get_model_catalog_entry(model_id)
        if not model:
            raise HTTPException(status_code=500, detail="Failed to retrieve created model")
        
        return ModelCatalogEntry(**model)
        
    except Exception as e:
        if "UNIQUE constraint failed" in str(e):
            raise HTTPException(status_code=400, detail=f"Model alias '{request.alias}' already exists")
        raise HTTPException(status_code=500, detail=f"Error creating model: {str(e)}")

@router.get("/", response_model=ModelCatalogResponse)
async def search_models(
    provider_name: Optional[str] = Query(None, description="Filter by provider"),
    model_type: Optional[str] = Query(None, description="Filter by model type"),
    is_favorite: Optional[bool] = Query(None, description="Filter by favorite status"),
    search: Optional[str] = Query(None, description="Search in alias, model_string, and description"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page")
):
    """Search and filter models in the catalog."""
    try:
        result = db.get_all_model_catalog_entries(
            provider_name=provider_name,
            model_type=model_type,
            is_favorite=is_favorite,
            search=search,
            page=page,
            page_size=page_size
        )
        
        models = [ModelCatalogEntry(**model) for model in result["models"]]
        
        return ModelCatalogResponse(
            models=models,
            total_count=result["total_count"],
            total_pages=result["total_pages"],
            current_page=result["current_page"],
            page_size=result["page_size"]
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching models: {str(e)}")

@router.get("/{model_id}", response_model=ModelCatalogEntry)
async def get_model(model_id: int):
    """Get a specific model by ID."""
    try:
        model = db.get_model_catalog_entry(model_id)
        if not model:
            raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
        
        return ModelCatalogEntry(**model)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting model: {str(e)}")

@router.put("/{model_id}", response_model=ModelCatalogEntry)
async def update_model(model_id: int, request: ModelCatalogUpdateRequest):
    """Update an existing model in the catalog."""
    try:
        # Check if model exists
        existing_model = db.get_model_catalog_entry(model_id)
        if not existing_model:
            raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
        
        # Update the model
        success = db.update_model_catalog_entry(
            model_id=model_id,
            alias=request.alias,
            model_string=request.model_string,
            provider_name=request.provider_name,
            model_type=request.model_type,
            description=request.description,
            max_new_tokens=request.max_new_tokens,
            temperature=request.temperature,
            num_ctx=request.num_ctx,
            trust_remote_code=request.trust_remote_code,
            tags=request.tags,
            is_favorite=request.is_favorite
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update model")
        
        # Return the updated model
        updated_model = db.get_model_catalog_entry(model_id)
        return ModelCatalogEntry(**updated_model)
        
    except HTTPException:
        raise
    except Exception as e:
        if "UNIQUE constraint failed" in str(e):
            raise HTTPException(status_code=400, detail=f"Model alias already exists")
        raise HTTPException(status_code=500, detail=f"Error updating model: {str(e)}")

@router.delete("/{model_id}")
async def delete_model(model_id: int):
    """Delete a model from the catalog."""
    try:
        # Check if model exists
        existing_model = db.get_model_catalog_entry(model_id)
        if not existing_model:
            raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
        
        # Delete the model
        success = db.delete_model_catalog_entry(model_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete model")
        
        return {"message": f"Model {model_id} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting model: {str(e)}")

@router.get("/by-provider/{provider_name}", response_model=List[ModelCatalogEntry])
async def get_models_by_provider(
    provider_name: str,
    model_type: Optional[str] = Query(None, description="Filter by model type")
):
    """Get models filtered by provider and optionally by type."""
    try:
        models = db.get_models_by_provider_and_type(provider_name, model_type)
        return [ModelCatalogEntry(**model) for model in models]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting models by provider: {str(e)}")

@router.post("/{model_id}/favorite")
async def toggle_favorite(model_id: int):
    """Toggle the favorite status of a model."""
    try:
        # Check if model exists
        existing_model = db.get_model_catalog_entry(model_id)
        if not existing_model:
            raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
        
        # Toggle favorite status
        new_favorite_status = not existing_model["is_favorite"]
        success = db.update_model_catalog_entry(
            model_id=model_id,
            is_favorite=new_favorite_status
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to toggle favorite status")
        
        return {"message": f"Model {model_id} favorite status set to {new_favorite_status}"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error toggling favorite: {str(e)}") 