"""Flask application factory with email processing setup.

This module provides the application factory pattern for creating a Flask application
with email processing capabilities. It handles the initialization of various components
including OpenAI client, email orchestration, and route registration.

Typical usage example:
    from app import create_app
    app = create_app()

Attributes:
    application: ASGI application instance for production environments.
"""

# Standard library imports
import logging
import os
from datetime import datetime, timedelta
from typing import Optional

# Third-party imports
from asgiref.wsgi import WsgiToAsgi
from flask import Flask, g, session, jsonify

# Local application imports
from .config import Config
from .utils.logging_setup import configure_logging
from .models import db, User

# Email processing components
from .email.core.email_processor import EmailProcessor
from .email.core.email_parsing import EmailParser
from .email.models.analysis_settings import ProcessingConfig
from .email.analyzers.semantic_analyzer import SemanticAnalyzer
from .email.analyzers.content_analyzer_subprocess import ContentAnalyzerSubprocess
from .email.utils.priority_scorer import PriorityScorer
from .email.pipeline.pipeline import create_pipeline
from .email.core.gmail_client_subprocess import GmailClientSubprocess
from .email.storage.cache import RedisEmailCache

# Utility imports
from .utils.memory_profiling import MemoryProfilingMiddleware

# Service initialization
from .services.openai_service import init_openai_client
from .services.redis_service import init_redis_client
from .services.db_service import init_db

# Route initialization
from .routes import init_routes

# This must be defined at the module level for Hypercorn to find it
application = None


class ASGIApp:
    """ASGI wrapper for WSGI Flask application.
    
    This class wraps a Flask application to make it compatible with ASGI servers
    like Hypercorn, while also handling lifespan events properly.
    
    Attributes:
        app: The WSGI-to-ASGI wrapped Flask application.
    """
    
    def __init__(self, app):
        """Initialize the ASGI wrapper.
        
        Args:
            app: The Flask application to wrap.
        """
        self.app = WsgiToAsgi(app)
    
    async def __call__(self, scope, receive, send):
        """Handle ASGI protocol events.
        
        Processes lifespan events for startup and shutdown, and delegates other
        requests to the wrapped Flask application.
        
        Args:
            scope: ASGI scope dictionary containing request metadata.
            receive: ASGI receive function for receiving messages.
            send: ASGI send function for sending messages.
        """
        if scope["type"] == "lifespan":
            while True:
                message = await receive()
                if message["type"] == "lifespan.startup":
                    # Perform any startup tasks
                    await send({"type": "lifespan.startup.complete"})
                elif message["type"] == "lifespan.shutdown":
                    # Perform any cleanup
                    await self.app.close_openai_client()
                    await self.app.close_redis_client()
                    await send({"type": "lifespan.shutdown.complete"})
                    return
        else:
            await self.app(scope, receive, send)

