"""Authentication routes for the Beacon application.

This module defines the Flask routes for authentication, including login, logout, 
and OAuth processing. It uses the Blueprint defined in __init__.py to register 
all routes with the 'auth' prefix.
"""

import logging
from flask import redirect, url_for, session, render_template, request

from app.models.activity import log_activity
from . import auth_bp
from .oauth import oauth_login as oauth_login_handler, oauth2callback as oauth2callback_handler

# Set up logger
logger = logging.getLogger(__name__)

@auth_bp.route('/')
@auth_bp.route('/login')
def show_login():
    """Display the login page.
    
    Renders the login template, which provides options for OAuth login and
    demo mode. If a user is already logged in, redirects to the home page.
    
    Returns:
        Response: Rendered login template or redirect to home page.
    """
    # Check for error parameter to show error message
    error = request.args.get('error')
    
    if 'user' in session:
        return redirect(url_for('email.home'))
    return render_template('login.html', error=error)

@auth_bp.route('/oauth/login')
def oauth_login():
    """Initiate the OAuth login flow.
    
    Delegates to the OAuth module to start the authentication process.
    
    Returns:
        Response: Redirect to Google's OAuth authorization page.
    """
    return oauth_login_handler()

@auth_bp.route('/oauth2callback')
async def oauth2callback():
    """Handle the OAuth 2.0 callback from Google.
    
    Delegates to the OAuth module to process the authorization response.
    
    Returns:
        Response: Redirect to the home page on success or error page on failure.
    """
    return await oauth2callback_handler()

@auth_bp.route('/logout')
def logout():
    """Clear the user's session and log them out.
    
    Logs the logout activity if a user ID is present, clears the session,
    and redirects to the login page.
    
    Returns:
        Response: Redirect to the login page.
    """
    if 'user' in session:
        user_id = session['user'].get('id')
        if user_id:
            log_activity(
                user_id=user_id,
                activity_type='user_logout',
                description=f"User logged out: {session['user'].get('email')}"
            )
    
    logger.info("User logged out\n")
    session.clear()
    return redirect(url_for('auth.show_login', from_logout=1))

@auth_bp.route('/demo-login')
def demo_login():
    """Create a demo session without OAuth.
    
    Delegates to the demo.auth module for handling demo login functionality.
    
    Returns:
        Response: Redirect to demo home page on success or login page on error.
    """
    from app.demo.auth import demo_login as demo_login_handler
    return demo_login_handler()