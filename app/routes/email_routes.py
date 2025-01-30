"""Core email functionality routes"""
from flask import Blueprint, current_app, render_template, jsonify, request, redirect, url_for, session
from ..auth.decorators import login_required
from ..email.pipeline.pipeline import AnalysisCommand
from ..email.models.analysis_settings import ProcessingConfig
from ..utils.logging_config import setup_logging
import logging
import asyncio
from functools import wraps

def async_route(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return wrapper

# Set up logger
logger = setup_logging()

try:
    email_bp = Blueprint('email', __name__)
except Exception as e:
    logger.error(f"Failed to initialize email blueprint: {str(e)}")
    raise

@email_bp.route('/')
@login_required
@async_route
async def home():
    """Home page that loads email UI without waiting for data."""
    return render_template('email_summary.html', emails=[])

@email_bp.route('/api/emails/metadata')
@login_required
@async_route
async def get_email_metadata():
    """Get basic email metadata without analysis."""
    try:
        raw_emails = await current_app.pipeline.connection.fetch_emails(days=1)
        basic_emails = []
        
        for email in raw_emails:
            parsed = current_app.pipeline.parser.extract_metadata(email)
            if parsed:
                basic_emails.append({
                    'id': parsed.id,
                    'subject': parsed.subject,
                    'sender': parsed.sender,
                    'date': parsed.date.isoformat() if parsed.date else None,
                })
        
        return jsonify({
            'status': 'success',
            'emails': basic_emails
        })
    except Exception as e:
        logger.error(f"Failed to fetch email metadata: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@email_bp.route('/api/emails/analysis')
@login_required
@async_route
async def get_email_analysis():
    """Get analyzed emails in batches."""
    try:
        command = AnalysisCommand(
            days_back=1,
            cache_duration_days=7,
            batch_size=10  # Process in small batches
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
        days = int(request.args.get('days', 1))
        batch_size = int(request.args.get('batch_size', 100))
        
        await current_app.pipeline.refresh_cache(days=days, batch_size=batch_size)
        
        return jsonify({
            'status': 'success',
            'message': f'Refreshed emails for the past {days} days'
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