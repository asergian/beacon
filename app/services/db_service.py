"""Database service module.

This module handles the initialization and configuration of database connections
using SQLAlchemy and Flask-Migrate for migration management.

Typical usage example:
    from app.services.db_service import init_db
    init_db(app)
"""

import logging
from flask import current_app
from flask_migrate import Migrate
from ..models import db

logger = logging.getLogger(__name__)

def init_db(app):
    """Initialize database connections and migrations.
    
    This function configures SQLAlchemy with the Flask application
    and sets up Flask-Migrate for database migrations.
    
    Args:
        app: Flask application instance
    """
    # Initialize SQLAlchemy with the Flask app
    db.init_app(app)
    
    # Initialize Flask-Migrate for database migrations
    Migrate(app, db)
    
    # Log database connection info (hide credentials)
    db_uri = app.config['SQLALCHEMY_DATABASE_URI']
    safe_uri = db_uri.split('@')[1] if '@' in db_uri else 'localhost'
    logger.info(f"Database connection initialized to: {safe_uri}")
    
    # Optionally add any additional database setup here
    # For example, connection pooling configuration, etc. 