"""Email processing and viewing routes.

This module provides routes for processing, analyzing, viewing, and 
sending emails. It includes functionality for fetching and analyzing emails,
streaming analysis results, and sending email responses.

Typical usage example:
    app.register_blueprint(email_bp, url_prefix='/email')
"""

from flask import Blueprint, current_app, render_template, jsonify, request, session, Response, stream_with_context, redirect, url_for
import logging
from ..auth.decorators import login_required
from ..email.models.analysis_command import AnalysisCommand
import asyncio
from app.models.user import User
from app.models.activity import log_activity
import json
import time
from datetime import datetime
import random
from ..utils.memory_profiling import log_memory_cleanup
import gc

# Set up logger
logger = logging.getLogger(__name__)
email_bp = Blueprint('email', __name__)

@email_bp.route('/')
@login_required
def home():
    """Email home page route.
    
    Renders the email summary page. For demo users, redirects to the demo home.
    
    Returns:
        Flask response: Rendered email summary template or redirect response.
    """
    # Check if user is in demo mode and redirect to demo home
    if session.get('user', {}).get('is_demo', False):
        logger.info("Redirecting demo user from email.home to demo.home")
        return redirect(url_for('demo.demo_home'))
        
    return render_template('email_summary.html', emails=[])

@email_bp.route('/api/emails/analysis')
@login_required
async def get_email_analysis():
    """API endpoint for getting analyzed emails.
    
    Fetches and analyzes emails based on user settings. For demo users,
    redirects to the demo analysis endpoint.
    
    Returns:
        JSON response: Analysis results including emails and statistics.
        
    Raises:
        Exception: If email analysis fails, returns a 500 error with details.
    """
    # Check if user is in demo mode and redirect to demo endpoint
    if session.get('user', {}).get('is_demo', False):
        logger.info("Redirecting demo user from email analysis to demo analysis")
        return redirect(url_for('demo.get_email_analysis'))
        
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
        
        # Ensure values are the correct type to prevent conversion errors
        try:
            # Force convert to integers
            days_back = int(days_back)
            cache_duration = int(cache_duration)
            logger.debug(f"Email API using days_back={days_back}, cache_duration={cache_duration}")
        except (ValueError, TypeError) as e:
            error_msg = f"Invalid settings format: {e}"
            logger.error(error_msg)
            return jsonify({
                'status': 'error',
                'message': error_msg
            }), 400
        
        command = AnalysisCommand(
            days_back=days_back,
            cache_duration_days=cache_duration,
            batch_size=20  # Process in small batches
        )
        result = await current_app.pipeline.get_analyzed_emails(command)
        
        # Force memory release after processing
        log_memory_cleanup(logger, "API Email Analysis Complete")
        
        return jsonify({
            'status': 'success',
            'emails': [email.dict() for email in result.emails],
            'stats': result.stats
        })
    except Exception as e:
        logger.error(f"Failed to fetch email analysis: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@email_bp.route('/api/emails/stream')
@login_required
def stream_email_analysis():
    """Stream analyzed emails as Server-Sent Events.
    
    Creates a streaming response that sends email analysis results as they
    become available. Handles cleanup of resources when the stream ends.
    
    Returns:
        Flask response: Streaming response with email analysis events.
    """
    
    # Check if user is in demo mode and redirect to demo stream
    if session.get('user', {}).get('is_demo', False):
        logger.info("Redirecting demo user from email stream to demo stream")
        return redirect(url_for('demo.stream_email_analysis'))
    
    def generate():
        """Generator function for streaming email analysis results.
        
        Yields:
            str: Server-Sent Event formatted string containing analysis data.
        """
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
            
            # Ensure values are the correct type to prevent conversion errors
            try:
                # Force convert to integers
                days_back = int(days_back)
                cache_duration = int(cache_duration)
                logger.debug(f"Email stream using days_back={days_back}, cache_duration={cache_duration}")
            except (ValueError, TypeError) as e:
                error_msg = f"Invalid settings format: {e}"
                logger.error(error_msg)
                yield f'event: error\ndata: {{"message": "{error_msg}"}}\n\n'
                return
            
            command = AnalysisCommand(
                days_back=days_back,
                cache_duration_days=cache_duration,
                batch_size=5  # Process in smaller batches for streaming
            )
            
            # Create event loop for async operations
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # Get the email analysis generator
                analysis_gen = current_app.pipeline.get_analyzed_emails_stream(command)
                
                # Process all yields from the generator
                while True:
                    try:
                        result = loop.run_until_complete(analysis_gen.__anext__())
                        
                        # Handle different message types
                        if isinstance(result, dict):
                            msg_type = result.get('type')
                            msg_data = result.get('data', {})
                            
                            if msg_type == 'status':
                                yield f'event: status\ndata: {json.dumps(msg_data)}\n\n'
                            elif msg_type == 'cached':
                                yield f'event: cached\ndata: {json.dumps(msg_data)}\n\n'
                            elif msg_type == 'batch':
                                yield f'event: batch\ndata: {json.dumps(msg_data)}\n\n'
                            elif msg_type == 'initial_stats':
                                yield f'event: initial_stats\ndata: {json.dumps(msg_data)}\n\n'
                            elif msg_type == 'stats':
                                yield f'event: stats\ndata: {json.dumps(msg_data)}\n\n'
                                yield 'event: close\ndata: {"message": "Processing complete"}\n\n'
                                break
                            elif msg_type == 'error':
                                yield f'event: error\ndata: {json.dumps(msg_data)}\n\n'
                                break
                            
                    except StopAsyncIteration:
                        break
                    except Exception as batch_error:
                        current_app.logger.error(f"Batch processing error: {batch_error}")
                        yield f'event: error\ndata: {{"message": "Error processing batch: {str(batch_error)}"}}\n\n'
                        break
                
            except Exception as analysis_error:
                current_app.logger.error(f"Analysis error: {analysis_error}")
                yield f'event: error\ndata: {{"message": "Email analysis failed: {str(analysis_error)}"}}\n\n'
            
        except Exception as e:
            current_app.logger.error(f"Error in generator: {e}")
            yield f'event: error\ndata: {{"message": "Internal server error: {str(e)}"}}\n\n'
        finally:
            # Clean up resources - ensure all async clients are properly closed
            # This is crucial to prevent memory leaks in streaming responses
            try:
                if loop:
                    try:
                        # First ensure the pipeline connection is closed
                        if hasattr(current_app.pipeline.connection, 'disconnect'):
                            loop.run_until_complete(current_app.pipeline.connection.disconnect())
                        
                        # Ensure any OpenAI client connections are properly closed
                        # Get the OpenAI client and close it
                        if hasattr(current_app, 'get_openai_client'):
                            openai_client = current_app.get_openai_client()
                            if openai_client and hasattr(openai_client, 'close'):
                                loop.run_until_complete(openai_client.close())
                            elif openai_client and hasattr(openai_client.http_client, 'aclose'):
                                # If the client has an internal httpx client, close that too
                                loop.run_until_complete(openai_client.http_client.aclose()) 
                        
                        # Run a final garbage collection to clean up any remaining resources
                        gc.collect()
                    except Exception as cleanup_error:
                        current_app.logger.warning(f"Error during async resource cleanup: {cleanup_error}")
            except Exception as disconnect_error:
                current_app.logger.warning(f"Failed to disconnect clients: {disconnect_error}")
            
            # Force memory release before closing connection
            try:
                log_memory_cleanup(logger, "Stream Complete")
            except Exception as memory_error:
                logger.error(f"Error during memory cleanup: {memory_error}")
            
            # Now safe to close the loop since all connections have been properly closed
            if loop:
                # Run pending callbacks one more time to ensure everything is properly cleaned up
                try:
                    loop.run_until_complete(asyncio.sleep(0.1))
                except:
                    pass
                finally:
                    loop.close()
            
            # Send a final event to ensure the client knows we're done
            yield 'event: close\ndata: {"message": "Connection closed"}\n\n'
    
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

# Helper function to run async code from a synchronous function
def run_async(coroutine):
    """Run an async function from a synchronous function.
    
    Creates a new event loop to run the coroutine and returns the result.
    
    Args:
        coroutine: The async coroutine to run.
        
    Returns:
        The result of the coroutine.
        
    Raises:
        Exception: If there's an error running the coroutine, the error is logged and re-raised.
    """
    try:
        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(coroutine)
        loop.close()
        return result
    except Exception as e:
        logger.error(f"Error running async code: {e}")
        raise

@email_bp.route('/api/emails/send_email', methods=['POST'])
@login_required
def send_email():
    """API endpoint to send an email response.
    
    Processes the email data from the request and sends it using either
    the Gmail API (if connected) or SMTP. Logs the activity upon success.
    
    Returns:
        JSON response: Success status and message.
        
    Raises:
        Exception: If there's an error sending the email, returns a 500 error with details.
    """
    try:
        # Log the request details
        logger.debug(f"Request to send_email: {request.path}, method: {request.method}")
        logger.debug(f"Request headers: {dict(request.headers)}")
        
        # Get data from request
        data = request.json
        to = data.get('to')
        subject = data.get('subject')
        content = data.get('content')
        cc = data.get('cc')
        original_email_id = data.get('original_email_id')
        
        # Validate required fields
        if not to or not subject or not content:
            return jsonify({
                'success': False,
                'message': 'Missing required fields'
            }), 400
        
        # Log the email sending attempt
        logger.info(f"Sending email to: {to}, subject: {subject}")
        
        # Process CC recipients if provided
        cc_list = None
        if cc:
            cc_list = [email.strip() for email in cc.split(',') if email.strip()]
        
        # Check if user is authenticated with Gmail
        user_email = None
        send_via_gmail = False
        gmail_client = None
        
        if 'user' in session and 'email' in session['user']:
            user_email = session['user']['email']
            
            # Check if Gmail credentials are available
            if 'credentials' in session:
                send_via_gmail = True
                
                # Initialize Gmail client
                try:
                    from app.email.clients.gmail.client_subprocess import GmailClientSubprocess
                    gmail_client = GmailClientSubprocess()
                    # Connect to Gmail API using our async runner
                    run_async(gmail_client.connect(user_email))
                    logger.debug(f"Will send email via Gmail API as {user_email}")
                except Exception as e:
                    import traceback
                    logger.error(f"Failed to initialize Gmail client: {e}")
                    logger.error(f"Gmail client initialization traceback: {traceback.format_exc()}")
                    send_via_gmail = False
        
        success = False
        
        if send_via_gmail and gmail_client:
            try:
                # Send email via Gmail API using our async runner
                result = run_async(gmail_client.send_email(
                    to=to,
                    subject=subject,
                    content=content,
                    cc=cc_list,
                    html_content=content,  # Use the same content for HTML (it's from CKEditor)
                    user_email=user_email
                ))
                
                # Log detailed information about the result
                logger.debug(f"Gmail API send result: {result}")
                
                # If we get here, email was sent successfully - but double check the result
                if isinstance(result, dict) and result.get('success', False):
                    success = True
                    logger.info(f"Email sent successfully via Gmail API to {to}\n")
                    if 'message_id' in result:
                        logger.debug(f"Message ID: {result['message_id']}")
                        logger.debug(f"Thread ID: {result.get('thread_id')}")
                        logger.debug(f"Label IDs: {result.get('label_ids', [])}")
                        
                        # Check if the message was properly labeled as SENT
                        if 'label_ids' in result and 'SENT' not in result['label_ids']:
                            logger.warning(f"Warning: Message was not automatically labeled as SENT")
                else:
                    logger.error(f"Invalid response from Gmail API: {result}")
                    success = False
                    
            except Exception as e:
                import traceback
                logger.error(f"Failed to send email via Gmail API: {e}")
                logger.error(f"Gmail API traceback: {traceback.format_exc()}")
                # Fall back to SMTP if Gmail API fails
                send_via_gmail = False
                success = False
        
        # Fall back to SMTP if not using Gmail or if Gmail API failed
        if not send_via_gmail:
            # Initialize email sender with SMTP configuration
            email_config = {
                'server': current_app.config.get('SMTP_SERVER'),
                'email': current_app.config.get('SMTP_EMAIL'),
                'password': current_app.config.get('SMTP_PASSWORD'),
                'port': current_app.config.get('SMTP_PORT'),
                'use_tls': current_app.config.get('SMTP_USE_TLS')
            }
            
            # Log the SMTP configuration (without sensitive info)
            logger.info(f"SMTP configuration: server={email_config['server']}, email={email_config['email']}, port={email_config['port']}, use_tls={email_config['use_tls']}")
            
            # Check if email configuration is complete
            if not all([email_config['server'], email_config['email'], email_config['password']]):
                missing_fields = []
                if not email_config['server']:
                    missing_fields.append('SMTP_SERVER')
                if not email_config['email']:
                    missing_fields.append('SMTP_EMAIL')
                if not email_config['password']:
                    missing_fields.append('SMTP_PASSWORD')
                    
                logger.error(f"Missing SMTP configuration: {', '.join(missing_fields)}")
                
                # Check if fallbacks are configured correctly
                logger.error(f"Checking fallbacks - SMTP_EMAIL fallback to EMAIL: {current_app.config.get('EMAIL')}")
                logger.error(f"Checking fallbacks - SMTP_PASSWORD fallback to IMAP_PASSWORD: {current_app.config.get('IMAP_PASSWORD') is not None}")
                
                return jsonify({
                    'success': False,
                    'message': f'Email service not configured: missing {", ".join(missing_fields)}'
                }), 500
            
            try:
                # Create email sender and send the email
                from app.email.core.email_sender import EmailSender, EmailSendingError
                sender = EmailSender(**email_config)
                
                # Set reply-to as the user's email if available
                reply_to = user_email if user_email else None
                
                # Run the async send_email method using our async runner
                success = run_async(sender.send_email(
                    to=to,
                    subject=subject,
                    content=content,
                    cc=cc_list,
                    html_content=content,  # Use the same content for HTML (it's from CKEditor)
                    reply_to=reply_to
                ))
                
                if not success:
                    raise EmailSendingError("Failed to send email")
                    
            except EmailSendingError as e:
                import traceback
                logger.error(f"Failed to send email via SMTP: {str(e)}")
                logger.error(f"SMTP traceback: {traceback.format_exc()}")
                return jsonify({
                    'success': False,
                    'message': f'Failed to send email: {str(e)}'
                }), 500
        
        # # If this is a response to an existing email, update its status.
        # if original_email_id:
        #     # In a real app, you would update the database
        #     logger.debug(f"Marking email {original_email_id} as responded")
        
        # Log user activity
        if 'user' in session and 'id' in session['user']:
            user_id = session['user']['id']
            try:
                # Direct call to log_activity
                log_activity(
                    user_id=user_id,
                    activity_type='email_sent',
                    description="Email sent",
                    metadata={
                        'to': to,
                        'subject': subject,
                        'original_email_id': original_email_id,
                        'sent_via': 'gmail_api' if send_via_gmail else 'smtp'
                    }
                )
            except Exception as log_error:
                logger.error(f"Failed to log activity: {log_error}")
                # Don't fail the request if logging fails
        
        # Return success response
        return jsonify({
            'success': True,
            'message': 'Email sent successfully',
            'sent_via': 'gmail_api' if send_via_gmail else 'smtp'
        })
        
    except Exception as e:
        import traceback
        logger.error(f"Error in send_email route: {e}")
        logger.error(f"Complete traceback: {traceback.format_exc()}")
        
        # Check configuration state
        logger.error(f"App config SMTP_SERVER: {current_app.config.get('SMTP_SERVER')}")
        logger.error(f"App config SMTP_EMAIL: {current_app.config.get('SMTP_EMAIL')}")
        logger.error(f"App config SMTP_PASSWORD exists: {current_app.config.get('SMTP_PASSWORD') is not None}")
        
        return jsonify({
            'success': False,
            'message': f'An unexpected error occurred: {str(e)}'
        }), 500