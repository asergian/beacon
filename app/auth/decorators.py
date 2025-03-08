"""Authentication decorators for route protection.

This module provides decorators that can be applied to Flask routes
to enforce authentication requirements and role-based access control.
These decorators check the user's session and redirect to login or
abort with appropriate status codes when requirements are not met.
"""

from functools import wraps
from flask import session, redirect, url_for, abort
from app.models.user import User

def login_required(f):
    """Decorator to require login for routes.
    
    Verifies that a user is logged in by checking if user data exists in the
    session. If no user is logged in, redirects to the login page.
    
    Args:
        f: The Flask route function to be decorated.
        
    Returns:
        function: The decorated function with login verification.
        
    Example:
        @app.route('/protected')
        @login_required
        def protected_route():
            return "This page requires login"
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        """Inner function that checks if user is logged in.
        
        Args:
            *args: Variable length argument list passed to the original function.
            **kwargs: Arbitrary keyword arguments passed to the original function.
            
        Returns:
            The result of the original function if user is logged in,
            or a redirect to the login page if not.
        """
        if 'user' not in session:
            return redirect(url_for('auth.show_login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to require admin role for routes.
    
    Verifies that a user is logged in and has the 'admin' role.
    If no user is logged in, redirects to the login page.
    If the user lacks admin privileges, responds with 403 Forbidden.
    
    Args:
        f: The Flask route function to be decorated.
        
    Returns:
        function: The decorated function with admin verification.
        
    Raises:
        HTTPException: 403 Forbidden if user is not an admin.
        
    Example:
        @app.route('/admin-only')
        @admin_required
        def admin_route():
            return "This page requires admin privileges"
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        """Inner function that checks if user is logged in and has admin role.
        
        Args:
            *args: Variable length argument list passed to the original function.
            **kwargs: Arbitrary keyword arguments passed to the original function.
            
        Returns:
            The result of the original function if user is logged in and has admin role,
            a redirect to the login page if not logged in,
            or a 403 Forbidden response if user is not an admin.
        """
        if 'user' not in session:
            return redirect(url_for('auth.show_login'))
        
        user = User.query.get(session['user']['id'])
        if not user or not user.has_role('admin'):
            abort(403)  # Forbidden
            
        return f(*args, **kwargs)
    return decorated_function 