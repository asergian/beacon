"""Process utility functions for the Gmail worker module.

This module provides utility functions for process management, optimization,
signal handling, and command-line argument parsing.
"""

import argparse
import json
import logging
import os
import signal
import sys
from typing import Any, Dict, Optional

from utils.logging_utils import get_logger

# Set up logger for this module
logger = get_logger('process_utils')


def setup_signal_handlers() -> None:
    """Set up signal handlers for timeout and interrupts.
    
    Configures signal handlers to handle timeouts gracefully, preventing
    the worker process from hanging indefinitely. This is important for
    maintaining reliability in production environments.
    
    Returns:
        None
    """
    # Set up signal handler for timeout
    def handle_timeout(signum, frame):
        """Handle SIGALRM signal for process timeout.
        
        Logs the timeout event and outputs a structured JSON error response
        before exiting the process.
        
        Args:
            signum: int: Signal number (SIGALRM)
            frame: frame: Current stack frame
            
        Note:
            This function does not return as it calls sys.exit(1)
        """
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
    """Optimize the process for better performance.
    
    Configures operating system level optimizations like process priority
    to improve performance. This is particularly important for memory-intensive
    operations like email processing.
    
    Returns:
        None
    """
    # Set process priority higher on Unix systems, but only if we have permission
    if sys.platform != 'win32':
        try:
            # Check if we can set the nice value by trying a minimal change first
            current = os.nice(0)  # Get current nice value without changing it
            
            # Only attempt to lower nice value if we're not already at a low value
            if current > -15:
                os.nice(-15 - current)  # Set to -15 relative to current
                logger.info(f"Set process nice value to -15 for better performance")
            else:
                logger.info(f"Process already has good priority (nice={current})")
        except PermissionError:
            # Silently continue if we don't have permission - this is expected in many environments
            pass
        except Exception as e:
            logger.warning(f"Could not optimize process: {e}")


def parse_arguments():
    """Parse command line arguments.
    
    Configures and processes command line arguments for the Gmail worker.
    Handles arguments for both fetch_emails and send_email actions.
    
    Returns:
        argparse.Namespace: Parsed arguments object with the following attributes:
            - credentials: str: OAuth credentials JSON or file path
            - user_email: str: User's email address
            - action: str: Action to perform ('fetch_emails' or 'send_email')
            - query: str: Gmail search query (for fetch_emails)
            - include_spam_trash: bool: Whether to include spam/trash (for fetch_emails)
            - days_back: int: Number of days back to fetch (for fetch_emails)
            - max_results: int: Maximum results to return (for fetch_emails)
            - user_timezone: str: User's timezone (for fetch_emails)
            - to: str: Recipients (for send_email)
            - subject: str: Email subject (for send_email)
            - content: str: Email content (for send_email)
            - html_content: str: HTML content (for send_email)
            - cc: str: CC recipients (for send_email)
            - bcc: str: BCC recipients (for send_email)
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