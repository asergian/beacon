"""Test and development routes for the Beacon application.

This module provides routes for testing and debugging email functionality,
cache management, and other development features. These routes are only
available when the application is in debug mode.

Typical usage example:
    if app.debug:
        app.register_blueprint(test_bp, url_prefix='/test')
"""
from flask import Blueprint, current_app, jsonify, render_template, session
from ..auth.decorators import login_required
import logging
import asyncio
from functools import wraps

test_bp = Blueprint('test', __name__)
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

@test_bp.route('/emails')
@login_required
@async_route
async def test_emails():
    """Test endpoint for email processing.
    
    Fetches and analyzes recent emails for the current user with full processing.
    
    Returns:
        HTML: Rendered template with processed email data.
        
    Raises:
        Exception: If email processing fails, returns a 500 error with the error message.
    """
    try:
        from app.email.pipeline.orchestrator import AnalysisCommand
        
        analyzer = current_app.config['EMAIL_ANALYZER']
        command = AnalysisCommand(days_back=1, cache_duration_days=7)
        emails = await analyzer.analyze_recent_emails(command=command)
        return render_template('email_summary.html', emails=emails)
    except Exception as e:
        logger.error(f"Email processing error: {e}")
        return {"error": str(e)}, 500

@test_bp.route('/connection')
@login_required
@async_route
async def test_connection():
    """Test route for verifying email server connection.
    
    Attempts to connect to the configured IMAP server and fetch recent emails
    to verify that the connection is working correctly.
    
    Returns:
        JSON response: Connection status, email count, and fetched emails.
        
    Raises:
        Exception: If connection test fails, returns a 500 error with details.
    """
    try:
        from app.email.clients.imap.client import IMAPEmailClient
        
        email_config = {
            'server': current_app.config.get('IMAP_SERVER'),
            'email': current_app.config.get('EMAIL'),
            'password': current_app.config.get('IMAP_PASSWORD')
        }
        
        if not all(email_config.values()):
            return jsonify({
                "status": "error",
                "message": "Missing email configuration."
            }), 500
            
        client = IMAPEmailClient(**email_config)
        emails = await client.fetch_emails(days=1)
        
        serializable_emails = []
        for email in emails:
            serializable_emails.append({
                'id': email['id'],
                'raw_message': email['raw_message'].decode('utf-8', errors='replace')
            })
        
        return jsonify({
            "status": "success",
            "connection": "established",
            "email_count": len(emails),
            "emails": serializable_emails
        })
            
    except Exception as e:
        logger.error(f"Test connection failed: {e}")
        return jsonify({"error": "Connection test failed"}), 500

@test_bp.route('/parsing')
@login_required
def test_parsing():
    """Test route for email parsing functionality.
    
    Fetches recent emails and attempts to parse them using the EmailParser,
    returning the parsing results and statistics.
    
    Returns:
        JSON response: Parsing status, email counts, and parsed email data.
        
    Raises:
        Exception: If parsing test fails, returns a 500 error with details.
    """
    try:
        from app.email.clients.imap.client import IMAPEmailClient
        from app.email.parsing.parser import EmailParser
        
        email_config = {
            'server': current_app.config.get('IMAP_SERVER'),
            'email': current_app.config.get('EMAIL'),
            'password': current_app.config.get('IMAP_PASSWORD')
        }
        
        if not all(email_config.values()):
            return jsonify({
                "status": "error",
                "message": "Missing email configuration."
            }), 500
            
        client = IMAPEmailClient(**email_config)
        raw_emails = asyncio.run(client.fetch_emails(days=1))
        
        parser = EmailParser()
        parsed_emails = []
        skipped_count = 0
        
        for email in raw_emails:
            try:
                parsed_email = parser.extract_metadata(email)
                if parsed_email is not None:
                    parsed_emails.append({
                        'id': email.get('id', 'unknown'),
                        'subject': getattr(parsed_email, 'subject', ''),
                        'sender': getattr(parsed_email, 'sender', ''),
                        'body': getattr(parsed_email, 'body', '')[:200],
                        'date': parsed_email.date.isoformat() if getattr(parsed_email, 'date', None) else None,
                    })
                else:
                    skipped_count += 1
                    logger.warning(f"Skipped email {email.get('id', 'unknown')} - parsing returned None")
            except Exception as e:
                skipped_count += 1
                logger.warning(f"Error processing email {email.get('id', 'unknown')}: {str(e)}")
                continue
        
        return jsonify({
            "status": "success",
            "connection": "established",
            "email_count": len(parsed_emails),
            "skipped_count": skipped_count,
            "parsed_emails": parsed_emails
        })
            
    except Exception as e:
        logger.error(f"Test parsing failed: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@test_bp.route('/analysis')
@login_required
@async_route
async def test_fetch_parse_analyze():
    """Test route for the complete email analysis pipeline.
    
    Tests the full email processing pipeline including fetching, parsing, 
    and analyzing emails using both NLP and LLM analyzers.
    
    Returns:
        JSON response: Analysis status, email count, and analysis results.
        
    Raises:
        Exception: If analysis fails, returns a 500 error with details.
    """
    try:
        email_analyzer = current_app.config['EMAIL_ANALYZER']
        text_analyzer = email_analyzer.text_analyzer
        llm_analyzer = email_analyzer.llm_analyzer
        
        logger.info("Starting to fetch emails...")
        raw_emails = await email_analyzer.email_client.fetch_emails(days=1)
        logger.info(f"Fetched {len(raw_emails)} emails.")

        parsed_emails = []
        for raw_email in raw_emails:
            try:
                parsed_email = email_analyzer.parser.extract_metadata(raw_email)
                if parsed_email is not None:
                    parsed_emails.append(parsed_email)
                    logger.debug(f"Parsed email ID: {raw_email.get('id', 'unknown')}")
                else:
                    logger.warning(f"Parsed email returned None for email ID: {raw_email.get('id', 'unknown')}")
            except Exception as e:
                logger.warning(f"Error parsing email {raw_email.get('id', 'unknown')}: {str(e)}")
        
        logger.info(f"Total parsed emails: {len(parsed_emails)}")

        analysis_results = []
        for parsed_email in parsed_emails:
            nlp_results = text_analyzer.analyze(parsed_email.body)
            llm_results = await llm_analyzer.analyze(parsed_email, nlp_results)
            
            analysis_results.append({
                'id': parsed_email.id,
                'analysis': nlp_results,
                'llm_analysis': llm_results
            })
            logger.debug(f"Analysis result for email ID {parsed_email.id}: {nlp_results}")

        return jsonify({
            "status": "success",
            "email_count": len(parsed_emails),
            "analysis_results": analysis_results
        })

    except Exception as e:
        logger.error(f"Test fetch, parse, and analyze failed: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Cache flush routes have been moved to admin_routes.py 