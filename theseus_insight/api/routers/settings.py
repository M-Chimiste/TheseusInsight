from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field, ValidationError, RootModel
from typing import List, Optional, Dict, Any
from theseus_insight.data_model.data_handling import PaperDatabase
import os
import json
from theseus_insight.communication.communication import GmailCommunication
from fastapi import status

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


# --- Settings Endpoints ---
@router.get("/settings", response_model=Dict[str, str])
def get_all_settings():
    db = get_db()
    return db.get_all_settings()

@router.get("/settings/{key}")
def get_setting(key: str):
    db = get_db()
    value = db.get_setting(key)
    if value is None:
        raise HTTPException(status_code=404, detail="Setting not found")
    return {"key": key, "value": value}

@router.put("/settings/{key}")
def set_setting(key: str, value: str):
    db = get_db()
    db.set_setting(key, value)
    return {"result": "updated"}

@router.delete("/settings/{key}")
def delete_setting(key: str):
    db = get_db()
    db.delete_setting(key)
    return {"result": "deleted"}

# --- Model Providers Endpoints ---
@router.get("/providers", response_model=List[Provider])
def get_providers():
    db = get_db()
    return db.get_model_providers()

@router.post("/providers", response_model=Provider)
def add_provider(provider: Provider):
    db = get_db()
    db.add_model_provider(provider.name)
    # Return the new provider (fetch by name)
    providers = db.get_model_providers()
    for p in providers:
        if p["name"] == provider.name:
            return p
    raise HTTPException(status_code=500, detail="Provider not created")

@router.delete("/providers/{provider_id}")
def delete_provider(provider_id: int):
    db = get_db()
    db.delete_model_provider(provider_id)
    return {"result": "deleted"}

# --- Models Endpoints ---
@router.get("/models", response_model=List[ModelConfig])
def get_models(provider_id: Optional[int] = None):
    db = get_db()
    return db.get_models(provider_id)

@router.post("/models", response_model=ModelConfig)
def add_model(model: ModelConfig):
    db = get_db()
    # Validate provider exists
    providers = db.get_model_providers()
    if not any(p["id"] == model.provider_id for p in providers):
        raise HTTPException(status_code=400, detail="Provider does not exist")
    db.add_model(model.provider_id, model.name, json.dumps(model.config_json) if model.config_json else None)
    # Return the new model (fetch by name and provider_id)
    models = db.get_models(model.provider_id)
    for m in models:
        if m["name"] == model.name:
            return m
    raise HTTPException(status_code=500, detail="Model not created")

@router.delete("/models/{model_id}")
def delete_model(model_id: int):
    db = get_db()
    db.delete_model(model_id)
    return {"result": "deleted"}

@router.get("/settings/email-recipients", response_model=EmailRecipients)
def get_email_recipients():
    db = get_db()
    return {"recipients": db.get_email_recipients()}

@router.put("/settings/email-recipients", response_model=EmailRecipients)
def set_email_recipients(payload: EmailRecipients):
    db = get_db()
    db.set_email_recipients(payload.recipients)
    return payload

@router.get("/settings/visualizer-settings", response_model=VisualizerSettings)
def get_visualizer_settings():
    db = get_db()
    return {"settings": db.get_visualizer_settings()}

@router.put("/settings/visualizer-settings", response_model=VisualizerSettings)
def set_visualizer_settings(payload: VisualizerSettings):
    db = get_db()
    db.set_visualizer_settings(payload.settings)
    return payload

@router.post("/settings/send-test-email")
def send_test_email():
    db = get_db()
    recipients = db.get_email_recipients()
    if not recipients:
        return {"success": False, "message": "No recipients configured."}
    try:
        comm = GmailCommunication(db_path=db.db_path)
        comm.compose_message(
            content="This is a test email from Theseus Insight.",
            start_date="2024-01-01",
            end_date="2024-01-01"
        )
        comm.send_email()
        return {"success": True, "message": f"Test email sent to: {', '.join(recipients)}"}
    except Exception as e:
        return {"success": False, "message": str(e)}

@router.get("/settings/orchestration")
def get_orchestration():
    db = get_db()
    value = db.get_setting("orchestration")
    if value is None:
        raise HTTPException(status_code=404, detail="Setting not found")
    try:
        return json.loads(value)
    except Exception:
        return value

@router.put("/settings/orchestration")
def set_orchestration(config: Dict[str, Any]):
    db = get_db()
    db.set_setting("orchestration", config)
    return config

@router.get("/settings/research-interests")
def get_research_interests():
    db = get_db()
    value = db.get_setting("research-interests")
    if value is None:
        return {"interests": ""}
    return {"interests": value}

@router.put("/settings/research-interests")
def set_research_interests(payload):
    print(payload)
    db = get_db()
    value = json.dumps(payload["interests"])
    db.set_setting("research-interests", value)
    return payload