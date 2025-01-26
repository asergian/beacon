"""Flask routes module for email processing functionality.

This module implements Flask blueprint patterns to handle email-related routes
and processing. It provides endpoints for viewing emails and email summaries.

Typical usage example:
    app = Flask(__name__)
    init_routes(app)
"""

from flask import Blueprint, current_app, render_template, jsonify
import asyncio
import logging
from .email_processor import EmailAnalyzer, TextAnalyzer

try:
    email_bp = Blueprint('email', __name__)
    logger = logging.getLogger(__name__)
except Exception as e:
    # Log error and re-raise since Blueprint creation is critical
    logging.error(f"Failed to initialize email blueprint: {str(e)}")
    raise

def init_routes(app):
    """Initializes Flask routes by registering the email blueprint.

    Args:
        app: Flask application instance to register blueprints with.
    """
    try:
        app.register_blueprint(email_bp)
        logger.info("Email blueprint registered successfully")
    except Exception as e:
        logger.error(f"Failed to register email blueprint: {str(e)}")
        raise

@email_bp.route('/')
def home():
    """Renders the home page.

    Returns:
        str: Rendered HTML template for the home page.
    """
    try:
        return render_template('home.html')
    except Exception as e:
        logger.error(f"Failed to render home template: {str(e)}")
        return {"error": "Failed to load home page"}, 500

@email_bp.route('/emails')
async def show_emails():
    """Processes and displays email summaries."""
    try:
        analyzer = current_app.config['EMAIL_ANALYZER']
        emails = await analyzer.analyze_recent_emails(days_back=1)
        return render_template('email_summary.html', emails=emails)
    except Exception as e:
        logger.error(f"Email processing error: {e}")
        return {"error": str(e)}, 500

@email_bp.route('/test-connection')
def test_email_connection():
    """Test endpoint to verify email connection and fetch emails directly.
    
    Returns:
        json: Connection status and email data if successful
    """
    try:
        from app.email_connection import IMAPEmailClient
        
        # Get email configuration
        email_config = {
            'server': current_app.config.get('IMAP_SERVER'),
            'email': current_app.config.get('EMAIL'),
            'password': current_app.config.get('IMAP_PASSWORD')
        }
        
        if not all(email_config.values()):
            return jsonify({
                "status": "error",
                "message": "Missing email configuration. Check IMAP_SERVER, EMAIL, and IMAP_PASSWORD settings."
            }), 500
            
        try:
            client = IMAPEmailClient(**email_config)
            emails = asyncio.run(client.fetch_emails(days=1))
            
            # Convert bytes to string for JSON serialization
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
            return jsonify({
                "status": "error",
                "message": str(e)
            }), 500
            
    except Exception as e:
        logger.error(f"Test connection failed: {e}")
        return jsonify({"error": "Connection test failed"}), 500

@email_bp.route('/test-parsing')
def test_email_parsing():
    """Test endpoint to verify email connection, fetch and parse emails."""
    try:
        from app.email_connection import IMAPEmailClient
        from app.email_parsing import EmailParser
        
        # Get email configuration
        email_config = {
            'server': current_app.config.get('IMAP_SERVER'),
            'email': current_app.config.get('EMAIL'),
            'password': current_app.config.get('IMAP_PASSWORD')
        }
        
        if not all(email_config.values()):
            return jsonify({
                "status": "error",
                "message": "Missing email configuration. Check IMAP_SERVER, EMAIL, and IMAP_PASSWORD settings."
            }), 500
            
        try:
            # Fetch emails
            client = IMAPEmailClient(**email_config)
            raw_emails = asyncio.run(client.fetch_emails(days=1))
            
            # Parse emails
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
                            'body': getattr(parsed_email, 'body', '')[:200],  # Limit body length
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
            return jsonify({
                "status": "error",
                "message": str(e)
            }), 500
            
    except Exception as e:
        logger.error(f"Test parsing failed: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@email_bp.route('/test-analysis')
async def test_fetch_parse_analyze():
    """Test route to fetch, parse emails, and apply the TextAnalyzer.

    Returns:
        json: Results of the text analysis on the fetched emails.
    """
    try:
        # Retrieve the email analyzer and text analyzer from the app config
        email_analyzer = current_app.config['EMAIL_ANALYZER']
        text_analyzer = email_analyzer.text_analyzer  # Access the TextAnalyzer from the EmailAnalyzer
        llm_analyzer = email_analyzer.llm_analyzer  # Access the LLMAnalyzer from the EmailAnalyzer
        
        logger.info("Starting to fetch emails...")
        
        # Fetch emails
        raw_emails = await email_analyzer.email_client.fetch_emails(days=1)
        logger.info(f"Fetched {len(raw_emails)} emails.")

        # Parse emails
        parsed_emails = []
        
        for raw_email in raw_emails:
            try:
                parsed_email = email_analyzer.parser.extract_metadata(raw_email)
                if parsed_email is not None:
                    parsed_emails.append({
                        'id': raw_email.get('id', 'unknown'),
                        'subject': getattr(parsed_email, 'subject', ''),
                        'sender': getattr(parsed_email, 'sender', ''),
                        'body': getattr(parsed_email, 'body', '')[:200],  # Limit body length
                        'date': parsed_email.date.isoformat() if getattr(parsed_email, 'date', None) else None,
                    })
                    logger.debug(f"Parsed email ID: {raw_email.get('id', 'unknown')}")
                else:
                    logger.warning(f"Parsed email returned None for email ID: {raw_email.get('id', 'unknown')}")
            except Exception as e:
                logger.warning(f"Error parsing email {raw_email.get('id', 'unknown')}: {str(e)}")
        
        logger.info(f"Total parsed emails: {len(parsed_emails)}")

        # Apply TextAnalyzer to parsed emails
        analysis_results = []
        
        for parsed_email in parsed_emails:
            nlp_results = text_analyzer.analyze(parsed_email.get('body', ''))  # Analyze the body of the parsed email
            llm_results = await llm_analyzer.analyze(parsed_email, nlp_results)  # Analyze with LLM using both parsed_email and nlp_results
            
            analysis_results.append({
                'id': parsed_email.get('id', 'unknown'),
                'analysis': nlp_results,
                'llm_analysis': llm_results  # Include LLM analysis results
            })
            logger.debug(f"Analysis result for email ID {parsed_email.get('id', 'unknown')}: {nlp_results}")

        return jsonify({
            "status": "success",
            "email_count": len(parsed_emails),
            "analysis_results": analysis_results
        })

    except Exception as e:
        logger.error(f"Test fetch, parse, and analyze failed: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500