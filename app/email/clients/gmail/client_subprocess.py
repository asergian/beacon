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
import tempfile
from typing import Dict, List
from datetime import datetime, timedelta, timezone
import time

from ..base import BaseEmailClient
from flask import session
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as AuthRequest

from app.utils.memory_profiling import log_memory_usage, log_memory_cleanup
import platform
from zoneinfo import ZoneInfo

# Directory of this file
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# Path to the subprocess script (this file)
SUBPROCESS_PATH = os.path.join(CURRENT_DIR, "gmail_subprocess_worker.py")

class GmailAPIError(Exception):
    """Exception raised for Gmail API-related errors."""
    pass

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
        
        Note:
            This implementation eliminates memory usage growth in the main process
            by ensuring raw message data remains only in the subprocess.
        """
        if not self._user_email and not user_email:
            raise ValueError("User email is required")
            
        user = user_email or self._user_email
        
        log_memory_usage(self.logger, "Before Gmail Client Subprocess - Main Process")
        
        # Import gc at the beginning of the method for consistent access
        import gc
        credentials_path = None
        
        try:
            with tempfile.NamedTemporaryFile(mode='w+', delete=False) as f:
                credentials_path = f.name
                f.write(self._credentials.to_json())
            
            # Default query to filter by date if not provided
            if not query:
                # Adjust days_back to match cache logic (days_back=1 means today only)
                adjusted_days = max(0, days_back - 1)  # Ensure we don't use negative days
                
                # Calculate the time range using user's timezone
                try:
                    # Create timezone object from string
                    user_tz = ZoneInfo(user_timezone)
                    self.logger.debug(f"Using user timezone: {user_timezone}")
                except (ImportError, Exception) as e:
                    self.logger.warning(f"Could not use user timezone ({user_timezone}), falling back to US/Pacific: {e}")
                    try:
                        user_tz = ZoneInfo('US/Pacific')
                    except Exception:
                        user_tz = timezone.utc
                
                # Calculate the time range using user's timezone
                user_now = datetime.now(user_tz)
                user_midnight = (user_now - timedelta(days=adjusted_days)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                
                # Convert to UTC for the Gmail query
                utc_date = user_midnight.astimezone(timezone.utc)
                date_cutoff = utc_date.strftime('%Y/%m/%d')
                query = f"after:{date_cutoff}"
                
                self.logger.debug(f"Fetching emails with days_back={days_back}, adjusted_days={adjusted_days}")
                self.logger.debug(f"    User timezone: {user_timezone}")
                self.logger.debug(f"    User now: {user_now}")
                self.logger.debug(f"    User midnight cutoff: {user_midnight}")
                self.logger.debug(f"    UTC query cutoff: {utc_date}")
                self.logger.debug(f"    Gmail query: {query}")
            
            # Modify the query to exclude emails from the SENT folder
            query = f"{query} -in:sent"
            self.logger.debug(f"Modified query to exclude sent emails: {query}")
            
            # Use subprocess script path from the module
            subprocess_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gmail_subprocess_worker.py")
            
            # Execute the subprocess command
            self.logger.debug(f"Fetching emails with query: {query}")
            
            # Convert include_spam_trash to a command-line argument
            include_spam_trash_arg = "--include_spam_trash" if include_spam_trash else ""
            
            # Build Python command
            python_executable = sys.executable
            
            # Get the project root directory to add to PYTHONPATH
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.abspath(os.path.join(current_dir, '../../../../'))
            
            # Set environment variables for the subprocess
            env = os.environ.copy()
            if 'PYTHONPATH' in env:
                env['PYTHONPATH'] = f"{project_root}:{env['PYTHONPATH']}"
            else:
                env['PYTHONPATH'] = project_root
            
            # Pass days_back to the subprocess
            cmd = f"{python_executable} {subprocess_path} --credentials @{credentials_path} --user_email {user} --query \"{query}\" {include_spam_trash_arg} --days_back {days_back} --max_results 100 --user_timezone \"{user_timezone}\""
            
            # Create a process with higher priority for faster execution
            # Use a lambda for preexec_fn to ensure correct execution
            if platform.system() != 'Windows':
                def set_priority():
                    try:
                        import os
                        os.nice(-10)  # Lower nice value = higher priority
                    except Exception as e:
                        self.logger.debug(f"Could not set subprocess priority: {e}")
                        
                process = await asyncio.create_subprocess_shell(
                    cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    preexec_fn=set_priority,
                    env=env  # Add the environment variables
                )
            else:
                process = await asyncio.create_subprocess_shell(
                    cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env  # Add the environment variables
                )
            
            # Timing for performance analysis
            start_time = time.time()
            
            # Initialize metrics collection
            metrics = {
                'emails_found': None,
                'emails_retrieved': None,
                'raw_data_size': None,
                'peak_memory': None,
                'start_memory': None,
                'end_memory': None
            }
            
            # Create async tasks to read stdout and stderr concurrently
            # This ensures each stream has only one reader
            async def read_stdout():
                data = await process.stdout.read()
                return data
                
            async def read_stderr():
                lines = []
                while True:
                    line = await process.stderr.readline()
                    if not line:  # EOF
                        break
                        
                    lines.append(line)
                    decoded_line = line.decode().strip()
                    
                    # Try to parse structured log line
                    if " - " in decoded_line and " | " in decoded_line:
                        # Split by pipe character to get components
                        # Format is typically: TIMESTAMP - MODULE | LEVEL | MESSAGE 
                        log_parts = [part.strip() for part in decoded_line.split(" | ")]
                        
                        # Extract the timestamp and message parts
                        timestamp, module, message = log_parts
                        
                        # Log each subprocess line with proper context
                        if "ERROR" in decoded_line or "ERROR" in module:
                            self.logger.error(f"Subprocess: [{module}] {message}")
                        elif "WARNING" in decoded_line or "WARNING" in module:
                            self.logger.warning(f"Subprocess: [{module}] {message}")
                        else:
                            self.logger.debug(f"Subprocess: [{module}] {message}")  # Changed to debug level to reduce noise
                        
                        # Extract key metrics for summary
                        if "Found" in message and "emails matching" in message:
                            try:
                                metrics['emails_found'] = int(message.split("Found ")[1].split(" emails")[0])
                            except:
                                pass
                        elif "Successfully retrieved" in message:
                            try:
                                metrics['emails_retrieved'] = int(message.split("Successfully retrieved ")[1].split(" emails")[0])
                            except:
                                pass
                        elif "Total data processed:" in message:
                            try:
                                raw_mb = float(message.split("Total data processed: ")[1].split(" MB")[0])
                                metrics['raw_data_size'] = raw_mb
                            except:
                                pass
                        elif "Memory Usage" in message:
                            try:
                                if "RSS=" in message:
                                    rss = float(message.split("RSS=")[1].split("MB")[0])
                                    if metrics['peak_memory'] is None or rss > metrics['peak_memory']:
                                        metrics['peak_memory'] = rss
                                    if "Subprocess Start" in message and metrics['start_memory'] is None:
                                        metrics['start_memory'] = rss
                                    if "Before Exit" in message:
                                        metrics['end_memory'] = rss
                            except:
                                pass
                    else:
                        # Fall back for lines that don't match expected format
                        self.logger.debug(f"Subprocess: {decoded_line}")  # Changed to debug level
                
                return lines
            
            # Run both tasks concurrently
            stdout_task = asyncio.create_task(read_stdout())
            stderr_task = asyncio.create_task(read_stderr())
            
            # Wait for both tasks and the process to complete
            try:
                # Use asyncio.gather to await both tasks
                stdout_data, stderr_lines = await asyncio.gather(stdout_task, stderr_task)
                
                # Wait for the process to exit
                await process.wait()
                
                # Log a concise summary of key metrics
                if any(v is not None for v in metrics.values()):
                    memory_change = ""
                    if metrics['start_memory'] and metrics['peak_memory']:
                        memory_increase = metrics['peak_memory'] - metrics['start_memory']
                        memory_change = f", Memory +{memory_increase:.1f}MB"
                        
                    summary_msg = f"Subprocess summary: "
                    if metrics['emails_found'] is not None:
                        summary_msg += f"Found {metrics['emails_found']} emails"
                    if metrics['emails_retrieved'] is not None:
                        summary_msg += f", Retrieved {metrics['emails_retrieved']} emails"
                    summary_msg += memory_change
                    
                    self.logger.info(summary_msg)
            except asyncio.CancelledError:
                # If we're cancelled, make sure to terminate the subprocess
                process.terminate()
                raise
            except Exception as e:
                self.logger.error(f"Error during subprocess execution: {e}")
                # Try to terminate the process in case it's still running
                process.terminate()
                raise GmailAPIError(f"Error during subprocess execution: {e}")
            
            # Process duration
            duration = time.time() - start_time
            
            # Check for errors and log detailed information
            if process.returncode != 0:
                # Fix the type handling for stderr_lines
                if isinstance(stderr_lines, list):
                    stderr_output = "\n".join([line.decode("utf-8") if isinstance(line, bytes) else line for line in stderr_lines])
                elif isinstance(stderr_lines, bytes):
                    stderr_output = stderr_lines.decode("utf-8")
                else:
                    stderr_output = str(stderr_lines)
                    
                self.logger.error(f"Subprocess failed with code {process.returncode}")
                self.logger.error(f"Subprocess stderr output:")
                
                # Split stderr output by lines for better readability in logs
                if stderr_output:
                    for line in stderr_output.splitlines():
                        self.logger.error(f"  {line}")
                else:
                    self.logger.error("  [No stderr output]")
                
                # Log stdout as well in case it contains useful information
                if stdout_data:
                    if isinstance(stdout_data, bytes):
                        stdout_output = stdout_data.decode("utf-8")
                    else:
                        stdout_output = str(stdout_data)
                        
                    self.logger.error(f"Subprocess stdout output:")
                    for line in stdout_output.splitlines():
                        self.logger.error(f"  {line}")
                
                # More robust error message
                error_summary = f"Gmail subprocess failed with code {process.returncode}"
                if stderr_output:
                    # Extract the last line which might contain the actual error
                    last_error_line = stderr_output.splitlines()[-1] if stderr_output.splitlines() else ""
                    error_summary += f": {last_error_line}"
                
                raise GmailAPIError(error_summary)
            
            # Parse the JSON output - use faster ujson if available
            log_memory_usage(self.logger, "Before JSON Deserialization")
            try:
                # Try to use orjson for faster processing (faster than ujson)
                import orjson
                # Handle potential extra data by finding the JSON object
                stdout_str = stdout_data.decode().strip()
                # Find the first '{' and last '}' to extract the JSON object
                json_start = stdout_str.find('{')
                json_end = stdout_str.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = stdout_str[json_start:json_end]
                    email_data = orjson.loads(json_str)
                else:
                    raise ValueError(f"Could not find valid JSON object in subprocess output")
            except ImportError:
                try:
                    # Try to use ujson for faster parsing if available
                    import ujson
                    stdout_str = stdout_data.decode().strip()
                    # Find the first '{' and last '}' to extract the JSON object
                    json_start = stdout_str.find('{')
                    json_end = stdout_str.rfind('}') + 1
                    if json_start >= 0 and json_end > json_start:
                        json_str = stdout_str[json_start:json_end]
                        email_data = ujson.loads(json_str)
                    else:
                        raise ValueError(f"Could not find valid JSON object in subprocess output")
                except ImportError:
                    # Fall back to standard json
                    stdout_str = stdout_data.decode().strip()
                    # Find the first '{' and last '}' to extract the JSON object
                    json_start = stdout_str.find('{')
                    json_end = stdout_str.rfind('}') + 1
                    if json_start >= 0 and json_end > json_start:
                        json_str = stdout_str[json_start:json_end]
                        email_data = json.loads(json_str)
                    else:
                        raise ValueError(f"Could not find valid JSON object in subprocess output")
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse subprocess output: {e}")
                self.logger.debug(f"Subprocess output: {stdout_data[:500]}...")
                raise GmailAPIError(f"Failed to parse subprocess output: {e}")
                
            # Check for success
            if not email_data.get('success', False):
                error_msg = email_data.get('error', 'Unknown error in Gmail subprocess')
                self.logger.error(f"Gmail subprocess returned error: {error_msg}")
                raise GmailAPIError(error_msg)
            
            # Get emails
            emails = email_data.get('emails', [])
            self.logger.debug(f"Deserialized {len(emails)} emails from subprocess")
            log_memory_usage(self.logger, "After JSON Deserialization")
            
            # Since we've already done parsing and filtering in the subprocess,
            # we can now directly use the emails as is.
            # The emails no longer contain raw_message data, only processed content,
            # which significantly reduces memory usage in the main process.
            
            # Log final stats
            fetched_count = len(emails)
            
            # Now we can include the filtering info from the subprocess
            included_days = f" since {days_back} days ago" if days_back > 1 else " from today"
            self.logger.debug(f"Fetched {fetched_count} emails from Gmail API{included_days}")
            
            log_memory_usage(self.logger, "After Email Processing - Main Process")
            
            return emails
                
        except Exception as e:
            self.logger.error(f"Error fetching emails: {e}")
            raise GmailAPIError(f"Failed to fetch emails: {e}")
            
        finally:
            # Always clean up the credentials file
            if credentials_path and os.path.exists(credentials_path):
                try:
                    os.unlink(credentials_path)
                except Exception as e:
                    self.logger.warning(f"Error removing credentials file: {e}")
    
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
        
        # Temporary file for credentials
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as credentials_file:
            credentials_path = credentials_file.name
            # Extract credentials data from the credentials object
            creds_data = {
                'token': self._credentials.token,
                'refresh_token': self._credentials.refresh_token,
                'token_uri': self._credentials.token_uri,
                'client_id': self._credentials.client_id,
                'client_secret': self._credentials.client_secret,
                'scopes': self._credentials.scopes
            }
            # Write credentials to temp file
            json.dump(creds_data, credentials_file)
        
        try:
            # Build command to execute subprocess
            python_executable = sys.executable
            subprocess_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gmail_subprocess_worker.py")
            
            # Get the project root directory to add to PYTHONPATH
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.abspath(os.path.join(current_dir, '../../../../'))
            
            # Set environment variables for the subprocess
            env = os.environ.copy()
            if 'PYTHONPATH' in env:
                env['PYTHONPATH'] = f"{project_root}:{env['PYTHONPATH']}"
            else:
                env['PYTHONPATH'] = project_root
            
            # Create command for sending email
            cmd_parts = [
                python_executable,
                subprocess_path,
                "--credentials", f"@{credentials_path}",
                "--user_email", user,
                "--action", "send_email",
                "--to", to,
                "--subject", f"{subject}"
            ]
            
            # Add optional parameters
            if cc:
                if isinstance(cc, list):
                    cmd_parts.extend(["--cc", ",".join(cc)])
                else:
                    cmd_parts.extend(["--cc", cc])
            
            if bcc:
                if isinstance(bcc, list):
                    cmd_parts.extend(["--bcc", ",".join(bcc)])
                else:
                    cmd_parts.extend(["--bcc", bcc])
            
            # Content and HTML content need to be written to temporary files to avoid command line issues
            with tempfile.NamedTemporaryFile(mode='w+', delete=False) as content_file:
                content_path = content_file.name
                content_file.write(content)
            
            cmd_parts.extend(["--content", f"@{content_path}"])
            
            if html_content:
                with tempfile.NamedTemporaryFile(mode='w+', delete=False) as html_file:
                    html_path = html_file.name
                    html_file.write(html_content)
                cmd_parts.extend(["--html_content", f"@{html_path}"])
            
            # Create process
            cmd = " ".join(cmd_parts)
            #self.logger.info(f"Executing command: {cmd}")
            
            # Use asyncio.create_subprocess_exec for better security and argument handling
            process = await asyncio.create_subprocess_exec(
                *cmd_parts,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env  # Add the environment variables
            )
            
            # Set up concurrent readers for stdout and stderr
            async def read_stdout():
                data = await process.stdout.read()
                return data.decode('utf-8')
            
            async def read_stderr():
                data = await process.stderr.read()
                return data.decode('utf-8')
            
            # Wait for both readers
            stdout_data, stderr_data = await asyncio.gather(read_stdout(), read_stderr())
            
            # Wait for process to complete
            exit_code = await process.wait()
            
            # If process failed, raise error
            if exit_code != 0:
                error = stderr_data or f"Process exited with code {exit_code}"
                self.logger.error(f"Subprocess error: {error}")
                raise GmailAPIError(f"Subprocess error: {error}")
            
            # Fix JSON parsing by extracting just the JSON part from stdout
            try:
                # Try to find JSON in the output - look for the first '{' and last '}'
                json_start = stdout_data.find('{')
                json_end = stdout_data.rfind('}') + 1
                
                if json_start >= 0 and json_end > json_start:
                    json_str = stdout_data[json_start:json_end]
                    self.logger.debug(f"Extracted JSON: {json_str}")
                    result = json.loads(json_str)
                else:
                    self.logger.error(f"Could not find JSON in output: {stdout_data}")
                    raise GmailAPIError(f"Could not find JSON in subprocess output: {stdout_data[:100]}...")
            except json.JSONDecodeError as e:
                self.logger.error(f"JSON parsing error: {e}")
                self.logger.error(f"Raw output: {stdout_data}")
                raise GmailAPIError("Failed to parse subprocess output")
            except Exception as e:
                self.logger.error(f"Error processing subprocess output: {e}")
                self.logger.error(f"Stdout: {stdout_data}")
                self.logger.error(f"Stderr: {stderr_data}")
                raise GmailAPIError("Failed to parse subprocess output")
            
            # Check for success
            if result.get('success', False):
                self.logger.debug(f"Email sent successfully via Gmail API: {result.get('message_id')}")
                return result
            else:
                error = result.get('error', 'Unknown error')
                self.logger.error(f"Gmail API error: {error}")
                raise GmailAPIError(f"Failed to send email: {error}")
        
        finally:
            # Clean up temporary files
            if 'credentials_path' in locals():
                os.unlink(credentials_path)
            if 'content_path' in locals():
                os.unlink(content_path)
            if 'html_path' in locals() and html_content:
                os.unlink(html_path)
    
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
            
            # Force deep garbage collection
            for _ in range(3):
                gc.collect(generation=2)  # Force full collection including oldest generation
            
            # Run the Python garbage collector in a more aggressive way
            # This helps free memory that might be held in reference cycles
            import sys
            try:
                # Get a reference to all objects
                all_objects = gc.get_objects()
                
                # Clear any large string objects that might be lingering
                for obj in all_objects:
                    # Use a try-except block to catch any issues with accessing object lengths
                    try:
                        # Only check pure Python strings, not torch objects
                        if type(obj) is str and len(obj) > 10000:
                            # Large strings - set local references to None 
                            obj = None
                    except Exception:
                        # Skip any objects that cause errors when checking length
                        pass
                
                # Explicitly break reference cycles in these modules if used
                modules_to_clear = ['json', 'email', 'google.auth', 'googleapiclient', 'httplib2']
                for module_name in modules_to_clear:
                    if module_name in sys.modules:
                        mod = sys.modules[module_name]
                        if hasattr(mod, '_reset_caches'):
                            mod._reset_caches()  # For modules with explicit cache reset
                        
                        # For httplib2 - Clear connection caches
                        if module_name == 'httplib2' and hasattr(mod, 'Http'):
                            # Safely clean up httplib2 connections without requiring service object
                            http_class = mod.Http
                            for attr in dir(http_class):
                                if attr.startswith('_conn_') and hasattr(http_class, attr):
                                    setattr(http_class, attr, {})
                            
                            # Clear SCHEMES to prevent errors during cleanup
                            if hasattr(mod, 'SCHEMES'):
                                try:
                                    for scheme in list(mod.SCHEMES.keys()):
                                        mod.SCHEMES[scheme].clear()
                                except (AttributeError, TypeError):
                                    # If SCHEMES isn't a dict or doesn't have clear method
                                    pass
                
                # Clear all objects reference
                all_objects = None
            except Exception as e:
                self.logger.warning(f"Advanced memory cleanup failed: {e}")
            
            # Force additional garbage collection after reference cleanup
            for _ in range(3):
                gc.collect()
                
            log_memory_cleanup(self.logger, "After Gmail Subprocess Disconnect")
            self.logger.info("Gmail client subprocess disconnected and memory cleaned")
            
            # Import psutil for more aggressive cleanup if available
            try:
                import psutil
                process = psutil.Process()
                # Try to return memory to OS (Linux/MacOS)
                if hasattr(process, 'memory_maps'):
                    maps = process.memory_maps()
                    self.logger.debug(f"Memory maps count before cleanup: {len(maps)}")
                    
                # Python doesn't reliably release memory back to OS, but we can try
                # system-specific approaches like calling malloc_trim on Linux
                if sys.platform.startswith('linux'):
                    try:
                        import ctypes
                        ctypes.CDLL('libc.so.6').malloc_trim(0)
                        self.logger.debug("Called malloc_trim to release memory to OS")
                    except Exception as e:
                        self.logger.debug(f"malloc_trim failed: {e}")
            except ImportError:
                self.logger.debug("psutil not available for advanced memory management")
            except Exception as e:
                self.logger.debug(f"Advanced OS memory release failed: {e}")
                
            return True
        except Exception as e:
            self.logger.error(f"Error during disconnection: {e}")
            return False 