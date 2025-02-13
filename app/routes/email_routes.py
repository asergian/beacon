"""Email processing and viewing routes."""

from flask import Blueprint, current_app, render_template, jsonify, request, redirect, url_for, session, Response, stream_with_context
import logging
from ..auth.decorators import login_required
from ..email.models.analysis_command import AnalysisCommand
from ..models import log_activity
import asyncio
from functools import wraps
from ..models import User
import json
import time

def async_route(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(f(*args, **kwargs))
    return wrapper

# Set up logger
logger = logging.getLogger(__name__)
email_bp = Blueprint('email', __name__)

@email_bp.route('/')
@login_required
def home():
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

@email_bp.route('/stream')
def email_stream():
    def generate():
        for i in range(10):  # Simulating a stream
            yield f"data: Message {i}\n\n"
            time.sleep(1)  # Simulate processing delay

    response = Response(stream_with_context(generate()), content_type='text/event-stream')
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"  # Important for Nginx setups
    response.headers["Connection"] = "keep-alive"
    return response

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

@email_bp.route('/api/emails/stream')
@login_required
def stream_email_analysis():
    """Stream analyzed emails as Server-Sent Events."""
    
    def generate():
        loop = None
        try:
            # Send initial connection message
            yield 'event: connected\ndata: {"status": "connected"}\n\n'
            
            # Check user context
            if 'user' not in session:
                yield 'event: error\ndata: {"message": "No user found in session"}\n\n'
                return
                
            user_id = int(session['user'].get('id'))
            user_email = session['user'].get('email')
            if not user_email:
                yield 'event: error\ndata: {"message": "No user email found in session"}\n\n'
                return
            
            # Get user settings
            user = User.query.get(user_id)
            if not user:
                yield 'event: error\ndata: {"message": "User not found in database"}\n\n'
                return
                
            # Get user settings for email analysis
            cache_duration = user.get_setting('email_preferences.cache_duration_days', 7)
            days_back = user.get_setting('email_preferences.days_to_analyze', 1)
            
            command = AnalysisCommand(
                days_back=days_back,
                cache_duration_days=cache_duration,
                batch_size=5  # Process in smaller batches for streaming
            )
            
            # Create event loop for async operations
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            yield 'event: status\ndata: {"message": "Checking cache..."}\n\n'
            
            # Check cache first
            cached_emails = []
            if current_app.pipeline.cache:
                try:
                    loop.run_until_complete(current_app.pipeline.cache.set_user(user_email))
                    cached_emails = loop.run_until_complete(
                        current_app.pipeline.cache.get_recent(
                            command.cache_duration_days,
                            command.days_back
                        )
                    )
                    
                    if cached_emails:
                        yield f'event: cached\ndata: {json.dumps({"emails": [email.dict() for email in cached_emails]})}\n\n'
                        yield f'event: status\ndata: {{"message": "Loading {len(cached_emails)} emails from cache"}}\n\n'
                    else:
                        yield 'event: status\ndata: {"message": "No cached emails found"}\n\n'
                        
                except Exception as cache_error:
                    current_app.logger.error(f"Cache error: {cache_error}")
                    yield f'event: status\ndata: {{"message": "Cache check failed, proceeding with analysis..."}}\n\n'
            
            # Start email analysis
            yield 'event: status\ndata: {"message": "Starting email analysis..."}\n\n'
            
            try:
                # Get the email analysis generator
                analysis_gen = current_app.pipeline.get_analyzed_emails_stream(command)
                
                # Process each batch
                total_processed = 0
                total_to_process = None  # Initialize as None until we get initial stats
                
                while True:
                    try:
                        # Get next batch using the event loop
                        batch = loop.run_until_complete(analysis_gen.__anext__())
                        
                        if isinstance(batch, dict):
                            if 'initial_stats' in batch:
                                # Update total_to_process when we get initial stats
                                new_emails = batch['initial_stats'].get('new_emails', 0)
                                if new_emails > 0:
                                    yield f'event: status\ndata: {{"message": "Found {new_emails} new emails to process"}}\n\n'
                                total_to_process = new_emails
                                continue
                            elif 'stats' in batch:
                                # Final stats
                                yield f'event: stats\ndata: {json.dumps(batch)}\n\n'
                                break
                        else:
                            # Email batch
                            total_processed += len(batch)
                            
                            # Send batch data
                            yield f'event: batch\ndata: {json.dumps({"emails": [email.dict() for email in batch]})}\n\n'
                            
                            # Only show processing progress if we have new emails to process
                            if total_to_process and total_to_process > 0:
                                yield f'event: status\ndata: {{"message": "Processed {total_processed} of {total_to_process} emails"}}\n\n'
                            
                    except StopAsyncIteration:
                        break
                    except Exception as batch_error:
                        current_app.logger.error(f"Batch processing error: {batch_error}")
                        yield f'event: error\ndata: {{"message": "Error processing batch: {str(batch_error)}"}}\n\n'
                        break
                    
                # Only show completion message if we processed new emails
                if total_to_process and total_to_process > 0:
                    yield f'event: status\ndata: {{"message": "Analysis complete - {total_processed} emails processed"}}\n\n'
                
            except Exception as analysis_error:
                current_app.logger.error(f"Analysis error: {analysis_error}")
                yield f'event: error\ndata: {{"message": "Email analysis failed: {str(analysis_error)}"}}\n\n'
            
        except Exception as e:
            current_app.logger.error(f"Error in generator: {e}")
            yield f'event: error\ndata: {{"message": "Internal server error: {str(e)}"}}\n\n'
        finally:
            # Clean up resources
            try:
                if loop and hasattr(current_app.pipeline.connection, 'disconnect'):
                    loop.run_until_complete(current_app.pipeline.connection.disconnect())
            except Exception as disconnect_error:
                current_app.logger.warning(f"Failed to disconnect Gmail client: {disconnect_error}")
            
            if loop:
                loop.close()
            
            # Send a final event to ensure the client knows we're done
            yield 'event: status\ndata: {"message": "Connection closed"}\n\n'

    response = Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache, no-transform',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
            'Content-Type': 'text/event-stream; charset=utf-8'
        }
    )
    return response