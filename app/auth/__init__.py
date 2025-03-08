"""Authentication module for the Beacon application.

This module handles user authentication, including OAuth flows with Google,
session management, and route protection through decorators. It's organized
into several components for better separation of concerns:

Components:
    decorators: Authentication-related decorators like login_required
    utils: Authentication utility functions for OAuth and user management 
    oauth: OAuth-specific handlers for the authentication flow
    routes: Authentication routes for login, logout, and OAuth callbacks

The module provides a Flask Blueprint that registers all routes under the
/auth prefix and ensures proper authentication for the application.

Usage:
    from app.auth import auth_bp  # Import the blueprint
    app.register_blueprint(auth_bp, url_prefix='/auth')  # Register with Flask app
    
    from app.auth import login_required  # Import decorators
    @app.route('/protected')
    @login_required
    def protected_route():
        return "This page requires login"
"""

from flask import Blueprint

# Create the auth blueprint
auth_bp = Blueprint('auth', __name__)

# Import routes to register them with the blueprint
from . import routes

# Make decorators available at module level for clean imports
from .decorators import login_required, admin_required

# Also make key utility and OAuth functions available
from .utils import get_oauth_config, create_or_update_user
from .oauth import oauth_login, oauth2callback

__all__ = [
    'auth_bp',
    'login_required',
    'admin_required',
    'get_oauth_config',
    'create_or_update_user',
    'oauth_login',
    'oauth2callback'
]
