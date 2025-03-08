"""Gmail client that uses a subprocess for memory isolation.

This module provides a Gmail client that implements the BaseEmailClient interface
but delegates the actual Gmail API operations to a subprocess for memory isolation.
It communicates with the subprocess via pipes or files.

Key features:
- Full memory isolation for Gmail API operations
- Elimination of raw message data transfer between processes
- Efficient subprocess communication using structured data
- Robust error handling and resource cleanup
"""

import logging
import json
import asyncio
import os
import sys
import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta, timezone
import platform
from zoneinfo import ZoneInfo

from flask import session
from google.oauth2.credentials import Credentials

from ..base import BaseEmailClient
from app.utils.memory_profiling import log_memory_usage, log_memory_cleanup
from .utils import (
    GmailAPIError,
    run_subprocess,
    parse_json_response,
    handle_subprocess_result,
    build_command,
    TempFileManager,
    calculate_date_cutoff
)

# Directory of this file
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# Path to the subprocess script
SUBPROCESS_PATH = os.path.join(CURRENT_DIR, "worker/main.py")

class GmailClientSubprocess(BaseEmailClient):
    """
    A client for interacting with Gmail using a subprocess for memory isolation.
    
    This class provides the same interface as GmailClient but uses a subprocess
    to fetch and process emails, which isolates the memory-intensive operations.
    
    Note: All methods that might be awaited in the email pipeline are implemented
    as async methods to maintain interface compatibility with GmailClient.
    """
    
    def __init__(self):
        """Initialize the Gmail API client subprocess handler."""
        self.logger = logging.getLogger(__name__)
        self._user_email = None
        self._credentials = None
        self._script_path = SUBPROCESS_PATH
        
        self.logger.debug(f"GmailClientSubprocess initialized with script: {self._script_path}")
        
        # Verify the script exists
        if not os.path.exists(self._script_path):
            self.logger.error(f"Gmail subprocess script not found: {self._script_path}")
            raise FileNotFoundError(f"Gmail subprocess script not found: {self._script_path}")
    
    async def connect(self, user_email: str):
        """Establish a connection to Gmail API using OAuth credentials."""
        # Store the user email
        self._user_email = user_email
        
        # Verify we have credentials for this user
        if 'credentials' not in session:
            raise GmailAPIError("No credentials found. Please authenticate first.")
        
        creds_dict = session['credentials']
        
        # Create credentials object
        self._credentials = Credentials(
            token=creds_dict['token'],
            refresh_token=creds_dict['refresh_token'],
            token_uri=creds_dict['token_uri'],
            client_id=creds_dict['client_id'],
            client_secret=creds_dict['client_secret'],
            scopes=creds_dict['scopes']
        )
        
        self.logger.info(f"Connected to Gmail API for user {user_email}")
        return True
    
    async def fetch_emails(self, days_back: int = 1, user_email: str = None, label_ids: List[str] = None,
                       query: str = None, include_spam_trash: bool = False, user_timezone: str = 'US/Pacific') -> List[Dict]:
        """
        Fetch emails from Gmail using subprocess to isolate memory usage.
        
        This method runs the Gmail API operations in a separate process to prevent
        memory leaks in the main application process. The subprocess handles all
        raw message parsing and returns only the essential metadata and content,
        without transferring the raw message data back to the main process.
        
        Args:
            days_back: Number of days back to fetch emails for
            user_email: User email address (if different from the authenticated user)
            label_ids: List of label IDs to filter by
            query: Gmail query string
            include_spam_trash: Whether to include emails in spam and trash
            user_timezone: User's timezone (e.g., 'America/New_York')
            
        Returns:
            List of email dictionaries containing processed message data (without raw messages)
            
        Raises:
            ValueError: If user_email is not provided
            GmailAPIError: If the subprocess fails or returns an error
        """
        if not self._user_email and not user_email:
            raise ValueError("User email is required")
            
        user = user_email or self._user_email
        
        log_memory_usage(self.logger, "Before Gmail Client Subprocess - Main Process")
        
        # Use TempFileManager to handle file cleanup
        with TempFileManager(self.logger) as temp_files:
            # Create temporary credentials file with properly serialized credentials
            creds_data = {
                'token': self._credentials.token,
                'refresh_token': self._credentials.refresh_token,
                'token_uri': self._credentials.token_uri,
                'client_id': self._credentials.client_id,
                'client_secret': self._credentials.client_secret,
                'scopes': self._credentials.scopes,
                'user_email': user
            }
            credentials_path = temp_files.create_file(
                json.dumps(creds_data),
                suffix=".json"
            )
            
            # Default query to filter by date if not provided
            if not query:
                # Calculate the date cutoff
                query = calculate_date_cutoff(days_back, user_timezone)
                self.logger.debug(f"Generated date query: {query}")
            
            # Modify the query to exclude emails from the SENT folder
            query = f"{query} -in:sent"
            self.logger.debug(f"Modified query to exclude sent emails: {query}")
            
            # Build command using the helper
            command = build_command(SUBPROCESS_PATH, credentials_path, user)
            
            # Add fetch-specific parameters, including include_spam_trash flag if needed
            command.extend([
                "--query", query,
                "--days_back", str(days_back),
                "--max_results", "100",
                "--user_timezone", user_timezone,
                *(["--include_spam_trash"] if include_spam_trash else [])
            ])
            
            # Start measuring time
            start_time = time.time()
            
            self.logger.info(f"Fetching emails for {user} with query: {query} (days_back={days_back})")
            
            # Execute subprocess
            stdout_data, stderr_lines, return_code = await run_subprocess(command, self.logger)
            
            # Process result using standardized error handling
            email_data = handle_subprocess_result(stdout_data, stderr_lines, return_code, "fetch emails", self.logger)
            
            # Verify we have emails data
            if 'emails' not in email_data:
                raise GmailAPIError("Invalid response format: 'emails' field missing")
            
            # Extract and process emails
            emails = email_data['emails']
            
            # Add cache key to each email
            for email in emails:
                email['cache_key'] = f"gmail:{user}:{email.get('id', '')}"
            
            duration = time.time() - start_time
            self.logger.info(f"Fetched {len(emails)} emails in {duration:.2f}s")
            
            return emails
    
    async def send_email(self, to: str, subject: str, content: str, cc: List[str] = None, 
                         bcc: List[str] = None, html_content: str = None, user_email: str = None) -> Dict:
        """
        Send an email using the Gmail API through a subprocess.
        
        Args:
            to: Recipient email address(es) - comma-separated string or single address
            subject: Email subject
            content: Plain text email content
            cc: Optional list of CC recipients
            bcc: Optional list of BCC recipients
            html_content: Optional HTML content (if not provided, plain text content will be used)
            user_email: Optional user email to send as (defaults to connected user)
            
        Returns:
            Dict: Response containing message ID and other details
            
        Raises:
            GmailAPIError: If the email sending fails or credentials are invalid
        """
        if not self._credentials:
            if not user_email and not self._user_email:
                raise GmailAPIError("Not connected to Gmail API. Call connect() first.")
            await self.connect(user_email or self._user_email)
        
        user = user_email or self._user_email
        
        # Use the TempFileManager context manager to handle file cleanup
        with TempFileManager(self.logger) as temp_files:
            # Create temporary credentials file with properly serialized credentials
            creds_data = {
                'token': self._credentials.token,
                'refresh_token': self._credentials.refresh_token,
                'token_uri': self._credentials.token_uri,
                'client_id': self._credentials.client_id,
                'client_secret': self._credentials.client_secret,
                'scopes': self._credentials.scopes,
                'user_email': user
            }
            credentials_path = temp_files.create_file(
                json.dumps(creds_data),
                suffix=".json"
            )
            # Build base command using helper
            cmd_parts = build_command(SUBPROCESS_PATH, credentials_path, user, action="send_email")
            
            # Add email-specific parameters
            cmd_parts.extend([
                "--to", to,
                "--subject", subject,
                "--content", f"@{temp_files.create_file(content, suffix='.txt')}"
            ])
            
            # Add HTML content if provided
            if html_content:
                cmd_parts.extend([
                    "--html_content", 
                    f"@{temp_files.create_file(html_content, suffix='.html')}"
                ])
            
            # Add optional CC and BCC parameters
            for param, value in [("cc", cc), ("bcc", bcc)]:
                if value:
                    cmd_parts.extend([
                        f"--{param}", 
                        ",".join(value) if isinstance(value, list) else value
                    ])
            
            # Execute subprocess
            stdout_data, stderr_lines, return_code = await run_subprocess(cmd_parts, self.logger)
            
            # Process result using standardized error handling
            result = handle_subprocess_result(stdout_data, stderr_lines, return_code, "send email", self.logger)
            
            # Verify success flag
            if not result.get('success', False):
                error = result.get('error', 'Unknown error')
                raise GmailAPIError(f"Failed to send email: {error}")
                
            self.logger.debug(f"Email sent successfully via Gmail API: {result.get('message_id')}")
            return result
    
    async def close(self):
        """Close the Gmail API connection."""
        # No connection to close in the subprocess model
        pass
            
    async def disconnect(self):
        """Cleanup method to close any open connections."""
        import gc
        try:
            log_memory_usage(self.logger, "Before Gmail Subprocess Disconnect")
            
            # Clear credential references
            self._credentials = None
            self._user_email = None
            
            # Force garbage collection
            gc.collect(generation=2)
            
            # Clear any httplib2 connections if the module is loaded
            if 'httplib2' in sys.modules:
                httplib2_mod = sys.modules['httplib2']
                
                # Clear connection caches
                if hasattr(httplib2_mod, 'SCHEMES'):
                    for scheme in list(httplib2_mod.SCHEMES.keys()):
                        if hasattr(httplib2_mod.SCHEMES[scheme], 'connections'):
                            httplib2_mod.SCHEMES[scheme].connections.clear()
                
                # Clear HTTP instance connection caches
                if hasattr(httplib2_mod, 'Http'):
                    http_class = httplib2_mod.Http
                    for attr in dir(http_class):
                        if attr.startswith('_conn_') and hasattr(http_class, attr):
                            setattr(http_class, attr, {})
            
            log_memory_cleanup(self.logger, "After Gmail Subprocess Disconnect")
            self.logger.info("Gmail client subprocess disconnected and memory cleaned")
            
            return True
        except Exception as e:
            self.logger.error(f"Error during disconnection: {e}")
            return False 