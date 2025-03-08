"""Demo routes for the Beacon application.

This module provides routes for the demo mode of the Beacon application,
allowing users to explore the app's features with pre-generated sample data.

Routes:
    /: Demo home page
    /api/emails/analysis: Get analyzed demo emails
    /api/emails/stream: Stream email analysis for demo mode
    /exit: Exit demo mode
"""

import json
import time
import logging
import random
from datetime import datetime, timedelta
from typing import Generator
from flask import (
    jsonify, render_template, session, redirect,
    url_for, Response, stream_with_context
)
# Replace Flask-Login imports with our custom decorator
# from flask_login import login_required, current_user
from app.auth.decorators import login_required

from .data import get_demo_email_bodies, generate_demo_metadata
from .analysis import demo_analysis, load_analysis_cache
from app.models.user import User
from . import demo_bp  # Import the blueprint from __init__.py

# Set up logger
logger = logging.getLogger(__name__)

def get_demo_emails():
    """Generate demo email data.
    
    Creates a set of sample emails with content and metadata for demonstration
    purposes. Includes AI analysis data for each email if analysis cache is available.
    
    Returns:
        List[Dict[str, Any]]: A list of dictionaries containing demo email data with analysis.
    """
    logger.info("Generating demo emails...")
    now = datetime.utcnow()
    
    # Helper function to generate random past date within a range
    def random_past_date(min_days: int, max_days: int) -> datetime:
        """Generate a random date in the past within the specified range.
        
        Args:
            min_days: Minimum number of days in the past
            max_days: Maximum number of days in the past
            
        Returns:
            datetime: A random datetime between min_days and max_days ago
        """
        days_ago = random.randint(min_days, max_days)
        return now - timedelta(days=days_ago)
    
    # Get email bodies and metadata
    email_bodies = get_demo_email_bodies()
    email_metadata = generate_demo_metadata()
    
    # Create email objects
    emails = []
    for email_id, body in email_bodies.items():
        metadata = email_metadata.get(email_id, {})
        
        # Get a date - either from metadata or generate a random one
        email_date = metadata.get('date', random_past_date(1, 30))
        # Convert datetime to ISO format string to make it JSON serializable
        email_date_str = email_date.isoformat()
        
        # Create base email object
        email = {
            'id': email_id,
            'thread_id': f"thread_{email_id}",
            'message_id': f"<{email_id}.demo@example.com>",
            'date': email_date_str,  # Use the string version
            'sender': metadata.get('sender', 'Demo Sender <demo@example.com>'),
            'recipient': metadata.get('recipient', 'Demo User <demo@example.com>'),
            'subject': metadata.get('subject', f'Demo Email {email_id}'),
            'body': body,
            'is_unread': metadata.get('is_unread', True),
            'is_important': False,
            'labels': ['INBOX'],
            
            # These will be populated by analysis application
            'summary': '',
            'key_phrases': [],
            'sentiment_indicators': {'positive': [], 'negative': [], 'neutral': []},
            'priority_level': 'MEDIUM',
            'priority_score': 50,
            'action_items': [],
            'category': 'Uncategorized',
            'needs_action': False
        }
        
        emails.append(email)
    
    # Sort emails by date, newest first
    emails.sort(key=lambda x: x['date'], reverse=True)
    
    return emails


@demo_bp.route('/')
@login_required
def demo_home():
    """Demo mode home page.
    
    Sets the demo mode flag in the user's session and renders the
    email summary template with demo mode enabled.
    
    Returns:
        Response: Rendered email summary template with demo mode flag.
    """
    # Set the demo flag in the session
    logger.info("Demo home route accessed")
    if 'user' in session:
        if not isinstance(session['user'], dict):
            session['user'] = {}
        session['user']['is_demo'] = True
    
    # Load the demo analysis cache if not already loaded
    if demo_analysis and not demo_analysis.analysis_cache:
        try:
            load_analysis_cache()
            logger.info("Demo analysis cache loaded")
        except Exception as e:
            logger.warning(f"Failed to load demo analysis cache: {e}")
        
    return render_template('email_summary.html', emails=[], demo_mode=True)


