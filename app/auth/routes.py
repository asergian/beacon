"""Authentication routes for Google OAuth2."""

from flask import Blueprint, current_app, redirect, request, url_for, session, render_template
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport import requests
import os
import pathlib
from datetime import datetime
import logging
from app.models import db
from app.models.user import User
from app.models.activity import log_activity
import json

# Set up logger
logger = logging.getLogger(__name__)
auth_bp = Blueprint('auth', __name__)

# OAuth 2.0 configuration
SCOPES = [
    'openid',  # Added openid scope
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send'
]

def _get_oauth_config():
    """Get OAuth configuration from environment or file."""
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
        
        config = {
            'web': {
                'client_id': os.environ['GOOGLE_CLIENT_ID'],
                'client_secret': os.environ['GOOGLE_CLIENT_SECRET'],
                'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                'token_uri': 'https://oauth2.googleapis.com/token',
                'redirect_uris': redirect_uris
            }
        }
        # Write config to a temporary file for google-auth-oauthlib
        config_path = '/tmp/oauth-config.json'
        with open(config_path, 'w') as f:
            json.dump(config, f)
        return config_path
    
    # Fallback to JSON file
    json_path = os.path.join(pathlib.Path(__file__).parent.parent.parent, 'beacon-gmail-client.json')
    if not os.path.exists(json_path):
        raise RuntimeError("OAuth credentials not found. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables or provide beacon-gmail-client.json")
    return json_path

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
        # Get OAuth config and create flow
        client_secrets_file = _get_oauth_config()
        flow = Flow.from_client_secrets_file(
            client_secrets_file,
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
        
        # Clean up temporary file if it was created
        if client_secrets_file.startswith('/tmp/'):
            try:
                os.remove(client_secrets_file)
            except:
                pass
        
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
            client_secrets_file = _get_oauth_config()
            flow = Flow.from_client_secrets_file(
                client_secrets_file,
                scopes=SCOPES,
                redirect_uri=request.base_url
            )
            
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
                'scopes': credentials.scopes,
                'id_token': credentials.id_token  # Store the ID token
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

@auth_bp.route('/demo-login')
def demo_login():
    """Create a demo session without OAuth."""
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
        
        # Update last login
        demo_user.last_login = datetime.utcnow()
        
        # Log demo login
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
        
        # Store mock credentials
        session['credentials'] = {
            'token': 'demo_token',
            'refresh_token': None,
            'token_uri': None,
            'client_id': None,
            'client_secret': None,
            'scopes': SCOPES,
            'id_token': None
        }
        
        db.session.commit()
        logger.info(f"Demo user logged in successfully")
        
        return redirect(url_for('demo.demo_home'))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Demo login error: {e}")
        return render_template('login.html', 
                            error="Failed to create demo session. Please try again."), 500