from fastapi import APIRouter, HTTPException
from typing import Dict, List
import json
import os

from ..models import (
    OrchestrationConfig, ArxivCategoriesConfig, ModelProvider,
    ResearchInterests, EmailRecipients, VisualizerSettings,
    ModelConfig, TTSModelConfig, ResearchAgentModelConfigApi
)
from ..dependencies import db, CREDENTIAL_KEYS
from ...utils.path_resolver import get_config_path, config_file_exists
from ... import theseus_insight as ti_module

router = APIRouter(prefix="/api/settings", tags=["settings"])

@router.get("/orchestration", response_model=OrchestrationConfig)
async def get_orchestration_config_api():
    """
    Retrieves the orchestration configuration, ensuring defaults for all fields including podcast and TTS.

    This endpoint fetches the orchestration configuration from the database.
    It returns the configuration with defaults for all fields including podcast and TTS.

    Returns:
        OrchestrationConfig: The orchestration configuration with defaults.

    Raises:
        HTTPException: If an error occurs while fetching the orchestration configuration.
    """
    try:
        db_config_json = db.get_setting("orchestration")
        loaded_config_data = {}

        if db_config_json:
            loaded_config_data = json.loads(db_config_json)
        else:
            # Fallback to orchestration.json if DB is empty
            config_path = get_config_path('orchestration.json')
            if config_file_exists('orchestration.json'):
                with open(config_path, 'r') as f:
                    loaded_config_data = json.load(f)
        
        # Define comprehensive defaults that Pydantic models expect
        default_embedding_model = ModelConfig(model_name='Alibaba-NLP/gte-modernbert-base', model_type='sentence-transformers', trust_remote_code=True)
        default_judge_model = ModelConfig(model_name='phi4-mini:3.8b-q8_0', model_type='ollama', max_new_tokens=512, temperature=0.1, num_ctx=4096)
        default_content_extraction_model = ModelConfig(model_name='gemma3:27b-it-qat', model_type='ollama', max_new_tokens=4096, temperature=0.1, num_ctx=131072)
        default_newsletter_sections_model = ModelConfig(model_name='gemma3:27b-it-qat', model_type='ollama', max_new_tokens=4096, temperature=0.1, num_ctx=131072)
        default_newsletter_intro_model = ModelConfig(model_name='gemini-2.0-flash', model_type='gemini', max_new_tokens=4096, temperature=0.1, num_ctx=131072)
        default_podcast_model = ModelConfig(model_name='gemini-2.0-flash', model_type='gemini', max_new_tokens=8192, temperature=0.1, num_ctx=131072)
        default_tts_model = TTSModelConfig(tts_provider='openai', tts_model_name='tts-1', speaker_1_voice='sage', speaker_1_speed=1.0, speaker_2_voice='ash', speaker_2_speed=1.0)

        # Create OrchestrationConfig by merging loaded data with defaults for missing top-level keys
        # Pydantic will handle missing sub-fields within ModelConfig/TTSModelConfig if they are optional or have defaults in their own definitions
        final_config = OrchestrationConfig(
            embedding_model=ModelConfig(**loaded_config_data.get('embedding_model', default_embedding_model.dict())),
            judge_model=ModelConfig(**loaded_config_data.get('judge_model', default_judge_model.dict())),
            content_extraction_model=ModelConfig(**loaded_config_data.get('content_extraction_model', default_content_extraction_model.dict())),
            newsletter_sections_model=ModelConfig(**loaded_config_data.get('newsletter_sections_model', default_newsletter_sections_model.dict())),
            newsletter_intro_model=ModelConfig(**loaded_config_data.get('newsletter_intro_model', default_newsletter_intro_model.dict())),
            podcast_model=ModelConfig(**loaded_config_data.get('podcast_model', default_podcast_model.dict())),
            tts_model=TTSModelConfig(**loaded_config_data.get('tts_model', default_tts_model.dict()))
        )
        return final_config

    except Exception as e:
        # Adding more context to the error for easier debugging
        error_detail = f"Error getting orchestration config: {str(e)}. DB JSON: {db_config_json if 'db_config_json' in locals() else 'Not fetched/Error'}. Loaded Data: {loaded_config_data if 'loaded_config_data' in locals() else 'Not loaded/Error'}."
        raise HTTPException(status_code=500, detail=error_detail)

@router.put("/orchestration")
async def update_orchestration_config_api(config: OrchestrationConfig):
    """
    Updates the orchestration configuration.

    This endpoint updates the orchestration configuration in the database.
    It also updates the orchestration.json file for legacy/fallback.

    Args:
        config (OrchestrationConfig): The orchestration configuration to update.

    Returns:
        dict: A dictionary containing the status and message of the update operation.

    Raises:
        HTTPException: If an error occurs while updating the orchestration configuration.
    """
    try:
        db.set_setting("orchestration", config.json())
        # Also update orchestration.json for legacy/fallback
        config_path = get_config_path('orchestration.json')
        with open(config_path, 'w') as f:
            json.dump(json.loads(config.json()), f, indent=2)
        return {"status": "success", "message": "Orchestration configuration updated successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating orchestration config: {str(e)}")

