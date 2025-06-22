import os
from .tasks import task_manager
from ..data_model.data_handling import PaperDatabase

# Initialize database
DB_URL = os.getenv("DATABASE_URL", "data/theseus.db")
db = PaperDatabase(DB_URL)

# List of credential environment variable names
CREDENTIAL_KEYS = [
    "GOOGLE_API_KEY",
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GMAIL_SENDER_ADDRESS",
    "GMAIL_APP_PASSWORD",
    "OLLAMA_URL",
    "CLIENT_ID",
    "PROJECT_ID",
    "CLIENT_SECRET",
    "CUSTOM_OAI_BASE_URL",
    "CUSTOM_OAI_API_KEY",
    "KAGGLE_USERNAME",
    "KAGGLE_KEY",
] 