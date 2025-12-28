from fastapi import APIRouter, HTTPException
from typing import List

from ..models import ModelProvider
from ...data_access import ModelProviderRepository

router = APIRouter(prefix="/api/model-providers", tags=["model-providers"])

@router.get("", response_model=List[ModelProvider])
async def get_model_providers_api():
    """
    Retrieves all available model providers.

    This endpoint fetches the list of available model providers from the database.
    It returns a list of model provider objects with ID and name.
    """
    try:
        providers_data = ModelProviderRepository.all()
        return [ModelProvider(id=p['id'], name=p['name']) for p in providers_data]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting model providers: {str(e)}") 