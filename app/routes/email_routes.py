"""Core email functionality routes"""
from flask import Blueprint, current_app, render_template, jsonify, request, redirect, url_for
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
    command = AnalysisCommand(
        days_back=1,
        cache_duration_days=7,
        priority_threshold=None,
        categories=None
    )
    result = await current_app.pipeline.get_analyzed_emails(command)
    return render_template('email_summary.html', emails=result.emails)

@email_bp.route('/emails')
@login_required
@async_route
async def get_emails():
    days = int(request.args.get('days', 0))
    priority = float(request.args.get('priority', ProcessingConfig.BASE_PRIORITY_SCORE))
    categories = request.args.getlist('category')
    batch_size = int(request.args.get('batch_size', 100))

    command = AnalysisCommand(
        days_back=days,
        batch_size=batch_size,
        priority_threshold=priority if priority > 0 else None,
        categories=categories if categories else None
    )

    result = await current_app.pipeline.get_analyzed_emails(command)
    
    if request.headers.get('Accept') == 'application/json':
        return jsonify({
            'emails': [email.dict() for email in result.emails],
            'stats': result.stats,
            'errors': result.errors
        })
    
    return render_template('email_summary.html', 
                         emails=result.emails,
                         stats=result.stats)

@email_bp.route('/emails/refresh', methods=['POST'])
@login_required
@async_route
async def refresh_emails():
    days = int(request.args.get('days', 1))
    batch_size = int(request.args.get('batch_size', 100))
    
    await current_app.pipeline.refresh_cache(days=days, batch_size=batch_size)
    
    return jsonify({
        'status': 'success',
        'message': f'Refreshed emails for the past {days} days'
    })