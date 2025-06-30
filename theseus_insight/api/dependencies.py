import os
from .tasks import task_manager

# PostgreSQL default instead of SQLite
DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/theseus")

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

def get_database_url() -> str:
    """Get validated database URL."""
    return DB_URL

def validate_database_connection() -> bool:
    """Validate PostgreSQL connection."""
    try:
        # Import here to avoid circular dependencies
        from ..storage.repositories import get_cursor
        with get_cursor() as cursor:
            cursor.execute("SELECT 1")
            return True
    except Exception:
        return False 