def create_app(config_class: Optional[object] = Config) -> Flask:
    """Create and configure the Flask application.
    
    This factory function initializes and configures a Flask application with all
    necessary services, middleware, and route registrations. It sets up database
    connections, email processing components, and security settings.
    
    Args:
        config_class: Configuration class or object to use. Defaults to Config.
            If a class is provided, it will be instantiated.
            
    Returns:
        Flask: A configured Flask application instance.
        
    Raises:
        Exception: If initialization of any component fails.
    """
    # Configure logging first
    configure_logging()
    logger = logging.getLogger(__name__)

    flask_app = Flask(__name__)

    # Get worker information
    worker_id = os.environ.get('HYPERCORN_WORKER_ID')
    is_worker = bool(worker_id)
    
    # Basic setup (no logging needed)
    flask_app.logger.handlers.clear()
    flask_app.config.from_object(config_class() if isinstance(config_class, type) else config_class)
    flask_app.secret_key = flask_app.config.get('FLASK_SECRET_KEY') or os.urandom(24)
    flask_app.config['SESSION_TYPE'] = 'filesystem'
    flask_app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
    flask_app.config['SESSION_PERMANENT'] = True

    # Trust proxy headers for HTTPS detection
    if os.environ.get('RENDER'):
        flask_app.config['PREFERRED_URL_SCHEME'] = 'https'
        # Trust the X-Forwarded-Proto header from Render/Cloudflare
        flask_app.config['PROXY_FIX_X_PROTO'] = 1
        from werkzeug.middleware.proxy_fix import ProxyFix
        flask_app.wsgi_app = ProxyFix(
            flask_app.wsgi_app,
            x_proto=1,  # Number of proxy servers
            x_host=1,
            x_prefix=1
        )
    
    # Initialize services
    try:
        os.makedirs(flask_app.instance_path)
    except OSError:
        pass
    
    try:
        # Initialize database
        init_db(flask_app)
        
        # Initialize core services
        with flask_app.app_context():
            # Initialize OpenAI client
            init_openai_client(flask_app)
            
            # Initialize Redis (if needed)
            init_redis_client(flask_app)
        
        # Initialize analyzers
        text_analyzer = ContentAnalyzerSubprocess()
        llm_analyzer = SemanticAnalyzer()
        
        # Create priority calculator
        priority_calculator = PriorityScorer(
            vip_senders=set(flask_app.config.get('VIP_SENDERS', [])),
            config=ProcessingConfig()
        )
        priority_calculator.set_priority_threshold(50)

        # Create Gmail client and parser
        # Use the subprocess version for better memory isolation
        gmail_client = GmailClientSubprocess()
        parser = EmailParser()
        
        # Create and store email processor
        processor = EmailProcessor(
            email_client=gmail_client,
            text_analyzer=text_analyzer,
            llm_analyzer=llm_analyzer,
            priority_calculator=priority_calculator,
            parser=parser
        )
        
        # Create cache with function to get Redis client
        cache = RedisEmailCache(flask_app.get_redis_client)
        
        # Create and store pipeline
        flask_app.pipeline = create_pipeline(
            connection=gmail_client,
            parser=parser,
            processor=processor,
            cache=cache
        )
        
        # User authentication and session management
        @flask_app.before_request
        def load_user():
            """Load user from session before each request.
            
            Populates g.user with User object if a valid user session exists,
            otherwise sets g.user to None.
            """
            # Use the original nested structure to avoid breaking existing code
            if 'user' in session and isinstance(session['user'], dict):
                user_id = session['user'].get('id')
                if user_id:
                    g.user = User.query.get(user_id)
                else:
                    g.user = None
            else:
                g.user = None
        
        # Health check endpoint
        @flask_app.route('/health')
        def health_check():
            """Health check endpoint for monitoring.
            
            Returns:
                dict: JSON response with status and current timestamp.
            """
            return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})
        
        # Global error handler
        @flask_app.errorhandler(Exception)
        def handle_exception(e):
            """Global exception handler for all routes.
            
            Logs exceptions and returns appropriate JSON responses based on
            the application's debug setting.
            
            Args:
                e: The exception that was raised.
                
            Returns:
                tuple: JSON error response and HTTP status code.
            """
            # Log the error
            logger.exception("Unhandled exception: %s", str(e))
            
            # Return JSON response for API endpoints
            if flask_app.config.get('DEBUG'):
                # Include traceback in debug mode
                import traceback
                return jsonify(error=str(e), traceback=traceback.format_exc()), 500
            else:
                # Generic error in production
                return jsonify(error="Server error"), 500
        
        # Register routes
        init_routes(flask_app)
        
        # Log initialization status based on environment
        if is_worker:
            logger.info(f"Worker process initialized (PID: {os.getpid()})")
        else:
            logger.info("Main application initialized\n")
        
        # Add memory profiling in development
        if flask_app.config.get('PROFILE_MEMORY', False):
            flask_app.wsgi_app = MemoryProfilingMiddleware(flask_app.wsgi_app)
            logger.info("Memory profiling enabled")
        
        # Set the global application variable for ASGI servers
        global application
        application = ASGIApp(flask_app)
        
        return flask_app
        
    except Exception as e:
        logger.exception("Error creating app: %s", str(e))
        raise


def initialize_render_app():
    """Initialize the application for Render deployment environment.
    
    This function is automatically called when running on the Render platform.
    It configures the application for production deployment, setting up port
    binding and worker configuration. The global application variable is set
    for ASGI servers to use.
    
    Returns:
        None
    
    Raises:
        Exception: If initialization fails, the error is logged and re-raised.
    """
    try:
        # Log deployment environment and port binding
        logger = logging.getLogger(__name__)
        port = int(os.environ.get('PORT', 10000))
        
        # Explicitly bind to port to help Render detect it
        from hypercorn.config import Config as HypercornConfig
        config = HypercornConfig()
        config.bind = [f"0.0.0.0:{port}"]
        
        global application
        application = ASGIApp(create_app())
            
        logger.info(
            "Initializing application for Render:\n"
            f"    Environment: {os.environ.get('FLASK_ENV', 'production')}\n"
            f"    Port: {port}\n"
            f"    Workers: {os.environ.get('HYPERCORN_WORKERS', '1')}\n"
            f"    Worker Class: {os.environ.get('HYPERCORN_WORKER_CLASS', 'asyncio')}"
        )
        
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to initialize application on Render: {e}")
        raise


# Initialize the application for production
if os.environ.get('RENDER'):
    initialize_render_app()


# Export for ASGI servers
__all__ = ['application', 'create_app']