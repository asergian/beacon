"""Routes for static pages like Privacy Policy, Terms of Service, and Support."""

from flask import Blueprint, render_template, request, jsonify, current_app
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import json
import smtplib
from email.message import EmailMessage
import os
import logging
from datetime import datetime
import re

static_pages_bp = Blueprint('static_pages', __name__)

# Initialize rate limiting
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

@static_pages_bp.route('/privacy-policy')
def privacy_policy():
    """Render the Privacy Policy page."""
    return render_template('static/privacy_policy.html')

@static_pages_bp.route('/terms-of-service')
def terms_of_service():
    """Render the Terms of Service page."""
    return render_template('static/terms_of_service.html')

@static_pages_bp.route('/support')
def support():
    """Render the Support page."""
    return render_template('static/support.html')

@static_pages_bp.route('/api/support-message', methods=['POST'])
@limiter.limit("5 per hour")  # Rate limit to prevent abuse
def submit_support_message():
    """Handle support form submissions.
    
    Returns:
        JSON response with success/error message
    """
    try:
        # Get form data from request
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'No data provided'
            }), 400
        
        # Extract fields
        name = data.get('name', '').strip()
        email = data.get('email', '').strip()
        subject = data.get('subject', 'General Question').strip()
        message = data.get('message', '').strip()
        
        # Server-side validation
        errors = validate_support_form(name, email, message)
        if errors:
            return jsonify({
                'success': False,
                'message': errors[0]  # Return first error message
            }), 400
            
        # Log the support request
        log_support_request(name, email, subject, message)
        
        # Send email notification
        send_support_email(name, email, subject, message)
        
        return jsonify({
            'success': True,
            'message': 'Your message has been received. We will get back to you soon!'
        })
        
    except Exception as e:
        # Log the error
        current_app.logger.error(f"Support form error: {str(e)}")
        
        return jsonify({
            'success': False,
            'message': 'An error occurred while processing your request.'
        }), 500

def validate_support_form(name, email, message):
    """Validate support form fields.
    
    Args:
        name (str): User's name
        email (str): User's email
        message (str): Support message
        
    Returns:
        list: List of error messages, empty if validation passed
    """
    errors = []
    
    # Validate name
    if not name:
        errors.append('Please enter your name')
    elif len(name) > 100:
        errors.append('Name is too long (maximum 100 characters)')
    
    # Validate email
    if not email:
        errors.append('Please enter your email address')
    elif not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
        errors.append('Please enter a valid email address')
    elif len(email) > 100:
        errors.append('Email is too long (maximum 100 characters)')
    
    # Validate message
    if not message:
        errors.append('Please enter a message')
    elif len(message) > 5000:
        errors.append('Message is too long (maximum 5000 characters)')
    
    return errors

def log_support_request(name, email, subject, message):
    """Log support request to file for record keeping.
    
    Args:
        name (str): User's name
        email (str): User's email
        subject (str): Message subject
        message (str): Support message
    """
    try:
        # Create logs directory if it doesn't exist
        log_dir = os.path.join(current_app.root_path, 'logs')
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # Construct log path
        log_file = os.path.join(log_dir, 'support_requests.log')
        
        # Create log entry
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = {
            'timestamp': timestamp,
            'name': name,
            'email': email,
            'subject': subject,
            'message': message
        }
        
        # Write to log file (append mode)
        with open(log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
            
    except Exception as e:
        current_app.logger.error(f"Error logging support request: {str(e)}")

def send_support_email(name, email, subject, message):
    """Send support email notification to administrators.
    
    Args:
        name (str): User's name
        email (str): User's email
        subject (str): Message subject
        message (str): Support message
    """
    try:
        # Get email settings from config or environment variables
        smtp_host = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
        smtp_port = int(os.environ.get('SMTP_PORT', 587))
        smtp_user = os.environ.get('SMTP_EMAIL', current_app.config.get('SMTP_EMAIL'))
        smtp_password = os.environ.get('SMTP_PASSWORD', current_app.config.get('SMTP_PASSWORD'))
        support_email = os.environ.get('SUPPORT_EMAIL', 'support@shronas.com')
        
        # Skip if SMTP credentials are not configured
        if not smtp_user or not smtp_password:
            current_app.logger.warning("SMTP not configured, skipping email notification")
            return
        
        # Create email message
        msg = EmailMessage()
        msg['Subject'] = f'[Support Form] {subject} - from {name}'
        msg['From'] = smtp_user
        msg['To'] = support_email
        msg['Reply-To'] = email
        
        # Format email body with clearly separated sections
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        email_body = f"""
        SENDER INFORMATION:
        -------------------
        Name: {name}
        Email: {email}
        Time: {timestamp}
        
        MESSAGE DETAILS:
        ---------------
        Subject: {subject}
        
        Message:
        {message}
        
        ---
        This message was automatically generated by the Beacon Support Form.
        """
        
        msg.set_content(email_body)
        
        # Send email and log attempt
        current_app.logger.info(f"Attempting to send support email: From={smtp_user}, To={support_email}, Subject='{subject}'")
        
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
            
            # Log successful email sending
            current_app.logger.info(f"Support email sent successfully from {name} <{email}> to {support_email}")
            
    except Exception as e:
        current_app.logger.error(f"Error sending support email: {str(e)}")
        # Add more detailed error information for debugging
        current_app.logger.error(f"Email details: From={smtp_user if 'smtp_user' in locals() else 'N/A'}, "
                                 f"To={support_email if 'support_email' in locals() else 'N/A'}, "
                                 f"Subject={subject}, Name={name}, Sender Email={email}") 