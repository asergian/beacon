"""Main entry point for Gmail worker process.

This module provides the main entry point for the Gmail worker process,
handling email fetching and sending tasks in a separate process.
"""

import asyncio
import json
import logging
import os
import sys
import traceback
from datetime import datetime
from typing import Dict, Any, Optional

# Add the project root to sys.path to ensure imports work correctly
project_root = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../../../../'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import local modules with absolute imports
from app.email.clients.gmail.worker.utils import (
    get_logger,
    parse_content_from_file,
    cleanup_resources,
    calculate_cutoff_time,
    setup_signal_handlers,
    optimize_process,
    parse_arguments
)
from app.email.clients.gmail.worker.api_client import GmailService


# Configure logging to write to a file
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../../../logs')
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, 'gmail_worker.log')

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        # Keep a minimal stderr handler for critical errors
        logging.StreamHandler(sys.stderr)
    ]
)
logger = get_logger()
logger.info(f"Gmail worker logging to: {LOG_FILE}")


async def main(credentials_json: str, user_email: str, query: str, 
              include_spam_trash: bool, days_back: int, 
              max_results: int = 100, user_timezone: str = 'US/Pacific') -> Dict[str, Any]:
    """Main function to run Gmail API operations.
    
    Handles the primary email fetching workflow by initializing the Gmail service,
    calculating date cutoffs based on the days_back parameter, fetching emails
    that match the query, and returning the results.
    
    Args:
        credentials_json: str: OAuth credentials JSON string or path to credentials file
        user_email: str: User's email address for which to fetch emails
        query: str: Gmail search query (same format as Gmail search box)
        include_spam_trash: bool: Whether to include emails from spam and trash folders
        days_back: int: Number of days back to fetch emails (1 = today only)
        max_results: int: Maximum number of results to return. Defaults to 100.
        user_timezone: str: User's timezone string (e.g., 'US/Pacific'). Defaults to 'US/Pacific'.
        
    Returns:
        Dict[str, Any]: Dictionary with the following keys:
            - emails: List of processed email dictionaries
            - count: Number of emails returned
            - query: The query that was used
            - user_email: The user email that was queried
            - days_back: Number of days back that were queried
            - error: Error message if an error occurred (only present on error)
    """
    try:
        # Initialize the Gmail service
        gmail = GmailService(credentials_json, logger)
        await gmail.initialize()
        
        # Calculate date cutoff for filtering
        if days_back > 0:
            _, cutoff_time = calculate_cutoff_time(days_back, user_timezone)
        else:
            cutoff_time = None
        
        # Fetch emails
        emails = await gmail.fetch_emails(
            query=query,
            include_spam_trash=include_spam_trash,
            cutoff_time=cutoff_time,
            max_results=max_results
        )
        
        # Return results as JSON
        return {
            "emails": emails,
            "count": len(emails),
            "query": query,
            "user_email": user_email,
            "days_back": days_back
        }
    except Exception as e:
        logger.error(f"Error in main function: {e}")
        return {
            "error": str(e),
            "emails": []
        }


async def send_email_task(credentials_json: str, user_email: str, to: str, 
                         subject: str, content: str, cc: Optional[str] = None,
                         bcc: Optional[str] = None, html_content: Optional[str] = None) -> Dict[str, Any]:
    """Task for sending an email.
    
    Handles the email sending workflow by initializing the Gmail service,
    processing recipient lists, and sending the email with both plain text
    and optional HTML content.
    
    Args:
        credentials_json: str: OAuth credentials JSON string or path to credentials file
        user_email: str: User's email address from which to send the email
        to: str: Recipient email address(es), comma-separated for multiple recipients
        subject: str: Email subject line
        content: str: Plain text email content
        cc: Optional[str]: CC recipients, comma-separated for multiple recipients
        bcc: Optional[str]: BCC recipients, comma-separated for multiple recipients
        html_content: Optional[str]: HTML version of the email content
        
    Returns:
        Dict[str, Any]: Dictionary with the following keys:
            - success: bool: Whether the email was sent successfully
            - message_id: str: ID of the sent message (if successful)
            - thread_id: str: ID of the thread the message belongs to (if successful)
            - user_email: str: The email address that sent the message (if successful)
            - error: str: Error message (only present on error)
    """
    try:
        # Initialize the Gmail service
        gmail = GmailService(credentials_json, logger)
        await gmail.initialize()
        
        # Process cc and bcc parameters
        cc_list = cc.split(',') if cc else None
        bcc_list = bcc.split(',') if bcc else None
        
        # Send email
        return await gmail.send_email(
            to=to,
            subject=subject,
            content=content,
            cc=cc_list,
            bcc=bcc_list,
            html_content=html_content
        )
    except Exception as e:
        logger.error(f"Error in send_email_task: {e}")
        return {
            "success": False,
            "error": str(e)
        }


if __name__ == "__main__":
    # Parse arguments
    args = parse_arguments()
    
    # Handle content and html_content from file (if specified with @)
    content = parse_content_from_file(args.content)
    html_content = parse_content_from_file(args.html_content)
    
    try:
        # Log starting memory usage
        logger.info(f"Initial memory usage: {os.popen(f'ps -p {os.getpid()} -o rss=').read().strip()} KB")
        
        # Set up signal handlers
        setup_signal_handlers()
        
        # Optimize process
        optimize_process()
        
        # Handle different actions
        if args.action == 'send_email':
            # Validate required parameters for sending email
            if not args.to or not content:
                print(json.dumps({
                    "success": False,
                    "error": "Missing required parameters for send_email action: to and content"
                }), flush=True)
                sys.exit(1)
                
            # Execute send_email function
            result = asyncio.run(send_email_task(
                credentials_json=args.credentials,
                user_email=args.user_email,
                to=args.to,
                subject=args.subject or "",
                content=content,
                cc=args.cc,
                bcc=args.bcc,
                html_content=html_content
            ))
            
            # Output result as JSON
            print(json.dumps(result), flush=True)
        else:
            # Execute fetch_emails function
            result = asyncio.run(main(
                credentials_json=args.credentials,
                user_email=args.user_email,
                query=args.query,
                include_spam_trash=args.include_spam_trash,
                days_back=args.days_back,
                max_results=args.max_results,
                user_timezone=args.user_timezone
            ))
            
            # Output result as JSON
            print(json.dumps(result), flush=True)
            
    except Exception as e:
        # Print error as JSON response
        if args.action == 'send_email':
            print(json.dumps({
                "success": False,
                "error": str(e)
            }), flush=True)
        else:
            error_response = {
                "error": str(e),
                "traceback": traceback.format_exc()
            }
            logger.error(f"Error in worker: {error_response['error']}")
            logger.debug(f"Traceback: {error_response['traceback']}")
            print(json.dumps(error_response), flush=True)
        sys.exit(1)
    finally:
        # Ensure all resources are cleaned up before exit
        cleanup_resources(logger) 