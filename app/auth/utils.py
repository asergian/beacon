"""Authentication utility functions.

This module provides utility functions for authentication workflows,
including OAuth configuration, user creation, and session management.
"""

import os
import json
import pathlib
import logging
from datetime import datetime
from flask import current_app, url_for, session
from google.oauth2 import id_token
from google.auth.transport import requests
from app.models import db
from app.models.user import User
from app.models.activity import log_activity

# Set up logger
logger = logging.getLogger(__name__)

# OAuth 2.0 configuration
SCOPES = [
    'openid',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send'
]

def get_oauth_config():
    """Get OAuth configuration from environment or file.
    
    Retrieves OAuth client configuration from environment variables or a client secrets
    file, depending on what's available. Creates a temporary file with configuration
    if using environment variables.
    
    Returns:
        str: Path to the client secrets file for OAuth Flow.
        
    Raises:
        FileNotFoundError: If client secrets file can't be found or created.
        ValueError: If environment variables are incomplete.
    """
    # First try environment variables
    if all(os.environ.get(key) for key in ['GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_SECRET']):
        # Set up redirect URIs for both dev and prod
        redirect_uris = [
            url_for('auth.oauth2callback', _external=True),  # Current environment's URL
            'https://localhost:5000/auth/oauth2callback'      # Development with HTTPS
        ]
        
        # Add production URIs if we're in production
        if os.environ.get('RENDER'):
            redirect_uris.extend([
                'https://beacon-is5i.onrender.com/auth/oauth2callback',  # Render domain
                'https://beacon.shronas.com/auth/oauth2callback'         # Custom domain
            ])
        
        # Create a temporary client secrets file
        client_config = {
            "web": {
                "client_id": os.environ.get('GOOGLE_CLIENT_ID'),
                "client_secret": os.environ.get('GOOGLE_CLIENT_SECRET'),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "redirect_uris": redirect_uris
            }
        }
        
        # Save to a temporary file in /tmp to match original functionality
        client_secrets_file = '/tmp/client_secrets.json'
        with open(client_secrets_file, 'w') as f:
            json.dump(client_config, f)
        
        return client_secrets_file
        
    # Fallback to client secrets file
    client_secrets_file = os.path.join(
        pathlib.Path(__file__).parent.parent.parent,
        'beacon-gmail-client.json'
    )
    
    if not os.path.exists(client_secrets_file):
        raise FileNotFoundError(
            f"Client secrets file not found at {client_secrets_file} and "
            "environment variables for OAuth are not set."
        )
    
    return client_secrets_file

def create_or_update_user(user_info, credentials):
    """Create or update a user from OAuth user info.
    
    Takes the user information from OAuth and either creates a new user
    or updates an existing one based on the email address.
    
    Args:
        user_info (dict): User information from Google OAuth.
        credentials (dict): OAuth credentials for the user.
        
    Returns:
        User: The created or updated user object.
        
    Raises:
        Exception: If there's an error creating or updating the user.
    """
    try:
        # Start a transaction
        db.session.begin()
        
        # Extract user info
        email = user_info.get('email')
        
        # Find or create user
        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(
                email=email,
                name=user_info.get('name', 'Unknown'),
                picture=user_info.get('picture'),
                roles=['user']
            )
            db.session.add(user)
            db.session.flush()  # Get user ID without committing
            
            # Log user creation
            activity = log_activity(
                user_id=user.id,
                activity_type='user_created',
                description=f"User created via OAuth: {email}"
            )
            db.session.add(activity)
        
        # Update user information
        user.name = user_info.get('name', user.name)
        user.picture = user_info.get('picture', user.picture)
        user.last_login = datetime.now()
        
        # Log the login
        activity = log_activity(
            user_id=user.id,
            activity_type='user_login',
            description=f"User logged in via OAuth: {email}"
        )
        db.session.add(activity)
        
        # Create session data - keep the original format
        session['user'] = {
            'id': user.id,
            'email': user.email,
            'name': user.name,
            'picture': user.picture,
            'roles': user.roles,
            'is_demo': False
        }
        
        # Store credentials in session
        session['credentials'] = credentials
        
        # Commit all changes
        db.session.commit()
        
        return user
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating/updating user: {e}")
        raise 