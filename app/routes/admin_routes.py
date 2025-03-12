"""Admin-only routes for the Beacon application.

This module provides routes for administrative tasks such as cache management,
user administration, and system configuration. These routes are only accessible
to users with the admin role.

Typical usage example:
    app.register_blueprint(admin_bp, url_prefix='/admin')
"""
from flask import Blueprint, current_app, jsonify, session
from ..auth.decorators import admin_required
import logging
import asyncio
from functools import wraps

admin_bp = Blueprint('admin', __name__)
logger = logging.getLogger(__name__)

def async_route(f):
    """Decorator to handle asynchronous Flask routes.
    
    Wraps an async function so it can be used as a Flask route handler by
    running it with asyncio.run().
    
    Args:
        f: The async function to wrap.
        
    Returns:
        function: A wrapper function that runs the async function.
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        """Synchronous wrapper function that runs the async function.
        
        This function executes the decorated async function in a newly created
        event loop using asyncio.run().
        
        Args:
            *args: Variable length argument list passed to the original function.
            **kwargs: Arbitrary keyword arguments passed to the original function.
            
        Returns:
            The result of the async function execution.
        """
        return asyncio.run(f(*args, **kwargs))
    return wrapper

@admin_bp.route('/cache/flush')
@admin_required
@async_route
async def flush_cache():
    """Admin route for flushing the current user's cache.
    
    Clears the cache for the current session. Requires admin privileges.
    
    Returns:
        JSON response: Cache flush status and message.
        
    Raises:
        Exception: If cache flush fails, returns a 500 error with details.
    """
    try:
        if 'user' not in session or 'email' not in session['user']:
            return jsonify({
                'status': 'error',
                'message': 'No user found in session'
            }), 401
        await current_app.pipeline.cache.clear_cache(session['user']['email'])
        return jsonify({
            'status': 'success',
            'message': 'Cache successfully cleared'
        })
    except Exception as e:
        logger.error(f"Failed to clear cache: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to clear cache: {str(e)}'
        }), 500
    

@admin_bp.route('/cache/flush-all')
@admin_required
@async_route
async def flush_all_cache():
    """Admin route for flushing all caches.
    
    Clears all caches associated with the current user's email address.
    Requires admin privileges.
    
    Returns:
        JSON response: Cache flush status and message.
        
    Raises:
        Exception: If cache flush fails, returns a 500 error with details.
    """
    try:
        # Clear cache
        if current_app.pipeline.cache:
            if 'user' not in session or 'email' not in session['user']:
                return jsonify({
                    'status': 'error',
                    'message': 'No user found in session'
                }), 401
            await current_app.pipeline.cache.clear_all_cache(session['user']['email'])
        return jsonify({
            'status': 'success',
            'message': 'All caches successfully cleared'
        })
    except Exception as e:
        logger.error(f"Failed to clear all caches: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to clear all caches: {str(e)}'
        }), 500 