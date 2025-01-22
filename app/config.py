# app/config.py
import os

class Config:
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', 'your-default-openai-key')  # Use environment variable if available
    IMAP_SERVER = os.getenv('IMAP_SERVER', 'imap.gmail.com')  # Default to Gmail
    EMAIL = os.getenv('EMAIL', 'your-email@example.com')  # Default email
    IMAP_PASSWORD = os.getenv('IMAP_PASSWORD', 'your-email-password')  # Default password
    LOGGING_LEVEL = os.getenv('LOGGING_LEVEL', 'INFO').upper()  # Default logging level