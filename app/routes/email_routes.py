"""Email processing and viewing routes."""

from flask import Blueprint, current_app, render_template, jsonify, request, redirect, url_for, session
import logging
from ..auth.decorators import login_required
from ..email.models.analysis_command import AnalysisCommand
from ..models import log_activity
import asyncio
from functools import wraps
from ..models import User

def async_route(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return wrapper

# Set up logger
logger = logging.getLogger(__name__)
email_bp = Blueprint('email', __name__)

@email_bp.route('/')
@login_required
@async_route
async def home():
    """Home page that loads email UI without waiting for data."""
    return render_template('email_summary.html', 
                         emails=[],
                         tiny_mce_api_key=current_app.config.get('TINYMCE_API_KEY', ''))

@email_bp.route('/api/user/settings')
@login_required
def get_user_settings():
    """Get user settings."""
    try:
        user = User.query.get(session['user']['id'])
        if not user:
            return jsonify({
                'status': 'error',
                'message': 'User not found'
            }), 404
            
        settings = user.get_all_settings()
        return jsonify({
            'status': 'success',
            'settings': settings
        })
    except Exception as e:
        logger.error(f"Failed to get user settings: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# Note: We previously had a /api/emails/metadata endpoint here for fetching basic email data
# It has been replaced by /api/emails/cached which serves analyzed emails from cache
# This provides a better UX by showing full email analysis while waiting for fresh data

@email_bp.route('/api/emails/cached')
@login_required
@async_route
async def get_cached_emails():
    """Get only cached emails without fetching from Gmail."""
    try:
        if not current_app.pipeline.cache:
            return jsonify({
                'status': 'error',
                'message': 'Cache not available'
            }), 404
            
        # Ensure user email is set in cache
        if 'user' not in session or 'email' not in session['user']:
            return jsonify({
                'status': 'error',
                'message': 'No user found in session'
            }), 401
            
        # Get user settings
        user = User.query.get(session['user']['id'])
        if not user:
            return jsonify({
                'status': 'error',
                'message': 'User not found'
            }), 404
            
        # Get settings
        days_back = user.get_setting('email_preferences.days_to_analyze', 1)
        cache_duration = user.get_setting('email_preferences.cache_duration_days', 7)
            
        # Create command with user settings
        command = AnalysisCommand(
            days_back=days_back,
            cache_duration_days=cache_duration
        )
            
        # Set user email in cache
        await current_app.pipeline.cache.set_user(session['user']['email'])
            
        # Get cached emails only using command
        cached_emails = await current_app.pipeline.cache.get_recent(command.cache_duration_days, command.days_back)
        
        return jsonify({
            'status': 'success',
            'emails': [email.dict() for email in cached_emails],
            'is_cached': True
        })
    except Exception as e:
        logger.error(f"Failed to fetch cached emails: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@email_bp.route('/api/emails/analysis')
@login_required
@async_route
async def get_email_analysis():
    """Get analyzed emails in batches."""
    try:
        # Get user settings
        user = User.query.get(session['user']['id'])
        if not user:
            return jsonify({
                'status': 'error',
                'message': 'User not found'
            }), 404
            
        # Get settings
        days_back = user.get_setting('email_preferences.days_to_analyze', 1)
        cache_duration = user.get_setting('email_preferences.cache_duration_days', 7)
        
        command = AnalysisCommand(
            days_back=days_back,
            cache_duration_days=cache_duration,
            batch_size=20  # Process in small batches
        )
        result = await current_app.pipeline.get_analyzed_emails(command)
        
        return jsonify({
            'status': 'success',
            'emails': [email.dict() for email in result.emails],
            'stats': result.stats
        })
    except Exception as e:
        logger.error(f"Failed to fetch email analysis: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# Deprecated routes below - will be removed in future versions
@email_bp.route('/emails')
@login_required
@async_route
async def get_emails():
    """Deprecated: Use /api/emails/analysis instead"""
    return redirect(url_for('email.get_email_analysis'))

@email_bp.route('/emails/refresh', methods=['POST'])
@login_required
@async_route
async def refresh_emails():
    """Refresh email cache"""
    try:
        # Get user settings
        user = User.query.get(session['user']['id'])
        if not user:
            return jsonify({
                'status': 'error',
                'message': 'User not found'
            }), 404
            
        # Get settings
        days_back = user.get_setting('email_preferences.days_to_analyze', 1)
        cache_duration = user.get_setting('email_preferences.cache_duration_days', 7)
        batch_size = int(request.args.get('batch_size', 100))
        
        # Create command with user settings
        command = AnalysisCommand(
            days_back=days_back,
            cache_duration_days=cache_duration,
            batch_size=batch_size
        )
        
        await current_app.pipeline.refresh_cache(days=command.days_back, batch_size=command.batch_size)
        
        return jsonify({
            'status': 'success',
            'message': f'Refreshed emails for the past {command.days_back} days'
        })
    except Exception as e:
        logger.error(f"Failed to refresh emails: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@email_bp.route('/api/user')
@login_required
def get_current_user():
    """Get current user ID from session."""
    try:
        if 'user' in session and 'email' in session['user']:
            return jsonify({
                'status': 'success',
                'user_id': session['user']['email']
            })
        return jsonify({
            'status': 'error',
            'message': 'No user found in session'
        }), 401
    except Exception as e:
        logger.error(f"Failed to get current user: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500