@router.get("/arxiv-categories", response_model=ArxivCategoriesConfig)
async def get_arxiv_categories_api():
    """
    Retrieves the ArXiv search categories.

    This endpoint fetches the ArXiv search categories from the database.
    It returns the categories with defaults if not found in the database.
    
    Returns:
        ArxivCategoriesConfig: The ArXiv search categories.

    Raises:
        HTTPException: If an error occurs while fetching the ArXiv categories.
    """
    try:
        settings_json = db.get_setting("arxiv_search_categories")
        if settings_json:
            return ArxivCategoriesConfig.parse_raw(settings_json)
        # Return default ArXivCategoriesConfig if not found in DB
        return ArxivCategoriesConfig(
            main_category="cs",
            filter_categories=["cs.ai", "cs.cl", "cs.lg", "cs.ir", "cs.ma", "cs.cv"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting ArXiv categories: {str(e)}")

@router.put("/arxiv-categories")
async def update_arxiv_categories_api(config: ArxivCategoriesConfig):
    """
    Updates the ArXiv search categories.

    This endpoint updates the ArXiv search categories in the database.
    It returns a success message if the categories are updated successfully.

    Args:
        config (ArxivCategoriesConfig): The ArXiv search categories to update.

    Returns:
        dict: A dictionary containing the status and message of the update operation.

    Raises:
        HTTPException: If an error occurs while updating the ArXiv categories.
    """
    try:
        db.set_setting("arxiv_search_categories", config.json())
        return {"status": "success", "message": "ArXiv categories updated successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating ArXiv categories: {str(e)}")

@router.get("/research-interests", response_model=ResearchInterests)
async def get_research_interests_api():
    """
    Retrieves the research interests.

    This endpoint fetches the research interests from the database.
    It returns the interests with defaults if not found in the database.

    Returns:
        ResearchInterests: The research interests.

    Raises:
        HTTPException: If an error occurs while fetching the research interests.
    """
    try:
        interests = db.get_setting("research_interests")
        if interests is not None: # Check if DB returned a value (could be empty string)
            return ResearchInterests(interests=interests)
        else:
            # Fallback to research_interests.txt
            config_path = get_config_path('research_interests.txt')
            if config_file_exists('research_interests.txt'):
                with open(config_path, 'r') as f:
                    interests_from_file = f.read().strip()
                return ResearchInterests(interests=interests_from_file)
            else:
                # Default to empty string if neither DB nor file exists
                return ResearchInterests(interests="")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting research interests: {str(e)}")

@router.put("/research-interests", response_model=ResearchInterests)
async def update_research_interests_api(data: ResearchInterests):
    """
    Updates the research interests.

    This endpoint updates the research interests in the database.
    It also updates the research_interests.txt file for legacy/fallback.

    Args:
        data (ResearchInterests): The research interests to update.

    Returns:
        ResearchInterests: The updated research interests.

    Raises:
        HTTPException: If an error occurs while updating the research interests.
    """
    try:
        # Save to DB
        db.set_setting("research_interests", data.interests)
        
        # Save to research_interests.txt
        config_path = get_config_path('research_interests.txt')
        try:
            with open(config_path, 'w') as f:
                f.write(data.interests)
        except IOError as e:
            # Log error but don't fail the request if DB save was successful
            print(f"Warning: Could not write to {config_path}: {e}")
            # Optionally, you could raise an HTTPException here if writing to file is critical
            # raise HTTPException(status_code=500, detail=f"Error saving research interests to file: {str(e)}")

        return data # Return the updated data
    except Exception as e:
        # Log the full error for debugging
        print(f"Full error updating research interests: {e}")
        raise HTTPException(status_code=500, detail=f"Error updating research interests: {str(e)}")

@router.get("/email-recipients", response_model=EmailRecipients)
async def get_email_recipients():
    """
    Retrieves the email recipients list.

    This endpoint fetches the email recipients list from the database.
    It returns the recipients list with defaults if not found in the database.

    Returns:
        EmailRecipients: The email recipients list.

    Raises:
        HTTPException: If an error occurs while fetching the email recipients list.
    """
    try:
        recipients_list = db.get_email_recipients()
        return EmailRecipients(recipients=recipients_list)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/email-recipients")
async def update_email_recipients(data: EmailRecipients):
    """
    Updates the email recipients list.

    This endpoint updates the email recipients list in the database.
    It returns a success message if the recipients are updated successfully.
    
    Args:
        data (EmailRecipients): The email recipients list to update.

    Returns:
        dict: A dictionary containing the status and message of the update operation.

    Raises:
        HTTPException: If an error occurs while updating the email recipients list.
    """
    try:
        # Basic email validation (optional here if Pydantic model handles it, or keep for defense-in-depth)
        for email in data.recipients:
            if "@" not in email or "." not in email: # Basic check
                raise HTTPException(status_code=400, detail=f"Invalid email address: {email}")
        db.set_email_recipients(data.recipients)
        return {"status": "success", "message": "Email recipients updated successfully."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/visualizer-settings", response_model=VisualizerSettings)
async def get_visualizer_settings():
    """
    Retrieves the visualizer settings.

    This endpoint fetches the visualizer settings from the database.
    It returns the settings with defaults if not found in the database.

    Returns:
        VisualizerSettings: The visualizer settings.

    Raises:
        HTTPException: If an error occurs while fetching the visualizer settings.
    """
    try:
        settings = db.get_visualizer_settings()
        if not settings:
            # Return default settings from the model
            return VisualizerSettings().dict()
        return settings
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/send-test-email")
async def send_test_email():
    """
    Sends a test email to the email address in GMAIL_SENDER_ADDRESS environment variable.

    This endpoint sends a test email to the email address in GMAIL_SENDER_ADDRESS environment variable.
    It returns a success message if the email is sent successfully.

    Returns:
        dict: A dictionary containing the status and message of the test email operation.

    Raises:
        HTTPException: If an error occurs while sending the test email.
    """
    try:
        from ...communication import GmailCommunication
        
        # Initialize email client
        gmail_sender = os.getenv("GMAIL_SENDER_ADDRESS")
        gmail_password = os.getenv("GMAIL_APP_PASSWORD")
        
        if not gmail_sender or not gmail_password:
            raise HTTPException(
                status_code=500,
                detail="Email credentials not configured"
            )
            
        comm = GmailCommunication(
            sender_address=gmail_sender,
            app_password=gmail_password,
            receiver_address=gmail_sender
        )
        
        # Send test email
        test_content = """
        This is a test email from Theseus Insight.
        
        If you're receiving this, your email configuration is working correctly.
        
        Best regards,
        Theseus Insight Team
        """
        
        from datetime import datetime
        comm.compose_message(
            content=test_content,
            start_date=datetime.now().date(),
            end_date=datetime.now().date(),
            subject="Theseus Insight - Test Email"
        )
        comm.send_email()

        return {"status": "success", "message": "Test email sent successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/credentials")
async def get_credentials():
    """
    Retrieves the API credentials from the database or environment.

    This endpoint fetches the API credentials from the database or environment.
    It returns the credentials as a dictionary.

    Returns:
        dict: A dictionary containing the API credentials.

    Raises:
        HTTPException: If an error occurs while fetching the API credentials.
    """
    try:
        creds = {}
        for key in CREDENTIAL_KEYS:
            if key == "OLLAMA_URL":
                val = db.get_setting(key) or os.getenv(key, "")
            else:
                val = db.get_secret_setting(key) or os.getenv(key, "")
            creds[key] = val
        return creds
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/credentials")
async def update_credentials(data: Dict[str, str]):
    """
    Updates the API credentials in the database and environment.

    This endpoint updates the API credentials in the database and environment.
    It returns a success message if the credentials are updated successfully.

    Args:
        data (Dict[str, str]): A dictionary containing the API credentials to update.

    Returns:
        dict: A dictionary containing the status and message of the update operation.

    Raises:
        HTTPException: If an error occurs while updating the API credentials.
    """
    try:
        for key, value in data.items():
            if key not in CREDENTIAL_KEYS:
                continue
            if key == "OLLAMA_URL":
                db.set_setting(key, value)
            else:
                db.set_secret_setting(key, value)
            os.environ[key] = value
            if hasattr(ti_module, key):
                setattr(ti_module, key, value)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/research-agent-model-config", response_model=ResearchAgentModelConfigApi)
async def get_research_agent_model_config():
    """Get research agent model configuration."""
    try:
        # Import locally to avoid circular imports
        from ...agentic_research.model_router import load_research_agent_model_config
        config = load_research_agent_model_config(db)
        
        return ResearchAgentModelConfigApi(
            boss_model=config.boss_model,
            worker_models=config.worker_models,
            default_worker=config.default_worker,
            max_retries=config.max_retries,
            timeout_seconds=config.timeout_seconds
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting research agent model config: {str(e)}")

@router.put("/research-agent-model-config")
async def update_research_agent_model_config(config: ResearchAgentModelConfigApi):
    """Update research agent model configuration."""
    try:
        # Import locally to avoid circular imports
        from ...agentic_research.model_router import ResearchAgentModelConfig, save_research_agent_model_config
        
        # Convert API model to internal config
        internal_config = ResearchAgentModelConfig({
            "boss_model": config.boss_model.dict(),
            "worker_models": {k: v.dict() for k, v in config.worker_models.items()},
            "default_worker": config.default_worker,
            "max_retries": config.max_retries,
            "timeout_seconds": config.timeout_seconds
        })
        
        # Save to database
        save_research_agent_model_config(db, internal_config)
        
        return {"status": "success", "message": "Research agent model configuration updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating research agent model config: {str(e)}") 