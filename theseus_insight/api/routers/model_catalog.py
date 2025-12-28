from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional, List
import logging
from datetime import datetime

from ..models import (
    ModelCatalogEntry,
    ModelCatalogCreateRequest,
    ModelCatalogUpdateRequest,
    ModelCatalogSearchRequest,
    ModelCatalogSearchResponse
)
from ...data_access import ModelCatalogRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/model-catalog", tags=["model-catalog"])


def _convert_model_timestamps(model_dict: dict) -> dict:
    """Convert PostgreSQL datetime objects to ISO strings for Pydantic models."""
    model_copy = model_dict.copy()
    
    # Handle datetime fields - PostgreSQL returns datetime objects directly
    for field in ['created_at', 'updated_at']:
        if model_copy.get(field):
            if isinstance(model_copy[field], datetime):
                model_copy[field] = model_copy[field].isoformat()
    
    return model_copy

@router.post("/", response_model=ModelCatalogEntry)
async def create_model(model_data: ModelCatalogCreateRequest):
    """Create a new model catalog entry."""
    try:
        model_id = ModelCatalogRepository.insert(model_data.dict())
        
        # Return the created model
        created_model = ModelCatalogRepository.get(model_id)
        if not created_model:
            raise HTTPException(status_code=500, detail="Failed to retrieve created model")
        
        return ModelCatalogEntry(**_convert_model_timestamps(created_model))
    
    except Exception as e:
        logger.error(f"Error creating model catalog entry: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create model: {str(e)}")

@router.get("/{model_id}", response_model=ModelCatalogEntry)
async def get_model(model_id: int):
    """Get a model catalog entry by ID."""
    try:
        model = ModelCatalogRepository.get(model_id)
        if not model:
            raise HTTPException(status_code=404, detail="Model not found")
        
        return ModelCatalogEntry(**_convert_model_timestamps(model))
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving model {model_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve model: {str(e)}")

@router.put("/{model_id}", response_model=ModelCatalogEntry)
async def update_model(model_id: int, model_data: ModelCatalogUpdateRequest):
    """Update a model catalog entry."""
    try:
        # Check if model exists
        existing_model = ModelCatalogRepository.get(model_id)
        if not existing_model:
            raise HTTPException(status_code=404, detail="Model not found")
        
        # Prepare update data (only include non-None values)
        update_data = {}
        for field, value in model_data.dict(exclude_unset=True).items():
            if value is not None:
                update_data[field] = value
        
        if not update_data:
            # No fields to update, return existing model
            return ModelCatalogEntry(**_convert_model_timestamps(existing_model))
        
        # Update the model
        ModelCatalogRepository.update(model_id, update_data)
        
        # Return updated model
        updated_model = ModelCatalogRepository.get(model_id)
        if not updated_model:
            raise HTTPException(status_code=500, detail="Failed to retrieve updated model")
        
        return ModelCatalogEntry(**_convert_model_timestamps(updated_model))
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating model {model_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update model: {str(e)}")

@router.delete("/{model_id}")
async def delete_model(model_id: int):
    """Delete a model catalog entry."""
    try:
        # Check if model exists
        existing_model = ModelCatalogRepository.get(model_id)
        if not existing_model:
            raise HTTPException(status_code=404, detail="Model not found")
        
        # Delete the model
        ModelCatalogRepository.delete(model_id)
        
        return {"message": "Model deleted successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting model {model_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete model: {str(e)}")

@router.get("/", response_model=ModelCatalogSearchResponse)
async def search_models(
    search: Optional[str] = Query(None, description="Search query"),
    provider: Optional[str] = Query(None, description="Filter by provider"),
    model_type: Optional[str] = Query(None, description="Filter by model type"),
    tags: Optional[List[str]] = Query(None, description="Filter by tags"),
    is_favorite: Optional[bool] = Query(None, description="Filter by favorite status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Page size")
):
    """Search model catalog with filters and pagination."""
    try:
        result = ModelCatalogRepository.search(
            search=search,
            provider=provider,
            model_type=model_type,
            tags=tags,
            is_favorite=is_favorite,
            page=page,
            page_size=page_size
        )
        
        # Convert models to Pydantic models
        models = [ModelCatalogEntry(**_convert_model_timestamps(model)) for model in result['models']]
        
        return ModelCatalogSearchResponse(
            models=models,
            total_count=result['total_count'],
            total_pages=result['total_pages'],
            current_page=result['current_page'],
            page_size=result['page_size']
        )
    
    except Exception as e:
        logger.error(f"Error searching model catalog: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to search models: {str(e)}")

@router.post("/{model_id}/toggle-favorite", response_model=ModelCatalogEntry)
async def toggle_favorite(model_id: int):
    """Toggle the favorite status of a model."""
    try:
        # Check if model exists
        existing_model = ModelCatalogRepository.get(model_id)
        if not existing_model:
            raise HTTPException(status_code=404, detail="Model not found")
        
        # Toggle favorite status
        ModelCatalogRepository.toggle_favorite(model_id)
        
        # Return updated model
        updated_model = ModelCatalogRepository.get(model_id)
        if not updated_model:
            raise HTTPException(status_code=500, detail="Failed to retrieve updated model")
        
        return ModelCatalogEntry(**_convert_model_timestamps(updated_model))
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling favorite for model {model_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to toggle favorite: {str(e)}") 