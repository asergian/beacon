"""OAuth authentication handling.

This module contains functions specifically for handling Google OAuth2 authentication,
including route handlers for the OAuth flow and callback processing.
"""

import logging
import os
from datetime import datetime
from flask import current_app, redirect, request, url_for, session, render_template
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport import requests

from .utils import get_oauth_config, create_or_update_user, SCOPES

# Set up logger
logger = logging.getLogger(__name__)

def oauth_login():
    """Initiate the OAuth login flow.
    
    Creates an OAuth flow and redirects the user to Google's authorization page.
    
    Returns:
        Response: Redirect to Google's OAuth authorization page.
        
    Raises:
        Exception: If there's an error setting up the OAuth flow.
    """
    logger.info("Starting OAuth login flow")
    try:
        # Get OAuth config and create flow
        client_secrets_file = get_oauth_config()
        flow = Flow.from_client_secrets_file(
            client_secrets_file,
            scopes=SCOPES,
            redirect_uri=url_for('auth.oauth2callback', _external=True)
        )
        
        # Generate URL for request step
        authorization_url, state = flow.authorization_url(
            access_type='offline',  # Enable refresh tokens
            include_granted_scopes='true',  # Enable incremental auth
            prompt='consent'  # Force re-consent to get refresh token
        )
        
        # Store the state in the session for later verification
        session['state'] = state
        
        # Clean up temporary file if it was created
        if client_secrets_file.startswith('/tmp/'):
            try:
                os.remove(client_secrets_file)
            except:
                pass
        
        return redirect(authorization_url)
    
    except Exception as e:
        logger.error(f"Error starting OAuth flow: {e}")
        return redirect(url_for('auth.show_login', error='oauth_setup_error'))

async def oauth2callback():
    """Handle the OAuth 2.0 callback from Google.
    
    Processes the authorization response, exchanges the authorization code for tokens,
    and creates or updates the user record with information from Google.
    
    Returns:
        Response: Redirect to the home page on success or an error page on failure.
        
    Raises:
        ValueError: If the OAuth state doesn't match or other validation errors.
    """
    logger.info("Handling OAuth callback")
    
    try:
        # Verify HTTPS in production
        if not request.is_secure and not current_app.debug:
            logger.error("Attempted OAuth callback over non-HTTPS connection")
            return render_template('login.html', 
                                error="HTTPS is required for secure authentication. Please use HTTPS."), 400
        
        # Verify state matches to prevent CSRF
        state = session.get('state')
        if not state or state != request.args.get('state'):
            logger.warning("OAuth state mismatch")
            return render_template('login.html', 
                                error="Invalid authentication state. Please try again."), 400
        
        # Clear the session after state verification but before setting new user data
        session.clear()
            
        # Get authorization code from callback
        code = request.args.get('code')
        if not code:
            logger.warning("No authorization code received")
            return render_template('login.html', 
                                error="No authorization code received. Please try again."), 400
        
        # Get OAuth config and create flow
        client_secrets_file = get_oauth_config()
        flow = Flow.from_client_secrets_file(
            client_secrets_file,
            scopes=SCOPES,
            redirect_uri=request.base_url
        )
        
        # Exchange authorization code for tokens
        flow.fetch_token(
            authorization_response=request.url,
            access_type='offline',
            include_granted_scopes=True
        )
        credentials = flow.credentials
        
        # Clean up temporary file if it was created
        if client_secrets_file.startswith('/tmp/'):
            try:
                os.remove(client_secrets_file)
            except:
                pass
        
        # Get user info from ID token
        id_info = id_token.verify_oauth2_token(
            credentials.id_token, 
            requests.Request(),
            flow.client_config['client_id']
        )
        
        # Verify email is verified
        if not id_info.get('email_verified'):
            logger.warning(f"Unverified email attempt: {id_info.get('email')}")
            return render_template('login.html', 
                                error="Email address not verified by Google. Please verify your email first."), 400
        
        # Store credentials as a dictionary
        creds_dict = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes,
            'id_token': credentials.id_token
        }
        
        # Create or update user
        try:
            create_or_update_user(id_info, creds_dict)
            
            # Redirect to home page on success
            logger.info(f"User authenticated successfully: {id_info.get('email')}")
            return redirect(url_for('email.home'))
            
        except Exception as e:
            logger.error(f"Database error during authentication: {str(e)}")
            return render_template('login.html', 
                                error="Failed to complete authentication. Please try again."), 500
        
    except Exception as e:
        logger.error(f"Error in OAuth callback: {e}")
        # Handle possible errors
        return render_template('login.html', 
                            error="Authentication error. Please try again later."), 400 