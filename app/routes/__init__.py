"""Routes initialization module for the Flask application.

This module handles the registration of all route blueprints used in the application.
It provides centralized route initialization to keep the application structure organized.

Typical usage example:
    from app import create_app
    app = create_app()
    init_routes(app)
"""

from flask import Flask, redirect, url_for
import logging
from ..auth.routes import auth_bp
from .email_routes import email_bp
from .test_routes import test_bp
from .user_routes import user_bp
from .static_pages import static_pages_bp
from .demo_routes import demo_bp
logger = logging.getLogger(__name__)

def init_routes(app: Flask):
    """Initialize all route blueprints for the Flask application.
    
    Registers all blueprint modules with their respective URL prefixes and
    sets up the root route to redirect to the login page. Test routes are
    only registered when the application is in debug mode.
    
    Args:
        app: Flask application instance to register routes with.
        
    Raises:
        Exception: If route registration fails, the error is logged and re-raised.
    """
    try:
        app.register_blueprint(auth_bp, url_prefix='/auth')
        app.register_blueprint(email_bp, url_prefix='/email')
        app.register_blueprint(user_bp, url_prefix='/user')
        app.register_blueprint(static_pages_bp, url_prefix='/pages')
        app.register_blueprint(demo_bp, url_prefix='/demo')
        if app.debug:  # Only register test routes in debug mode
            app.register_blueprint(test_bp, url_prefix='/test')
        #if multiprocessing.parent_process():
        #    logger.info(f"Routes initialized for worker process (PID: {os.getpid()})" )
    except Exception as e:
        logger.error(f"Failed to register routes: {str(e)}")
        raise
    
    # Add root route
    @app.route('/')
    def root():
        """Root route handler that redirects to the login page.
        
        Returns:
            A redirect response to the login page.
        """
        return redirect(url_for('auth.show_login'))
