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

class EmailRecipients(BaseModel):
    recipients: List[str] = Field(default_factory=list)

class VisualizerSettings(BaseModel):
    settings: Dict[str, Any] = Field(default_factory=dict)

class ResearchInterests(BaseModel):
    interests: str

# --- Settings Endpoints ---
@router.get("/settings", response_model=Dict[str, str])
def get_all_settings():
    db = get_db()
    return db.get_all_settings()


# --- Orchestration ---
@router.get("/orchestration")
def get_orchestration():
    db = get_db()
    value = db.get_setting("orchestration")
    if value is None:
        raise HTTPException(status_code=404, detail="Setting not found")
    try:
        return json.loads(value)
    except Exception:
        return value

@router.put("/orchestration", status_code=status.HTTP_204_NO_CONTENT)
def set_orchestration(payload: dict = Body(...)):
    db = get_db()
    db.set_setting("orchestration", json.dumps(payload))
    return Response(status_code=status.HTTP_204_NO_CONTENT)

# --- Research Interests ---
@router.get("/research-interests")
def get_research_interests():
    db = get_db()
    value = db.get_setting("research-interests")
    if value is None:
        return {"interests": ""}
    return {"interests": value}

@router.put("/research-interests", status_code=status.HTTP_204_NO_CONTENT)
def set_research_interests(payload: dict = Body(...)):
    print(payload)
    db = get_db()
    db.set_setting("research-interests", payload["interests"])
    return Response(status_code=status.HTTP_204_NO_CONTENT)

# --- Visualizer Settings ---
@router.get("/visualizer-settings", response_model=VisualizerSettings)
def get_visualizer_settings():
    db = get_db()
    return {"settings": db.get_visualizer_settings()}

@router.put("/visualizer-settings", status_code=status.HTTP_204_NO_CONTENT)
def set_visualizer_settings(payload: dict = Body(...)):
    db = get_db()
    db.set_setting("visualizer_settings", json.dumps(payload))
    return Response(status_code=status.HTTP_204_NO_CONTENT)

# --- Email Recipients ---
@router.get("/email-recipients", response_model=EmailRecipients)
def get_email_recipients():
    db = get_db()
    return {"recipients": db.get_email_recipients()}

@router.put("/email-recipients", status_code=status.HTTP_204_NO_CONTENT)
def set_email_recipients(payload: dict = Body(...)):
    db = get_db()
    db.set_setting("email_recipients", json.dumps(payload["recipients"]))
    return Response(status_code=status.HTTP_204_NO_CONTENT)

# --- Send Test Email ---
@router.post("/send-test-email", status_code=status.HTTP_204_NO_CONTENT)
def send_test_email():
    db = get_db()
    recipients = db.get_email_recipients()
    if not recipients:
        raise HTTPException(status_code=400, detail="No recipients configured.")
    try:
        comm = GmailCommunication(db_path=db.db_path)
        comm.compose_message(
            content="This is a test email from Theseus Insight.",
            start_date="2024-01-01",
            end_date="2024-01-01"
        )
        comm.send_email()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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