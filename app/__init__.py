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
from logging.handlers import RotatingFileHandler
from openai import AsyncOpenAI
from typing import Optional
import os
from datetime import timedelta
import asyncio

from .config import Config
from .models import db
from flask_migrate import Migrate
from .email.core.email_processor import EmailProcessor
from .email.core.email_connection import EmailConnection
from .email.core.email_parsing import EmailParser
from .email.models.analysis_settings import ProcessingConfig
from .email.analyzers.semantic_analyzer import SemanticAnalyzer
from .email.analyzers.content_analyzer import ContentAnalyzer
from .email.utils.priority_scoring import PriorityScorer
from .email.pipeline.pipeline import create_pipeline
from .email.core.gmail_client import GmailClient
from .email.storage.cache import RedisEmailCache

from .routes import init_routes
from .email.utils.nlp_setup import create_nlp_model
from .utils.async_utils import async_manager

def init_logging(app: Flask) -> None:
    """Initialize logging configuration for the application.
    
    Args:
        app: Flask application instance
    """
    # Ensure the logs directory exists
    if not os.path.exists('logs'):
        os.makedirs('logs')
        
    # Set up file handler
    file_handler = RotatingFileHandler(
        'logs/beacon.log',
        maxBytes=10240000,  # 10MB
        backupCount=10
    )
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    
    # Set logging level from config
    file_handler.setLevel(app.config.get('LOGGING_LEVEL', logging.INFO))
    app.logger.addHandler(file_handler)
    
    # Also log to console in development
    if app.debug:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        app.logger.addHandler(console_handler)
    
    app.logger.setLevel(app.config.get('LOGGING_LEVEL', logging.INFO))
    app.logger.info('Beacon startup')

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
        
        # Test the OpenAI client to ensure it's working
        test_client = AsyncOpenAI(api_key=app.config['OPENAI_API_KEY'])
        
        # Create a function to get or create the OpenAI client
        def get_openai_client():
            if 'async_openai_client' not in g:
                g.async_openai_client = AsyncOpenAI(
                    api_key=app.config['OPENAI_API_KEY'],
                    timeout=60.0  # Set a reasonable timeout
                )
            return g.async_openai_client
        
        # Register a function to clean up the client when the request ends
        def close_openai_client(e=None):
            client = g.pop('async_openai_client', None)
            if client is not None:
                # Add any cleanup if needed
                pass
        
        # Register the teardown function
        app.teardown_appcontext(close_openai_client)
        
        # Store the getter function in the app
        app.get_openai_client = get_openai_client
        
        logger.info("OpenAI client initialized successfully")
        
    except ValueError as e:
        logger = getattr(current_app, 'logger', logging.getLogger(__name__))
        logger.error(f"Failed to initialize OpenAI client: {str(e)}")
        raise
    except Exception as e:
        logger = getattr(current_app, 'logger', logging.getLogger(__name__))
        logger.error(f"Unexpected error initializing OpenAI client: {str(e)}")
        raise

def create_app(config_class: Optional[object] = Config) -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)
    
    # Load configuration
    if isinstance(config_class, type):
        app.config.from_object(config_class())
    else:
        app.config.from_object(config_class)
    
    # Set up session configuration
    app.secret_key = app.config.get('FLASK_SECRET_KEY') or os.urandom(24)
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
    app.config['SESSION_PERMANENT'] = True
    
    # Initialize extensions
    db.init_app(app)
    migrate = Migrate(app, db)
    
    # Ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass
        
    # Initialize logging
    init_logging(app)
    
    # Initialize OpenAI client
    with app.app_context():
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

        # Create Gmail client
        gmail_client = GmailClient()
        parser = EmailParser()
        
        # Create and store email processor
        processor = EmailProcessor(
            email_client=gmail_client,
            text_analyzer=text_analyzer,
            llm_analyzer=llm_analyzer,
            priority_calculator=priority_calculator,
            parser=parser
        )
        
        # Initialize Redis connection pool
        from redis.asyncio import ConnectionPool, Redis
        redis_url = app.config.get('REDIS_URL', 'redis://localhost:6379')
        
        # Create a connection pool with proper configuration
        pool = ConnectionPool.from_url(
            redis_url,
            max_connections=10,  # Adjust based on your needs
            decode_responses=True  # Automatically decode responses to strings
        )
        
        # Store the pool in the app config
        app.config['REDIS_POOL'] = pool
        
        # Create Redis client with connection pool and async context
        def get_redis_client():
            if 'redis_client' not in g:
                loop = async_manager.ensure_loop()
                g.redis_client = Redis(
                    connection_pool=app.config['REDIS_POOL'],
                    decode_responses=True
                )
            return g.redis_client
        
        # Simple cleanup that doesn't try to close connections
        def close_redis_client(e=None):
            if 'redis_client' in g:
                del g.redis_client
        
        app.teardown_appcontext(close_redis_client)
        app.get_redis_client = get_redis_client
        
        # Create cache with function to get Redis client
        cache = RedisEmailCache(get_redis_client)
        
        # Create and store pipeline
        app.pipeline = create_pipeline(
            connection=gmail_client,
            parser=parser,
            processor=processor,
            cache=cache
        )
        
        app.logger.info("Email components initialized successfully")
        
    except Exception as e:
        app.logger.error(f"Failed to initialize email components: {str(e)}")
        raise

    # Register blueprints
    try:
        init_routes(app)
        app.logger.info("Routes initialized successfully")
    except Exception as e:
        app.logger.error(f"Failed to initialize routes: {str(e)}")
        raise
        
    return app