"""Route initialization for the application."""

from flask import Flask, redirect, url_for
import logging
from ..auth.routes import auth_bp
from .email_routes import email_bp
from .test_routes import test_bp
from .user_routes import user_bp
from .static_pages import static_pages_bp
logger = logging.getLogger(__name__)

def init_routes(app: Flask):
    """Initialize all routes for the application."""
    try:
        app.register_blueprint(auth_bp, url_prefix='/auth')
        app.register_blueprint(email_bp, url_prefix='/email')
        app.register_blueprint(user_bp, url_prefix='/user')
        app.register_blueprint(static_pages_bp, url_prefix='/pages')
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
        return redirect(url_for('auth.show_login'))
