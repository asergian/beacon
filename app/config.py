# app/config.py
import os
from dotenv import load_dotenv

class Config:
    """Base configuration class."""
    
    def __init__(self):
        """Initialize configuration with environment variables."""
        # Load environment variables
        load_dotenv()
        
        # IMAP Configuration
        self.IMAP_SERVER = os.environ.get('IMAP_SERVER') or 'imap.gmail.com'
        self.EMAIL = os.environ.get('EMAIL') or 'your-email@example.com'
        self.IMAP_PASSWORD = os.environ.get('IMAP_PASSWORD') or 'your-email-password'
        
        # OpenAI Configuration
        self.OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY') or 'your-default-openai-key'
        
        # Logging Configuration
        self.LOGGING_LEVEL = os.environ.get('LOGGING_LEVEL', 'ERROR').upper()
        
        # Redis Configuration (if used)
        self.REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379')
        
        # Debug flag
        self.DEBUG = os.environ.get('FLASK_DEBUG', '0') == '1'
        
    def __getitem__(self, key):
        """Allow dictionary-style access to config values."""
        return getattr(self, key)
        
    def get(self, key, default=None):
        """Implement get method for compatibility with dict interface."""
        return getattr(self, key, default)