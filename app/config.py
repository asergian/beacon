# app/config.py
import os

class Config:
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', 'your-default-openai-key')  # Use environment variable if available
    IMAP_SERVER = os.getenv('IMAP_SERVER', 'imap.gmail.com')  # Default to Gmail
    EMAIL = os.getenv('EMAIL', 'your-email@example.com')  # Default email
    IMAP_PASSWORD = os.getenv('IMAP_PASSWORD', 'your-email-password')  # Default password
    LOGGING_LEVEL = os.getenv('LOGGING_LEVEL', 'ERROR').upper()  # Default logging level
    #EMAIL_ORCHESTRATOR = os.getenv('EMAIL_ORCHESTRATOR', '')  # Default orchestrator
    #SERVER_NAME = os.getenv('SERVER_NAME', 'localhost')  # Default server name