"""Authentication routes for Google OAuth2."""

from flask import Blueprint, current_app, redirect, request, url_for, session, render_template
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport import requests
import os
import pathlib
from datetime import datetime
import logging
from ..models import db, User, log_activity

# Set up logger
logger = logging.getLogger(__name__)
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

@auth_bp.route('/oauth/login')
def oauth_login():
    """Initiate the OAuth login flow."""
    logger.info("Starting OAuth login flow")
    try:
        # Create flow instance to manage the OAuth 2.0 Authorization Grant Flow
        flow = Flow.from_client_secrets_file(
            os.path.join(pathlib.Path(__file__).parent.parent.parent, 'beacon-gmail-client.json'),
            scopes=SCOPES,
            redirect_uri=url_for('auth.oauth2callback', _external=True)
        )
        
        # Generate URL for request to Google's OAuth 2.0 server
        authorization_url, state = flow.authorization_url(
            access_type='offline',  # Enable refresh token
            include_granted_scopes='true',  # Enable incremental authorization
            prompt='consent'  # Force consent screen to ensure refresh token
        )
        
        # Store the state in the session for later validation
        session['state'] = state
        
        # Redirect to Google's OAuth 2.0 server
        return redirect(authorization_url)
        
    except Exception as e:
        logger.error(f"Failed to initiate OAuth flow: {e}")
        return render_template('login.html', error="Failed to start authentication. Please try again."), 500

@auth_bp.route('/oauth2callback')
async def oauth2callback():
    """Handle the OAuth 2.0 callback from Google."""
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
        
        # Get OAuth credentials
        try:
            flow = Flow.from_client_secrets_file(
                os.path.join(pathlib.Path(__file__).parent.parent.parent, 'beacon-gmail-client.json'),
                scopes=SCOPES,
                redirect_uri=request.base_url
            )
            
            flow.fetch_token(
                authorization_response=request.url,
                access_type='offline',
                include_granted_scopes=True
            )
            
            credentials = flow.credentials
            
            # Get user info from ID token
            id_info = id_token.verify_oauth2_token(
                credentials.id_token, 
                requests.Request(),
                flow.client_config['client_id']
            )
        except Exception as e:
            logger.error(f"OAuth flow error: {e}")
            return render_template('login.html', 
                                error="Authentication failed. Please try again."), 500
        
        # Handle user creation/update and activity logging in a transaction
        try:
            # Start a transaction
            db.session.begin()
            
            # Find or create user
            user = User.query.filter_by(email=id_info['email']).first()
            is_new_user = user is None
            
            if is_new_user:
                # Create new user
                user = User(
                    email=id_info['email'],
                    name=id_info.get('name'),
                    picture=id_info.get('picture'),
                    roles=['user', 'admin'] if id_info['email'] == 'alex.sergian@gmail.com' else ['user']
                )
                db.session.add(user)
                db.session.flush()  # Get the user ID without committing
                
                # Log user creation in the same transaction
                activity = log_activity(
                    user_id=user.id,
                    activity_type='user_created',
                    description=f"New user account created for {user.email}"
                )
                db.session.add(activity)
            else:
                # Update existing user
                user.name = id_info.get('name')
                user.picture = id_info.get('picture')
                user.last_login = datetime.utcnow()
                
                # Log user login in the same transaction
                activity = log_activity(
                    user_id=user.id,
                    activity_type='user_login',
                    description=f"User logged in: {user.email}"
                )
                db.session.add(activity)
            
            # Store user info and credentials in session
            session['user'] = {
                'id': user.id,
                'email': user.email,
                'name': user.name,
                'picture': user.picture,
                'roles': user.roles
            }
            session['credentials'] = {
                'token': credentials.token,
                'refresh_token': credentials.refresh_token,
                'token_uri': credentials.token_uri,
                'client_id': credentials.client_id,
                'client_secret': credentials.client_secret,
                'scopes': credentials.scopes
            }
            
            # Commit the entire transaction
            db.session.commit()
            logger.info(f"Successfully authenticated user: {user.email}")
            
            # Redirect to email home
            return redirect(url_for('email.home'))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Database error during authentication: {str(e)}")
            return render_template('login.html', 
                                error="Failed to complete authentication. Please try again."), 500
            
    except Exception as e:
        logger.error(f"OAuth callback error: {e}")
        return render_template('login.html', 
                            error="Authentication failed. Please try again."), 500

@auth_bp.route('/logout')
def logout():
    """Clear the user's session."""
    if 'user' in session:
        user_id = session['user'].get('id')
        if user_id:
            log_activity(
                user_id=user_id,
                activity_type='user_logout',
                description=f"User logged out: {session['user'].get('email')}"
            )
    
    logger.info("User logged out")
    session.clear()
    return redirect(url_for('auth.show_login', from_logout=1))