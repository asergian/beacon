"""Authentication decorators."""

from functools import wraps
from flask import session, redirect, url_for, abort
from ..models import User

def login_required(f):
    """Decorator to require login for routes.
    
    Checks if user is logged in by verifying session data.
    If not logged in, redirects to login page.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('auth.show_login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to require admin role for routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('auth.show_login'))
        
        user = User.query.get(session['user']['id'])
        if not user or not user.has_role('admin'):
            abort(403)  # Forbidden
            
        return f(*args, **kwargs)
    return decorated_function 