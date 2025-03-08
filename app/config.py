# app/config.py
"""
Application configuration module.

This module defines the configuration structure for the application,
handling environment variables, logging setup, and providing
a centralized configuration object for the application.
"""
import os
from typing import Any
from dotenv import load_dotenv

# Load environment variables immediately
load_dotenv()

class Config:
    """Base configuration class.
    
    This class holds all configuration settings for the application,
    primarily loaded from environment variables with sensible defaults.
    """
    
    def __init__(self) -> None:
        """Initialize configuration with environment variables.
        
        Loads configuration values from environment variables with defaults
        for development environments.
        """
        # Flask Configuration
        self.FLASK_SECRET_KEY = os.environ.get('FLASK_SECRET_KEY') or 'your-default-flask-secret-key'
        self.LOGGING_LEVEL = os.environ.get('LOGGING_LEVEL', 'ERROR').upper()
        self.DEBUG = os.environ.get('FLASK_DEBUG', '0') == '1'

        # IMAP Configuration
        self.IMAP_SERVER = os.environ.get('IMAP_SERVER') or 'imap.gmail.com'
        self.EMAIL = os.environ.get('EMAIL') or 'your-email@example.com'
        self.IMAP_PASSWORD = os.environ.get('IMAP_PASSWORD') or 'your-email-password'
        
        # SMTP Configuration; use the same email and password as IMAP by default
        self.SMTP_SERVER = os.environ.get('SMTP_SERVER') or 'smtp.gmail.com'
        self.SMTP_PORT = int(os.environ.get('SMTP_PORT') or 587)
        self.SMTP_USE_TLS = os.environ.get('SMTP_USE_TLS', '1') == '1'
        self.SMTP_EMAIL = os.environ.get('SMTP_EMAIL') or self.EMAIL
        self.SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD') or self.IMAP_PASSWORD
        self.SUPPORT_EMAIL = os.environ.get('SUPPORT_EMAIL') or 'support@shronas.com'
        
        # Load environment variables into config
        self.REDIS_TOKEN = os.environ.get('REDIS_TOKEN')
        self.REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379')

        # OpenAI Configuration
        self.OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY') or 'your-default-openai-key'

        # Database Configuration
        database_url = os.environ.get('DATABASE_URL', 'postgresql://localhost/beacon')
        # Handle Render's postgres:// URLs
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        self.SQLALCHEMY_DATABASE_URI = database_url
        self.SQLALCHEMY_TRACK_MODIFICATIONS = os.environ.get('SQLALCHEMY_TRACK_MODIFICATIONS', False)
        
    def __getitem__(self, key: str) -> Any:
        """Allow dictionary-style access to config values.
        
        Args:
            key: The configuration key to retrieve
            
        Returns:
            The value of the requested configuration item
            
        Raises:
            AttributeError: If the key doesn't exist
        """
        return getattr(self, key)
        
    def get(self, key: str, default: Any = None) -> Any:
        """Implement get method for compatibility with dict interface.
        
        Args:
            key: The configuration key to retrieve
            default: The default value to return if key doesn't exist
            
        Returns:
            The value of the requested configuration item or default
        """
        return getattr(self, key, default)