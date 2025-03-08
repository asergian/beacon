# Authentication Module

The Authentication module provides user authentication, authorization, and session management capabilities for the Beacon application.

## Overview

This module handles all aspects of user authentication and authorization, including login flows, OAuth integration, session management, and access control. It enables secure user authentication using both traditional username/password methods and OAuth-based authentication with providers like Google.

## Directory Structure

```
auth/
├── __init__.py        # Package exports and route registration
├── decorators.py      # Authentication and authorization decorators
├── oauth.py           # OAuth provider integration
├── routes.py          # Authentication-related routes
├── README.md          # This documentation
└── utils.py           # Authentication utilities
```

## Components

### Authentication Decorators
Provides decorators to protect routes and enforce authentication and authorization requirements. Includes `login_required` and `admin_required` decorators for access control.

### OAuth Integration
Handles OAuth authentication flows with providers like Google, managing token exchange, user profile retrieval, and session establishment.

### Authentication Routes
Implements routes for user login, logout, registration, and OAuth callback handling.

### Authentication Utilities
Provides helper functions for password hashing, token generation, session management, and other authentication-related operations.

## Usage Examples

```python
# Protecting a route with authentication
from app.auth.decorators import login_required

@app.route('/protected')
@login_required
def protected_route():
    return "This route requires authentication"

# Requiring admin privileges
from app.auth.decorators import admin_required

@app.route('/admin')
@admin_required
def admin_route():
    return "This route requires admin privileges"

# OAuth authentication
from app.auth.oauth import get_google_auth_url

@app.route('/login/google')
def google_login():
    auth_url = get_google_auth_url()
    return redirect(auth_url)
```

## Internal Design

The authentication module follows these design principles:
- Clear separation between authentication and authorization
- Secure handling of credentials and tokens
- Seamless integration with multiple authentication providers
- Proper session management with appropriate timeouts and security controls
- Decorator-based access control for easy application

## Dependencies

Internal:
- `app.models.user`: For user data management
- `app.utils.logging_setup`: For logging authentication events

External:
- `flask`: For request handling and sessions
- `requests`: For OAuth API communication
- `werkzeug.security`: For password hashing and verification
- `google-auth-oauthlib`: For Google OAuth integration

## Additional Resources

- [Flask-Login Documentation](https://flask-login.readthedocs.io/)
- [OAuth 2.0 Documentation](https://oauth.net/2/)
- [Google OAuth Documentation](https://developers.google.com/identity/protocols/oauth2) 