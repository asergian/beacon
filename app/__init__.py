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

from flask import Flask, g, current_app, session
import logging
from openai import AsyncOpenAI
from typing import Optional
import os
from datetime import timedelta
from asgiref.wsgi import WsgiToAsgi
import multiprocessing

from .config import Config, configure_logging
from .models import db, User
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

# This will be our ASGI application instance
application = None

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
        
        # Log initialization status based on process type
        if multiprocessing.parent_process():
            logger.debug(f"OpenAI client initialized successfully for worker process (PID: {os.getpid()})")
        
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
    flask_app = Flask(__name__)
    
    # Get worker information
    worker_id = os.environ.get('HYPERCORN_WORKER_ID')
    is_worker = bool(worker_id)
    logger = logging.getLogger(__name__)
    
    # Basic setup (no logging needed)
    flask_app.logger.handlers.clear()
    flask_app.config.from_object(config_class() if isinstance(config_class, type) else config_class)
    flask_app.secret_key = flask_app.config.get('FLASK_SECRET_KEY') or os.urandom(24)
    flask_app.config['SESSION_TYPE'] = 'filesystem'
    flask_app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
    flask_app.config['SESSION_PERMANENT'] = True
    
    # Initialize extensions (no logging needed)
    db.init_app(flask_app)
    Migrate(flask_app, db)
    
    try:
        os.makedirs(flask_app.instance_path)
    except OSError:
        pass
    
    try:
        # Initialize components
        with flask_app.app_context():
            init_openai_client(flask_app)
            
        # Initialize NLP model
        nlp_model = create_nlp_model()
        
        # Initialize analyzers
        text_analyzer = ContentAnalyzer(nlp_model)
        llm_analyzer = SemanticAnalyzer()
        
        # Create priority calculator
        priority_calculator = PriorityScorer(
            vip_senders=set(flask_app.config.get('VIP_SENDERS', [])),
            config=ProcessingConfig()
        )
        priority_calculator.set_priority_threshold(50)

        # Create Gmail client and parser
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
        
        # Redis setup
        redis_url = flask_app.config.get('REDIS_URL')
        if not redis_url:
            if os.environ.get('RENDER'):
                raise ValueError("REDIS_URL environment variable is required in production")
            redis_url = 'redis://localhost:6379'
            logger.warning("No REDIS_URL configured, using default: %s", redis_url)

        try:
            if os.environ.get('RENDER'):
                # Upstash Redis in production
                from upstash_redis.asyncio import Redis as UpstashRedis
                # Extract token from URL if present, otherwise use separate env var
                upstash_token = flask_app.config.get('REDIS_TOKEN')
                if not upstash_token:
                    raise ValueError("REDIS_TOKEN environment variable is required for Upstash Redis")
                
                redis_client = UpstashRedis(url=redis_url, token=upstash_token)
                # Test the connection
                redis_client.set("_test_key", "test_value", ex=10)
                test_result = redis_client.get("_test_key")
                if test_result != "test_value":
                    raise ValueError("Redis connection test failed")
                
                logger.info("Upstash Redis connection initialized successfully")
                flask_app.config['REDIS_CLIENT'] = redis_client
            else:
                # Standard Redis for development
                from redis.asyncio import ConnectionPool, Redis
                pool = ConnectionPool.from_url(
                    redis_url,
                    max_connections=10,
                    decode_responses=True
                )
                flask_app.config['REDIS_POOL'] = pool
                logger.info("Local Redis connection pool initialized successfully")

        except Exception as e:
            logger.error("Failed to initialize Redis: %s", str(e))
            if os.environ.get('RENDER'):
                raise  # Re-raise in production
            # In development, we'll continue without Redis
            logger.warning("Continuing without Redis in development mode")
        
        # Create Redis client getter
        def get_redis_client():
            if 'redis_client' not in g:
                if os.environ.get('RENDER'):
                    # In production, use the Upstash client directly
                    g.redis_client = flask_app.config['REDIS_CLIENT']
                else:
                    # In development, use async Redis
                    loop = async_manager.ensure_loop()
                    g.redis_client = Redis(
                        connection_pool=flask_app.config.get('REDIS_POOL'),
                        decode_responses=True
                    )
            return g.redis_client
        
        def close_redis_client(e=None):
            if 'redis_client' in g:
                del g.redis_client
        
        flask_app.teardown_appcontext(close_redis_client)
        flask_app.get_redis_client = get_redis_client
        
        # Create cache with function to get Redis client
        cache = RedisEmailCache(get_redis_client)
        
        # Create and store pipeline
        flask_app.pipeline = create_pipeline(
            connection=gmail_client,
            parser=parser,
            processor=processor,
            cache=cache
        )
        
        # Register blueprints
        init_routes(flask_app)
        
        # Log initialization status based on process type
        if multiprocessing.parent_process():
            logger.info(f"Worker process initialized (PID: {os.getpid()})")
        else:
            logger.info("Main application initialized")
            
    except Exception as e:
        logger.error(f"Failed to initialize application: {e}")
        raise
        
    @flask_app.before_request
    def load_user():
        g.user = None
        if 'user' in session:
            g.user = User.query.get(session['user']['id'])
    
    @flask_app.route('/health')
    def health_check():
        """Health check endpoint for Render."""
        return {'status': 'healthy'}, 200

    # Create and store the ASGI application globally
    global application
    application = WsgiToAsgi(flask_app)
    
    return flask_app

# Initialize the application
if os.environ.get('RENDER'):
    # Only initialize if we're on Render
    flask_app = create_app()
    application = WsgiToAsgi(flask_app)
    
    # Log the port binding for Render
    port = int(os.environ.get('PORT', 10000))
    logger = logging.getLogger(__name__)
    logger.info(f"Initializing application for Render on port {port}")
else:
    # Just declare the variable for local dev
    application = None

# Export for ASGI servers
__all__ = ['application', 'create_app']