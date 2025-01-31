# app/config.py
import os
from dotenv import load_dotenv
from datetime import timedelta

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
        
        # TinyMCE Configuration
        self.TINYMCE_API_KEY = os.environ.get('TINYMCE_API_KEY') or 'your-default-tiny-mce-key'

        self.FLASK_SECRET_KEY = os.environ.get('FLASK_SECRET_KEY') or 'your-default-flask-secret-key'
        
        # Logging Configuration
        self.LOGGING_LEVEL = os.environ.get('LOGGING_LEVEL', 'ERROR').upper()
        
        # Redis Configuration (if used)
        self.REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379')
        
        # Database Configuration
        self.SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'postgresql://localhost/beacon')
        self.SQLALCHEMY_TRACK_MODIFICATIONS = os.environ.get('SQLALCHEMY_TRACK_MODIFICATIONS', False)
        
        # Debug flag
        self.DEBUG = os.environ.get('FLASK_DEBUG', '0') == '1'
        
    def __getitem__(self, key):
        """Allow dictionary-style access to config values."""
        return getattr(self, key)
        
    def get(self, key, default=None):
        """Implement get method for compatibility with dict interface."""
        return getattr(self, key, default)