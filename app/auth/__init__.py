"""Authentication module for Google OAuth2 integration."""

from flask import Blueprint
from .routes import init_auth_routes

def create_auth_blueprint() -> Blueprint:
    """Create and configure the authentication blueprint.
    
    Returns:
        Blueprint: The configured authentication blueprint
    """
    auth_bp = Blueprint('auth', __name__)
    init_auth_routes(auth_bp)
    return auth_bp 