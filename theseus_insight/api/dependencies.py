"""Shared API constants.

This module used to carry dead database helpers (get_database_url,
validate_database_connection) whose import target no longer existed;
they were removed in the refactor cleanup. Only CREDENTIAL_KEYS is
consumed (main.py, routers/settings.py).
"""

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
