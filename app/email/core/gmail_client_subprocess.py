"""Gmail client that uses a subprocess for memory isolation.

This module provides a Gmail client that uses a subprocess to fetch and decode
emails, which isolates the memory-intensive operations from the main process.
"""

import asyncio
import json
import logging
import os
import signal
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
import time

import aiofiles
from googleapiclient.discovery import build
from googleapiclient.discovery_cache.base import Cache
from flask import session
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as AuthRequest

from app.utils.memory_utils import log_memory_usage
import base64
from email import message_from_bytes

# Directory of this file
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# Path to the subprocess script (this file)
SUBPROCESS_PATH = os.path.join(CURRENT_DIR, "gmail_subprocess.py")

class GmailAPIError(Exception):
    """Exception raised for Gmail API-related errors."""
    pass

class GmailClientSubprocess:
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
        
        self.logger.info(f"GmailClientSubprocess initialized with script: {self._script_path}")
        
        # Verify the script exists
        if not os.path.exists(self._script_path):
            self.logger.error(f"Gmail subprocess script not found: {self._script_path}")
            raise FileNotFoundError(f"Gmail subprocess script not found: {self._script_path}")
    
    async def connect(self, user_email: str):
        """Establish a connection to Gmail API using OAuth credentials."""
        try:
            # Store the user email
            self._user_email = user_email
            
            # Verify we have credentials for this user
            if 'credentials' not in session:
                raise GmailAPIError("No credentials found. Please authenticate first.")
            
            creds_dict = session['credentials']
            
            # Create credentials object to check if it's valid
            # We'll only use this to verify and refresh if needed
            credentials = Credentials(
                token=creds_dict['token'],
                refresh_token=creds_dict['refresh_token'],
                token_uri=creds_dict['token_uri'],
                client_id=creds_dict['client_id'],
                client_secret=creds_dict['client_secret'],
                scopes=creds_dict['scopes']
            )
            
            # Check if credentials need refresh
            if credentials.expired and credentials.refresh_token:
                self.logger.info("Refreshing expired credentials")
                credentials.refresh(AuthRequest())
                
                # Update session with new token
                creds_dict['token'] = credentials.token
                session['credentials'] = creds_dict
                
                self.logger.info("Credentials refreshed successfully")
            
            self._credentials = credentials
            
            self.logger.info(f"Connected to Gmail API for user {user_email}")
            return True
            
        except Exception as e:
            self.logger.error(f"Connection error: {e}")
            self._credentials = None
            self._user_email = None
            raise GmailAPIError(f"Failed to connect: {e}")
    
    async def fetch_emails(self, days_back: int = 1, user_email: str = None, label_ids: List[str] = None,
                   query: str = None, include_spam_trash: bool = False) -> List[Dict]:
        """
        Fetch emails from Gmail using subprocess to isolate memory usage
        
        Args:
            days_back: Number of days back to fetch emails for
            user_email: User email address (if different from the authenticated user)
            label_ids: List of label IDs to filter by
            query: Gmail query string
            include_spam_trash: Whether to include emails in spam and trash
            
        Returns:
            List of email dictionaries with processed message data
        """
        if not self._user_email and not user_email:
            raise ValueError("User email is required")
            
        user = user_email or self._user_email
        
        log_memory_usage(self.logger, "Before Gmail Client Subprocess - Main Process")
        
        try:
            with tempfile.NamedTemporaryFile(mode='w+', delete=False) as f:
                credentials_path = f.name
                f.write(self._credentials.to_json())
            
            # Default query to filter by date if not provided
            if not query:
                # Adjust days_back to match cache logic (days_back=1 means today only)
                adjusted_days = max(0, days_back - 1)  # Ensure we don't use negative days
                
                # Calculate the time range using local timezone
                local_tz = datetime.now().astimezone().tzinfo
                local_midnight = (datetime.now(local_tz) - timedelta(days=adjusted_days)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                
                # Calculate one day before the local midnight in UTC for the query
                utc_date = (local_midnight).astimezone(timezone.utc)
                date_cutoff = utc_date.strftime('%Y/%m/%d')
                query = f"after:{date_cutoff}"
                
                self.logger.info(
                    f"Fetching emails with days_back={days_back}, adjusted_days={adjusted_days}\n"
                    f"    Local midnight cutoff: {local_midnight.strftime('%Y-%m-%d %H:%M:%S %Z')}\n"
                    f"    Query cutoff (UTC-1): after:{date_cutoff}"
                )
                
            if label_ids:
                # Add label filters to query
                for label in label_ids:
                    query += f" label:{label}"
                    
            # Run the subprocess with the processed query
            self.logger.info(f"Fetching emails with query: {query}")
            
            cmd = [
                sys.executable, 
                self._script_path,
                "--credentials", f"@{credentials_path}",
                "--user_email", user,
                "--query", query
            ]
            
            if include_spam_trash:
                cmd.append("--include_spam_trash")
                
            self.logger.debug(f"Running command: {' '.join(cmd)}")
            
            # Use asyncio to run the subprocess asynchronously
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Await the subprocess completion
            stdout_bytes, stderr_bytes = await process.communicate()
            
            # Convert bytes to strings
            stdout = stdout_bytes.decode('utf-8')
            stderr = stderr_bytes.decode('utf-8')
            
            # Only log stderr as error if process return code indicates failure
            # Otherwise forward subprocess logs at INFO level
            if process.returncode != 0:
                self.logger.error(f"Subprocess error: {stderr}")
                raise GmailAPIError(f"Gmail subprocess failed with code {process.returncode}: {stderr}")
            elif stderr:
                # Process and format subprocess logs for better readability
                log_lines = stderr.strip().split('\n')
                
                # Only log a summary to avoid cluttering the main log
                summary_lines = []
                for line in log_lines:
                    # Extract important information like email counts, memory usage
                    if "Found" in line and "emails" in line:
                        summary_lines.append(line)
                    elif "Successfully retrieved" in line:
                        summary_lines.append(line)
                    elif "Memory usage" in line:
                        summary_lines.append(line)
                
                if summary_lines:
                    self.logger.info(f"Subprocess summary: {' | '.join(summary_lines)}")
                
                # Log all lines at debug level for troubleshooting
                for line in log_lines:
                    self.logger.debug(f"Subprocess: {line}")
            
            try:
                result = json.loads(stdout)
                emails = result.get("emails", [])
                filtered_emails = []
                
                # Keep track of filtering stats
                total_emails = len(emails)
                filtered_out = 0
                
                # Recalculate cutoff time for consistency
                if days_back > 0:
                    local_tz = datetime.now().astimezone().tzinfo
                    adjusted_days = max(0, days_back - 1)
                    local_midnight_cutoff = (datetime.now(local_tz) - timedelta(days=adjusted_days)).replace(
                        hour=0, minute=0, second=0, microsecond=0
                    )
                else:
                    local_midnight_cutoff = None
                
                # Process the emails to convert base64-encoded raw_message back to bytes
                for email in emails:
                    if 'raw_message' in email and isinstance(email['raw_message'], str):
                        try:
                            # Decode base64 data
                            raw_msg = base64.b64decode(email['raw_message'])
                            email['raw_message'] = raw_msg
                            
                            # Extract additional headers like original client does
                            email_msg = message_from_bytes(raw_msg)
                            
                            # Add Message-ID header to match original client format
                            email['Message-ID'] = email_msg.get('Message-ID')
                            
                            # Add other important headers
                            email['subject'] = email_msg.get('subject')
                            email['from'] = email_msg.get('from')
                            email['to'] = email_msg.get('to')
                            date_str = email_msg.get('date')
                            email['date'] = date_str
                            
                            # Filter by date if we have a cutoff and this is a date-filtered query
                            if local_midnight_cutoff and date_str:
                                try:
                                    # Parse email date - using the same approach as GmailClient
                                    from email.utils import parsedate_to_datetime
                                    
                                    if not date_str:
                                        # Skip emails with no date
                                        continue
                                        
                                    try:
                                        # Remove the "(UTC)" part if it exists
                                        date_str = date_str.split(' (')[0].strip()
                                        email_date = parsedate_to_datetime(date_str)
                                    except Exception as e:
                                        self.logger.warning(f"Failed to parse email date '{date_str}': {e}")
                                        # Still include the email if date parsing fails
                                        filtered_emails.append(email)
                                        continue
                                    
                                    if not email_date:
                                        # Skip emails with unparseable dates
                                        self.logger.warning(f"Couldn't parse date: {date_str}")
                                        # Still include the email
                                        filtered_emails.append(email)
                                        continue
                                    
                                    # Convert to local timezone for comparison
                                    local_email_date = email_date.astimezone(local_tz)
                                    
                                    # Only include emails at or after our local midnight cutoff
                                    if local_email_date >= local_midnight_cutoff:
                                        filtered_emails.append(email)
                                        self.logger.debug(
                                            f"INCLUDED: Email '{email.get('subject', 'No subject')}' "
                                            f"from {local_email_date.strftime('%Y-%m-%d %H:%M:%S %Z')}"
                                        )
                                    else:
                                        self.logger.debug(
                                            f"FILTERED OUT: Email '{email.get('subject', 'No subject')}' "
                                            f"from {local_email_date.strftime('%Y-%m-%d %H:%M:%S %Z')} - "
                                            f"before cutoff {local_midnight_cutoff.strftime('%Y-%m-%d %H:%M:%S %Z')}"
                                        )
                                        filtered_out += 1
                                except Exception as e:
                                    # If date parsing fails, include the email to be safe
                                    self.logger.warning(f"Error in date filtering: {e}")
                                    filtered_emails.append(email)
                            else:
                                # No filtering needed, include the email
                                filtered_emails.append(email)
                            
                            # Log the ID being used for cache identification
                            self.logger.debug(f"Email ID for cache: {email['id']}, Message-ID header: {email['Message-ID']}")
                            
                            # Clear reference to parsed email message
                            email_msg = None
                        except Exception as e:
                            self.logger.error(f"Failed to decode or process raw_message: {e}")
                            # If decoding fails, set to None to avoid parsing errors
                            email['raw_message'] = None
                            # Still include the email with the error
                            filtered_emails.append(email)
                    else:
                        # No raw message to process, include as is
                        filtered_emails.append(email)
                
                if local_midnight_cutoff:
                    self.logger.info(
                        f"Fetched {total_emails} emails from Gmail API, filtered to {len(filtered_emails)} "
                        f"(filtered out {filtered_out} before {local_midnight_cutoff.strftime('%Y-%m-%d %H:%M:%S')})"
                    )
                else:
                    self.logger.info(f"Fetched {len(filtered_emails)} emails from Gmail API for {user}")
                
                return filtered_emails
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse subprocess output: {e}")
                self.logger.debug(f"Subprocess output: {stdout[:500]}...")
                raise GmailAPIError(f"Failed to parse subprocess output: {e}")
                
        except Exception as e:
            self.logger.error(f"Error in fetch_emails: {str(e)}")
            raise
        finally:
            # Remove temp credentials file
            if 'credentials_path' in locals():
                try:
                    os.unlink(credentials_path)
                except:
                    pass
            
            log_memory_usage(self.logger, "After Gmail Client Subprocess - Main Process")
    
    async def close(self):
        """Close the Gmail API connection."""
        # No connection to close in the subprocess model
        pass
            
    async def disconnect(self):
        """Cleanup method to close any open connections."""
        self.logger.info("Gmail client subprocess disconnected")
        return True 