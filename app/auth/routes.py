"""Authentication routes for Google OAuth2."""

from flask import Blueprint, current_app, redirect, request, url_for, session, render_template
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport import requests
import os
import pathlib
from ..utils.logging_config import setup_logging

# Set up logger
logger = setup_logging()
auth_bp = Blueprint('auth', __name__)

# OAuth 2.0 configuration
SCOPES = [
    'openid',  # Added openid scope
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/gmail.readonly'
]

@auth_bp.route('/')
@auth_bp.route('/login')
def show_login():
    """Display the login page."""
    if 'user' in session:
        return redirect(url_for('email.home'))
    return render_template('login.html')

@auth_bp.route('/login/start', methods=['POST'])
def start_login():
    """Initiate Google OAuth2 login flow."""
    logger.info("Starting OAuth login flow")
    
    try:
        # Verify HTTPS
        if not request.is_secure:
            logger.error("Attempted OAuth flow over non-HTTPS connection")
            return render_template('login.html', 
                                error="HTTPS is required for secure authentication. Please use HTTPS."), 400
        
        # Load client configuration
        client_secrets_file = os.path.join(
            pathlib.Path(__file__).parent.parent.parent,
            'beacon-gmail-client.json'
        )
        
        # Create flow instance to manage OAuth 2.0 Authorization Grant Flow
        flow = Flow.from_client_secrets_file(
            client_secrets_file,
            scopes=SCOPES,
            redirect_uri=url_for('auth.oauth2callback', _external=True)
        )
        
        # Generate URL for request to Google's OAuth 2.0 server
        authorization_url, state = flow.authorization_url(
            access_type='offline',  # Enable refresh token
            include_granted_scopes='true'  # Enable incremental authorization
        )
        
        logger.info("Authorization URL: %s", authorization_url)
        
        # Store the state in the session for later validation
        session['state'] = state
        logger.debug("OAuth state stored in session")
        
        return redirect(authorization_url)
        
    except Exception as e:
        logger.error(f"Failed to initiate OAuth flow: {e}")
        return render_template('login.html', 
                            error="Failed to initiate authentication. Please try again."), 500

@auth_bp.route('/oauth2callback')
async def oauth2callback():
    """Handle the OAuth 2.0 callback from Google."""
    logger.info("Handling OAuth callback")
    
    try:
        # Verify HTTPS
        if not request.is_secure:
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
        
        client_secrets_file = os.path.join(
            pathlib.Path(__file__).parent.parent.parent,
            'beacon-gmail-client.json'
        )
        
        flow = Flow.from_client_secrets_file(
            client_secrets_file,
            scopes=SCOPES,
            state=state,
            redirect_uri=url_for('auth.oauth2callback', _external=True)
        )
        
        # Use authorization code to get credentials
        flow.fetch_token(authorization_response=request.url)
        credentials = flow.credentials
        
        # Get user info from ID token
        id_info = id_token.verify_oauth2_token(
            credentials.id_token, 
            requests.Request(),
            flow.client_config['client_id']
        )
        
        # Store user info and credentials in session
        session['user'] = {
            'email': id_info['email'],
            'name': id_info.get('name'),
            'picture': id_info.get('picture')
        }
        session['credentials'] = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }
        
        logger.info(f"Successfully authenticated user: {id_info['email']}")
        return redirect(url_for('email.home'))
        
    except ValueError as e:
        logger.error(f"Error verifying ID token: {e}")
        return render_template('login.html', 
                            error="Failed to verify authentication. Please try again."), 400
    except Exception as e:
        logger.error(f"OAuth callback error: {e}")
        return render_template('login.html', 
                            error="Authentication failed. Please try again."), 500

@auth_bp.route('/logout')
def logout():
    """Clear the user's session."""
    logger.info("User logged out")
    session.clear()
    return redirect(url_for('auth.show_login'))