@demo_bp.route('/api/emails/stream')
@login_required
def stream_email_analysis():
    """Stream email analysis for demo mode.
    
    Creates a server-sent events (SSE) stream that simulates the real-time
    analysis of emails, showing the progress of email processing.
    
    Returns:
        Response: SSE stream with demo email analysis updates.
    """
    logger.info("Starting demo analysis stream")
    
    def generate() -> Generator[str, None, None]:
        """Generate server-sent events for demo email analysis.
        
        Yields:
            str: SSE-formatted string with demo analysis updates.
        """
        try:
            # Send initial connection message
            yield "event: connected\ndata: {\"status\": \"connected\"}\n\n"
            
            # Send initial status
            yield "event: status\ndata: {\"message\": \"Loading demo data...\"}\n\n"
            time.sleep(0.25)
            
            # Get user settings and demo emails
            user = User.query.get(session['user']['id'])
            if not user:
                yield "event: error\ndata: {\"message\": \"User not found\"}\n\n"
                return
            
            # Get all demo emails
            demo_emails = get_demo_emails()
            total_emails = len(demo_emails)
            
            # Get user settings
            settings = user.get_all_settings()
            
            # Check if AI features are enabled
            ai_enabled = settings.get('ai_features', {}).get('enabled', True)
            
            # Get model type and context length settings
            model_type = str(settings.get('ai_features', {}).get('model_type', 'gpt-4o-mini')).lower()
            context_length = str(settings.get('ai_features', {}).get('context_length', '1000'))
            
            # Send initial stats
            initial_stats = {
                "total_fetched": total_emails,
                "new_emails": total_emails,
                "cached": 0
            }
            yield f"event: initial_stats\ndata: {json.dumps(initial_stats)}\n\n"
            
            # Process emails in batches of 5
            processed = 0
            batch_size = 5
            
            for i in range(0, total_emails, batch_size):
                batch = demo_emails[i:i+batch_size]
                
                # Update progress
                batch_start = i + 1
                batch_end = min(i + batch_size, total_emails)
                progress_pct = int((processed / total_emails) * 100)
                
                # Send progress update
                progress_data = {
                    "message": f"Processing emails {batch_start}-{batch_end} of {total_emails}...",
                    "count": processed,
                    "total": total_emails
                }
                yield f"event: status\ndata: {json.dumps(progress_data)}\n\n"
                
                # Process each email in the batch
                batch_results = []
                for email in batch:
                    if not ai_enabled:
                        # If AI is disabled, remove AI-generated fields
                        email.pop('summary', None)
                        email.pop('priority', None)
                        email.pop('priority_level', None)
                        email.pop('category', None)
                        email.pop('custom_categories', None)
                        email.pop('entities', None)
                        email.pop('key_phrases', None)
                        email.pop('sentiment_indicators', None)
                        email.pop('needs_action', None)
                        email.pop('action_items', None)
                    else:
                        # Apply pre-generated analysis based on model and context length
                        email = demo_analysis.apply_analysis(email, model_type, context_length)
                    
                    batch_results.append(email)
                    processed += 1
                
                # Simulate batch processing time
                time.sleep(0.5)
                
                # Send batch results
                batch_data = {
                    "emails": batch_results,
                    "batch_size": len(batch_results),
                    "total_processed": processed,
                    "progress_pct": int((processed / total_emails) * 100)
                }
                yield f"event: batch\ndata: {json.dumps(batch_data)}\n\n"
            
            # Calculate stats from demo emails
            stats = {
                'total_analyzed': len(demo_emails),
                'processed': len(demo_emails),
                'cached': 0,
                'total': len(demo_emails),
                'categories': {},
                'sentiment_distribution': {},
                'priority_levels': {},
                'action_required': 0,
                'processing_time_ms': random.randint(800, 1500)  # Simulate processing time
            }
            
            for email in demo_emails:
                # Category distribution
                category = email.get('category', 'Uncategorized')
                stats['categories'][category] = stats['categories'].get(category, 0) + 1
                
                # Priority distribution
                priority = email.get('priority_level', 'MEDIUM')
                stats['priority_levels'][priority] = stats['priority_levels'].get(priority, 0) + 1
                
                # Action items
                if email.get('needs_action', False):
                    stats['action_required'] += 1
                
                # Sentiment distribution
                sentiment = 'neutral'
                if email.get('sentiment_indicators'):
                    pos = len(email['sentiment_indicators'].get('positive', []))
                    neg = len(email['sentiment_indicators'].get('negative', []))
                    if pos > neg:
                        sentiment = 'positive'
                    elif neg > pos:
                        sentiment = 'negative'
                stats['sentiment_distribution'][sentiment] = stats['sentiment_distribution'].get(sentiment, 0) + 1
            
            # Send stats
            yield f"event: stats\ndata: {json.dumps(stats)}\n\n"
            
            # Send cached data (all processed emails)
            # cached_data = {
            #     "emails": demo_emails
            # }
            # yield f"event: cached\ndata: {json.dumps(cached_data)}\n\n"
            
            # Send completion notification
            completion_data = {
                "message": "Email analysis complete!",
                "total": total_emails,
                "processed": processed
            }
            yield f"event: complete\ndata: {json.dumps(completion_data)}\n\n"
            
            # Send close event
            yield "event: close\ndata: {\"message\": \"Connection closed\"}\n\n"
            
            logger.info("Demo email stream completed")
            
        except Exception as e:
            logger.error(f"Error in demo stream: {e}")
            yield f"event: error\ndata: {{\"message\": \"Error: {str(e)}\"}}\n\n"
    
    response = Response(
        stream_with_context(generate()),
        mimetype='text/event-stream'
    )
    response.headers['Cache-Control'] = 'no-cache, no-transform'
    response.headers['Connection'] = 'keep-alive'
    response.headers['X-Accel-Buffering'] = 'no'
    response.headers['Content-Type'] = 'text/event-stream; charset=utf-8'

    return response


@demo_bp.route('/exit')
@login_required
def exit_demo():
    """Exit demo mode.
    
    Clears the demo flag from the user's session and redirects
    to the authentication login page.
    
    Returns:
        Response: Redirect to the login page.
    """
    # Clear the demo flag and redirect to login
    if 'user' in session and isinstance(session['user'], dict):
        session['user']['is_demo'] = False
    
    return redirect(url_for('auth.logout')) 