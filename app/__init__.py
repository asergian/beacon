"""Flask application factory with email processing setup.

This module provides the application factory pattern for creating a Flask application
with email processing capabilities. It handles the initialization of various components
including OpenAI client, email orchestration, and route registration.

Typical usage example:
    from app import create_app
    app = create_app()

Attributes:
    None

Functions:
    init_openai_client: Initializes the OpenAI client with API key configuration.
    create_app: Factory function that creates and configures the Flask application.
"""

from flask import Flask, g, current_app
import logging
from openai import AsyncOpenAI
from typing import Optional

from .config import Config
from .email.core.email_processor import EmailProcessor
from .email.core.email_connection import EmailConnection
from .email.core.email_parsing import EmailParser
from .email.models.analysis_settings import ProcessingConfig
from .email.analyzers.semantic_analyzer import SemanticAnalyzer
from .email.analyzers.content_analyzer import ContentAnalyzer
from .email.utils.priority_scoring import PriorityScorer

from .routes import init_routes
from .email.utils.nlp_setup import create_nlp_model

def init_openai_client(app):
    """Initializes the AsyncOpenAI client with configuration from the Flask app.

    Configures an AsyncOpenAI client instance with the API key from the application
    configuration and stores it in Flask's global context (g). The client is used
    for making asynchronous requests to OpenAI's API endpoints.

    Args:
        app: Flask application instance containing the configuration.

    Raises:
        ValueError: If the OpenAI API key is empty or invalid.
        Exception: For other unexpected initialization errors.

    Returns:
        None
    """
    
    # Here you can set any other client-specific configurations
    try:
        # Initialize AsyncOpenAI client with API key from config
        # Raises ValueError if API key is invalid/empty
        if not app.config['OPENAI_API_KEY']:
            raise ValueError("OpenAI API key cannot be empty")

        # Create a fallback logger in case app logger isn't available
        logger = getattr(current_app, 'logger', logging.getLogger(__name__))
        
        logger.info("OpenAI API key set")
        g.async_openai_client = AsyncOpenAI(api_key=app.config['OPENAI_API_KEY'])
    except ValueError as e:
        logger = getattr(current_app, 'logger', logging.getLogger(__name__))
        logger.error(f"Failed to initialize OpenAI client: {str(e)}")
        raise
    except Exception as e:
        logger = getattr(current_app, 'logger', logging.getLogger(__name__))
        logger.error(f"Unexpected error initializing OpenAI client: {str(e)}")
        raise

def create_app(config_class: Optional[object] = Config) -> Flask:
    """Create and configure Flask application."""
    
    # Create logger before Flask app
    logger = logging.getLogger(__name__)
    logger.info("Starting create_app...")
    
    # Create Flask app
    app = Flask(__name__)
    logger.info("Flask app instance created")
    
    # Initialize config
    config = config_class()  # Create instance of config class
    app.config.update({
        key: getattr(config, key)
        for key in dir(config)
        if not key.startswith('_')
    })
    logger.info("Config loaded and updated")

    # Log the actual configuration values being used
    logger.info("Current configuration values:")
    for key in ['IMAP_SERVER', 'EMAIL', 'IMAP_PASSWORD', 'OPENAI_API_KEY', 'LOGGING_LEVEL']:
        # Mask sensitive values in logs
        value = app.config.get(key, 'Not set')
        if key in ['IMAP_PASSWORD', 'OPENAI_API_KEY']:
            value = f"{value[:1]}..." if value else 'Not set'
        logger.info(f"{key}: {value}")

    # Verify all required configurations
    required_configs = {
        'OPENAI_API_KEY': None,
        'IMAP_SERVER': 'server',
        'EMAIL': 'email',
        'IMAP_PASSWORD': 'password',
        'LOGGING_LEVEL': None
    }
    
    # Validate all required configs and prepare email config
    email_config = {}
    for key in required_configs.keys():
        value = app.config.get(key)
        if not value or value in ['your-default-openai-key', 'your-email@example.com', 'your-email-password']:
            app.logger.error(f"Missing or default required configuration: {key}")
            raise ValueError(f"Missing or default required configuration: {key}")
        email_config[key.lower()] = value

    # Now, explicitly set the email_config for IMAP
    email_config = {
        'server': email_config['imap_server'],
        'email': email_config['email'],
        'password': email_config['imap_password']
    }

    # Initialize the OpenAI client when the request context is pushed
    @app.before_request
    def before_request():
        init_openai_client(app)
    
    # Initialize components
    try:
        nlp_model = create_nlp_model()
        
        text_analyzer = ContentAnalyzer(nlp_model)
        llm_analyzer = SemanticAnalyzer()
        priority_calculator = PriorityScorer(
            vip_senders=set(app.config.get('VIP_SENDERS', [])),
            config=ProcessingConfig()
        )

        # Unpack email_config when initializing EmailConnection using **
        email_client = EmailConnection(**email_config)
        parser = EmailParser()
        
        # Create and store email analyzer
        app.config['EMAIL_ANALYZER'] = EmailProcessor(
            email_client=email_client,
            text_analyzer=text_analyzer,
            llm_analyzer=llm_analyzer,
            priority_calculator=priority_calculator,
            parser=parser
        )
        app.logger.info("Email analyzer initialized successfully")
        
    except Exception as e:
        app.logger.error(f"Failed to initialize email components: {str(e)}")
        raise

    # Register routes
    try:
        init_routes(app)
        app.logger.info("Routes initialized successfully")
    except Exception as e:
        app.logger.error(f"Failed to initialize routes: {str(e)}")
        raise

    return app