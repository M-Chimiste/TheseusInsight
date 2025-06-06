from fastapi import APIRouter, HTTPException
from typing import List

from ..models import ModelProvider
from ..dependencies import db

router = APIRouter(prefix="/api/model-providers", tags=["model-providers"])

@router.get("", response_model=List[ModelProvider])
async def get_model_providers_api():
    """Get all available model providers."""
    try:
        providers_data = db.get_model_providers() # This returns a list of dicts like [{'id': 1, 'name': 'ollama'}]
        return [ModelProvider(id=p['id'], name=p['name']) for p in providers_data]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting model providers: {str(e)}") 