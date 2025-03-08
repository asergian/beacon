"""Main entry point for Gmail worker process.

This module provides the command-line interface and main execution logic
for the Gmail worker process.
"""

import argparse
import asyncio
import json
import logging
import os
import signal
import sys
import traceback
from datetime import datetime
from typing import Dict, Any, Optional

# Import local modules
from utils import (
    get_logger,
    parse_content_from_file,
    cleanup_resources,
    calculate_cutoff_time
)
from api_client import GmailService


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
    
    Args:
        credentials_json: OAuth credentials JSON string or path
        user_email: User's email address
        query: Gmail search query
        include_spam_trash: Whether to include spam and trash folders
        days_back: Number of days back to fetch emails
        max_results: Maximum number of results to return
        user_timezone: User's timezone
        
    Returns:
        Dictionary with results
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
    
    Args:
        credentials_json: OAuth credentials JSON string or path
        user_email: User's email address
        to: Recipient email address(es)
        subject: Email subject
        content: Plain text content
        cc: CC recipients
        bcc: BCC recipients
        html_content: HTML content
        
    Returns:
        Dictionary with send result
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


def setup_signal_handlers() -> None:
    """Set up signal handlers for timeout and interrupts."""
    # Set up signal handler for timeout
    def handle_timeout(signum, frame):
        logger.error("Timeout reached while processing request")
        # Output JSON response based on the action
        if len(sys.argv) > 2 and '--action' in sys.argv and 'send_email' in sys.argv:
            print(json.dumps({
                "success": False,
                "error": "Timeout reached while processing request",
            }), flush=True)
        else:
            print(json.dumps({
                "error": "Timeout reached while fetching emails",
                "emails": []
            }), flush=True)
        sys.exit(1)
        
    # Set a timeout (e.g. 5 minutes) to prevent hanging
    signal.signal(signal.SIGALRM, handle_timeout)
    signal.alarm(300)  # 5 minutes timeout


def optimize_process() -> None:
    """Optimize the process for better performance."""
    # Set process priority higher on Unix systems
    if sys.platform != 'win32':
        try:
            os.nice(-15)  # Even higher priority (-20 is highest, 19 is lowest)
            logger.info(f"Set process nice value to -15 for better performance")
        except Exception as e:
            logger.warning(f"Could not set process priority: {e}")


def parse_arguments():
    """Parse command line arguments.
    
    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(description="Gmail API Worker Process")
    parser.add_argument("--credentials", required=True, help="OAuth2 credentials JSON string or @file containing credentials")
    parser.add_argument("--user_email", required=True, help="User email address")
    parser.add_argument("--action", choices=['fetch_emails', 'send_email'], default='fetch_emails',
                      help='Action to perform (fetch_emails or send_email)')
    
    # Arguments for fetch_emails action
    parser.add_argument("--query", default="", help="Gmail search query")
    parser.add_argument("--include_spam_trash", action="store_true", help="Include emails in spam and trash")
    parser.add_argument("--days_back", type=int, default=1, help="Number of days back to fetch emails")
    parser.add_argument('--max_results', type=int, default=100, help='Maximum number of results to fetch')
    parser.add_argument('--user_timezone', default='US/Pacific', help='User timezone (e.g., "America/New_York")')
    
    # Arguments for send_email action
    parser.add_argument('--to', help='Recipient email address(es) for send_email action')
    parser.add_argument('--subject', help='Email subject for send_email action')
    parser.add_argument('--content', help='Email content (plain text) or @file path for send_email action')
    parser.add_argument('--html_content', help='Email HTML content or @file path for send_email action')
    parser.add_argument('--cc', help='CC recipients for send_email action')
    parser.add_argument('--bcc', help='BCC recipients for send_email action')
    
    return parser.parse_args()


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