from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional, List
import logging

from ..models import (
    ModelCatalogEntry,
    ModelCatalogCreateRequest,
    ModelCatalogUpdateRequest,
    ModelCatalogSearchRequest,
    ModelCatalogSearchResponse
)
from ..dependencies import db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/model-catalog", tags=["model-catalog"])

@router.post("/", response_model=ModelCatalogEntry)
async def create_model(model_data: ModelCatalogCreateRequest):
    """Create a new model catalog entry."""
    try:
        model_id = db.create_model_catalog_entry(
            alias=model_data.alias,
            model_string=model_data.model_string,
            provider_name=model_data.provider_name,
            model_type=model_data.model_type,
            description=model_data.description,
            max_new_tokens=model_data.max_new_tokens,
            temperature=model_data.temperature,
            num_ctx=model_data.num_ctx,
            trust_remote_code=model_data.trust_remote_code,
            tags=model_data.tags,
            is_favorite=model_data.is_favorite
        )
        
        # Return the created model
        created_model = db.get_model_catalog_entry(model_id)
        if not created_model:
            raise HTTPException(status_code=500, detail="Failed to retrieve created model")
        
        return ModelCatalogEntry(**created_model)
    
    except Exception as e:
        logger.error(f"Error creating model catalog entry: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create model: {str(e)}")

@router.get("/{model_id}", response_model=ModelCatalogEntry)
async def get_model(model_id: int):
    """Get a model catalog entry by ID."""
    try:
        model = db.get_model_catalog_entry(model_id)
        if not model:
            raise HTTPException(status_code=404, detail="Model not found")
        
        return ModelCatalogEntry(**model)
    
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
        existing_model = db.get_model_catalog_entry(model_id)
        if not existing_model:
            raise HTTPException(status_code=404, detail="Model not found")
        
        # Prepare update data (only include non-None values)
        update_data = {}
        for field, value in model_data.dict(exclude_unset=True).items():
            if value is not None:
                update_data[field] = value
        
        if not update_data:
            # No fields to update, return existing model
            return ModelCatalogEntry(**existing_model)
        
        # Update the model
        success = db.update_model_catalog_entry(model_id, **update_data)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update model")
        
        # Return updated model
        updated_model = db.get_model_catalog_entry(model_id)
        if not updated_model:
            raise HTTPException(status_code=500, detail="Failed to retrieve updated model")
        
        return ModelCatalogEntry(**updated_model)
    
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
        existing_model = db.get_model_catalog_entry(model_id)
        if not existing_model:
            raise HTTPException(status_code=404, detail="Model not found")
        
        # Delete the model
        success = db.delete_model_catalog_entry(model_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete model")
        
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
        result = db.search_model_catalog(
            search=search,
            provider=provider,
            model_type=model_type,
            tags=tags,
            is_favorite=is_favorite,
            page=page,
            page_size=page_size
        )
        
        # Convert models to Pydantic models
        models = [ModelCatalogEntry(**model) for model in result['models']]
        
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
        existing_model = db.get_model_catalog_entry(model_id)
        if not existing_model:
            raise HTTPException(status_code=404, detail="Model not found")
        
        # Toggle favorite status
        success = db.toggle_model_favorite(model_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to toggle favorite status")
        
        # Return updated model
        updated_model = db.get_model_catalog_entry(model_id)
        if not updated_model:
            raise HTTPException(status_code=500, detail="Failed to retrieve updated model")
        
        return ModelCatalogEntry(**updated_model)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling favorite for model {model_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to toggle favorite: {str(e)}") 