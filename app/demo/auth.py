"""Demo authentication module.

This module provides authentication functionality specific to demo mode.
It allows users to sign in with a demo account without requiring actual
OAuth credentials, creating a temporary session for demonstration purposes.

Functions:
    demo_login: Authenticates a demo user session without OAuth.
"""

import logging
from datetime import datetime
from flask import session, redirect, url_for
from app.models import db
from app.models.user import User
from app.models.activity import log_activity

logger = logging.getLogger(__name__)

# OAuth scopes required for demo user (matching real auth)
DEMO_SCOPES = [
    'openid',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send'
]

def demo_login():
    """Create a demo user session without OAuth authentication.
    
    Creates or finds a demo user account and establishes a session
    with mock credentials. This allows users to explore the application's
    features without requiring actual Google account authentication.
    
    Returns:
        Response: A redirect to the demo home page.
        
    Raises:
        Exception: If there's an error creating or logging in the demo user.
    """
    logger.info("Starting demo login")
    try:
        # Clear any existing session
        session.clear()
        
        # Find or create demo user
        demo_email = "demo@example.com"
        demo_user = User.query.filter_by(email=demo_email).first()
        
        if not demo_user:
            demo_user = User(
                email=demo_email,
                name="Demo User",
                picture="https://api.dicebear.com/7.x/avataaars/svg?seed=Demo&backgroundColor=4A90E2",
                roles=['demo']
            )
            db.session.add(demo_user)
            db.session.flush()
        
        # Update last login time
        demo_user.last_login = datetime.utcnow()
        
        # Log the demo login activity
        activity = log_activity(
            user_id=demo_user.id,
            activity_type='demo_login',
            description="Demo user logged in"
        )
        db.session.add(activity)
        
        # Store demo user info in session
        session['user'] = {
            'id': demo_user.id,
            'email': demo_user.email,
            'name': demo_user.name,
            'picture': demo_user.picture,
            'roles': demo_user.roles,
            'is_demo': True
        }
        
        # Store mock credentials in session
        session['credentials'] = {
            'token': 'demo_token',
            'refresh_token': None,
            'token_uri': None,
            'client_id': None,
            'client_secret': None,
            'scopes': DEMO_SCOPES,
            'id_token': None
        }
        
        db.session.commit()
        logger.info(f"Demo user logged in successfully")
        
        return redirect(url_for('demo.demo_home'))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error during demo login: {e}")
        # Clear any partial session data
        session.clear()
        # Redirect to login page with error
        return redirect(url_for('auth.show_login', error='demo_error')) 