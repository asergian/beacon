"""Authentication utilities for Gmail API.

This module provides authentication-related functionality for interacting with
the Gmail API, including credential management and token verification.
"""

import logging
from typing import Dict
from flask import session
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as AuthRequest
from google.oauth2 import id_token

from .exceptions import GmailAPIError, AuthenticationError

logger = logging.getLogger(__name__)


def create_credentials(creds_dict: Dict) -> Credentials:
    """Create a Credentials object from session dictionary.

    Args:
        creds_dict: Dictionary containing OAuth credential information

    Returns:
        Google OAuth Credentials object

    Raises:
        ValueError: If essential credential information is missing
    """
    if not creds_dict.get('token') or not creds_dict.get('refresh_token'):
        raise ValueError("Invalid credentials: missing token or refresh token")
        
    return Credentials(
        token=creds_dict['token'],
        refresh_token=creds_dict['refresh_token'],
        token_uri=creds_dict['token_uri'],
        client_id=creds_dict['client_id'],
        client_secret=creds_dict['client_secret'],
        scopes=creds_dict['scopes']
    )


def update_session_credentials(credentials: Credentials, user_email: str):
    """Update session with current credential state.

    Args:
        credentials: The Google OAuth credentials object
        user_email: The email address of the authenticated user
    """
    if credentials and user_email:
        session['credentials'] = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes,
            'id_token': credentials.id_token
        }


async def ensure_valid_credentials(user_email: str) -> Credentials:
    """Ensure credentials are valid, refreshing if necessary.

    Args:
        user_email: The email address of the user to authenticate

    Returns:
        Valid Google OAuth Credentials object

    Raises:
        ValueError: If user_email is not provided
        GmailAPIError: If credential verification/refresh fails
    """
    try:
        if not user_email:
            raise ValueError("user_email is required")
            
        # Get credentials from session
        if 'credentials' not in session:
            raise GmailAPIError("No credentials found. Please authenticate first.")
        
        creds_dict = session['credentials']
        
        # Verify the token matches the requested user
        try:
            id_info = id_token.verify_oauth2_token(
                creds_dict.get('id_token'),
                AuthRequest(),
                creds_dict.get('client_id')
            )
            token_email = id_info.get('email', '').lower()
            
            # Verify credentials belong to the right user
            if token_email != user_email.lower():
                logger.error(f"Email mismatch - Token: {token_email}, Requested: {user_email}")
                raise GmailAPIError("Credentials don't match the requested user")
        except ValueError as e:
            logger.debug(f"Token needs refresh: {e}")
            # If token verification fails, try to refresh credentials
            if creds_dict.get('refresh_token'):
                logger.info("Refreshing expired token...")
                temp_creds = create_credentials(creds_dict)
                temp_creds.refresh(AuthRequest())
                creds_dict['token'] = temp_creds.token
                creds_dict['id_token'] = temp_creds.id_token
                session['credentials'] = creds_dict
                # Try verification again
                id_info = id_token.verify_oauth2_token(
                    temp_creds.id_token,
                    AuthRequest(),
                    creds_dict.get('client_id')
                )
                token_email = id_info.get('email', '').lower()
                if token_email != user_email.lower():
                    raise GmailAPIError("Credentials don't match the requested user")
                logger.info("Token refreshed successfully")
            else:
                raise GmailAPIError("Unable to verify user credentials - no refresh token available")
        
        # Verify all required fields are present
        required_fields = ['token', 'refresh_token', 'token_uri', 'client_id', 'client_secret', 'scopes']
        missing_fields = [field for field in required_fields if field not in creds_dict]
        
        if missing_fields:
            session.pop('credentials', None)
            raise GmailAPIError(f"Authentication incomplete - missing: {', '.join(missing_fields)}")
        
        credentials = create_credentials(creds_dict)
        
        # Check if credentials need refresh
        if not credentials.valid:
            if credentials.expired and credentials.refresh_token:
                logger.debug("Refreshing expired credentials")
                credentials.refresh(AuthRequest())
                update_session_credentials(credentials, user_email)
                logger.debug("Credentials refreshed successfully")
            else:
                raise GmailAPIError("Credentials invalid and cannot be refreshed")
                
        return credentials
        
    except Exception as e:
        logger.error(f"Credential error: {e}")
        session.pop('credentials', None)
        raise GmailAPIError(f"Failed to ensure valid credentials: {e}") 