"""Test and development routes"""
from flask import Blueprint, current_app, jsonify, render_template, session
from ..auth.decorators import login_required
import logging
import asyncio
from functools import wraps

test_bp = Blueprint('test', __name__)
logger = logging.getLogger(__name__)

def async_route(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return wrapper

@test_bp.route('/emails')
@login_required
@async_route
async def test_emails():
    try:
        analyzer = current_app.config['EMAIL_ANALYZER']
        emails = await analyzer.analyze_recent_emails(days_back=1)
        return render_template('email_summary.html', emails=emails)
    except Exception as e:
        logger.error(f"Email processing error: {e}")
        return {"error": str(e)}, 500

@test_bp.route('/connection')
@login_required
@async_route
async def test_connection():
    try:
        from app.email.core.email_connection import IMAPEmailClient
        
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
    try:
        from app.email.core.email_connection import IMAPEmailClient
        from app.email.core.email_parsing import EmailParser
        
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

@test_bp.route('/cache/flush')
@async_route
async def flush_cache():
    try:
        await current_app.pipeline.cache.clear_cache()
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
    

@test_bp.route('/cache/flush-all')
@async_route
async def flush_all_cache():
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