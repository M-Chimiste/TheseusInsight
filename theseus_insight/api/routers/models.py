from fastapi import APIRouter, HTTPException, Body, status, Response
from pydantic import BaseModel, Field, ValidationError, RootModel
from typing import List, Optional, Dict, Any
from theseus_insight.data_model.data_handling import PaperDatabase
import os
import json
from theseus_insight.communication.communication import GmailCommunication

router = APIRouter()

def get_db():
    db_path = os.environ.get("THESEUS_DB_PATH", "data/papers.db")
    return PaperDatabase(db_path)

# --- Pydantic Schemas

class Provider(BaseModel):
    id: int
    name: str

class ModelConfig(BaseModel):
    id: Optional[int]
    provider_id: int
    name: str
    config_json: Optional[Dict[str, Any]] = None

# --- Model Providers Endpoints ---
@router.get("/providers", response_model=List[Provider])
def get_providers():
    db = get_db()
    return db.get_model_providers()

@router.post("/providers", response_model=Provider, status_code=status.HTTP_201_CREATED)
def add_provider(provider: Provider):
    db = get_db()
    db.add_model_provider(provider.id, provider.name)
    providers = db.get_model_providers()
    for p in providers:
        if p["name"] == provider.name:
            return p
    raise HTTPException(status_code=500, detail="Provider not created")

@router.delete("/providers/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_provider(provider_id: int):
    db = get_db()
    db.delete_model_provider(provider_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

# --- Models Endpoints ---
@router.get("/models", response_model=List[ModelConfig])
def get_models(provider_id: Optional[int] = None):
    db = get_db()
    return db.get_models(provider_id)

@router.post("/models", response_model=ModelConfig, status_code=status.HTTP_201_CREATED)
def add_model(model: ModelConfig):
    db = get_db()
    providers = db.get_model_providers()
    if not any(p["id"] == model.provider_id for p in providers):
        raise HTTPException(status_code=400, detail="Provider does not exist")
    db.add_model(model.provider_id, model.name, json.dumps(model.config_json) if model.config_json else None)
    models = db.get_models(model.provider_id)
    for m in models:
        if m["name"] == model.name:
            return m
    raise HTTPException(status_code=500, detail="Model not created")

@router.delete("/models/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_model(model_id: int):
    db = get_db()
    db.delete_model(model_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)