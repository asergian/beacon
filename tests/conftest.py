# conftest.py
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables first with error handling
try:
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if not os.path.exists(env_path):
        raise FileNotFoundError(f"Test .env file not found at: {env_path}")
    
    if not load_dotenv(env_path):
        raise RuntimeError(f"Failed to load environment variables from: {env_path}")
except Exception as e:
    print(f"Error loading test environment variables: {str(e)}", file=sys.stderr)
    sys.exit(1)

import pytest
from app import create_app
from app.config import Config

class TestConfig(Config):
    TESTING = True
    IMAP_SERVER = os.getenv('IMAP_SERVER', 'imap.gmail.com')  # Default to Gmail
    EMAIL = os.getenv('EMAIL', 'your-email@example.com')  # Default email
    IMAP_PASSWORD = os.getenv('IMAP_PASSWORD', 'your-email-password')  # Default password
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', 'your-default-openai-key')  # Use environment variable if available
    LOGGING_LEVEL = os.getenv('LOGGING_LEVEL', 'ERROR').upper()  # Default logging level

@pytest.fixture
def app():
    app = create_app(TestConfig)
    return app

@pytest.fixture
def client(app):
    with app.test_client() as client:
        return client

@pytest.fixture
def imap_config():
    return {
        'server': TestConfig.IMAP_SERVER,
        'email': TestConfig.EMAIL,
        'password': TestConfig.IMAP_PASSWORD
    }