"""Gmail client that uses a subprocess for memory isolation.

This module provides a Gmail client that uses a subprocess to fetch and decode
emails, which isolates the memory-intensive operations from the main process.
"""

import asyncio
import json
import logging
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from typing import Dict, List
import time

from flask import session
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as AuthRequest

from app.utils.memory_utils import log_memory_usage, log_memory_cleanup
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
            
            # Perform garbage collection before starting subprocess
            gc.collect()
            
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
            
            # Release byte buffers
            stdout_bytes = None
            stderr_bytes = None
            
            # Perform garbage collection after subprocess completes
            gc.collect()
            
            # Only log stderr as error if process return code indicates failure
            # Otherwise forward subprocess logs at INFO level
            if process.returncode != 0:
                self.logger.error(f"Subprocess error: {stderr}")
                raise GmailAPIError(f"Gmail subprocess failed with code {process.returncode}: {stderr}")
            elif stderr:
                # Process and format subprocess logs for better readability
                log_lines = stderr.strip().split('\n')
                
                # Create a summary section with key metrics only
                metrics = {
                    'emails_found': None,
                    'emails_retrieved': None,
                    'start_memory': None,
                    'peak_memory': None,
                    'end_memory': None,
                    'raw_data_size': None
                }
                
                # Parse each line and log individually with proper formatting
                for line in log_lines:
                    if not line.strip():
                        continue
                        
                    # Extract metrics for summary while also logging each line
                    log_parts = line.split(' - ', 2)  # Split into timestamp, module, message
                    
                    if len(log_parts) >= 3:
                        # Extract the timestamp and message parts
                        timestamp, module, message = log_parts
                        
                        # Log each subprocess line with proper context
                        if "ERROR" in line or "ERROR" in module:
                            self.logger.error(f"Subprocess: [{module}] {message}")
                        elif "WARNING" in line or "WARNING" in module:
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
                        self.logger.debug(f"Subprocess: {line}")  # Changed to debug level
                
                # Log a concise summary of key metrics
                if any(v is not None for v in metrics.values()):
                    memory_change = ""
                    if metrics['start_memory'] and metrics['peak_memory']:
                        memory_increase = metrics['peak_memory'] - metrics['start_memory']
                        memory_change = f", Memory +{memory_increase:.1f}MB"
                        
                    raw_data_info = ""
                    if metrics['raw_data_size'] is not None:
                        raw_data_info = f", Raw data: {metrics['raw_data_size']:.2f}MB"
                        
                    self.logger.info(
                        f"Subprocess summary: Found {metrics['emails_found'] or '?'} emails, "
                        f"Retrieved {metrics['emails_retrieved'] or '?'} emails{memory_change}{raw_data_info}"
                    )
                
                # Clear log data
                log_lines = None
                metrics = None
            
            # Force garbage collection before JSON parsing
            gc.collect()
            
            try:
                # After deserializing but before filtering
                # Process raw_message data - decompress if compressed
                log_memory_usage(self.logger, "Before JSON Deserialization")
                result = json.loads(stdout)
                
                # Free up the stdout memory immediately
                stdout = None
                
                # Extract emails from result - the subprocess returns {'success': bool, 'emails': []}
                emails_to_process = result.get("emails", [])
                
                # Clear the result object to free memory
                result = None
                
                if not isinstance(emails_to_process, list):
                    self.logger.error(f"Unexpected result format from subprocess: {type(emails_to_process)}")
                    raise GmailAPIError(f"Invalid email data format: expected list, got {type(emails_to_process)}")
                
                self.logger.info(f"Deserialized {len(emails_to_process)} emails from subprocess")
                log_memory_usage(self.logger, "After JSON Deserialization")
                
                # Import gzip module here to ensure it's available in this scope
                import gzip
                
                # Track memory usage before and after decompression
                decompression_count = 0
                log_memory_usage(self.logger, "Before Email Decompression")
                decompression_start_time = time.time()
                
                # Process in smaller batches to manage memory better
                batch_size = 10
                email_batches = [emails_to_process[i:i+batch_size] for i in range(0, len(emails_to_process), batch_size)]
                
                # Clear the full list to free memory
                emails_to_process_total = len(emails_to_process)
                emails_to_process = None
                
                # Process each batch of emails
                all_processed_emails = []
                
                for batch_idx, email_batch in enumerate(email_batches):
                    for email in email_batch:
                        if email.get('raw_message') and isinstance(email.get('raw_message'), str):
                            # Check if this is compressed data (it will start with specific prefix)
                            if email['raw_message'].startswith('COMPRESSED:'):
                                try:
                                    decompression_count += 1
                                    # Remove the prefix and decode base64
                                    compressed_data = base64.b64decode(email['raw_message'][11:])
                                    # Store original compressed size for logging
                                    compressed_size = len(compressed_data)
                                    # Decompress
                                    email['raw_message'] = gzip.decompress(compressed_data)
                                    # Log decompression ratio
                                    original_size = len(email['raw_message'])
                                    ratio = (original_size - compressed_size) / original_size * 100 if original_size > 0 else 0
                                    
                                    if decompression_count <= 2:  # Only log details for first few emails
                                        self.logger.debug(
                                            f"Decompressed email {email['id']}: "
                                            f"{compressed_size/1024:.1f}KB → {original_size/1024:.1f}KB "
                                            f"(saved {ratio:.1f}%)"
                                        )
                                    
                                    # Explicitly delete compressed data to free memory immediately
                                    del compressed_data
                                except Exception as e:
                                    self.logger.error(f"Failed to decompress email data: {e}")
                                    email['raw_message'] = None
                    
                    # Append processed batch to results
                    all_processed_emails.extend(email_batch)
                    
                    # Clear batch reference and force GC
                    email_batch = None
                    if (batch_idx + 1) % 2 == 0:
                        log_memory_cleanup(self.logger, f"After decompressing batch {batch_idx+1}/{len(email_batches)}")
                
                decompression_time = time.time() - decompression_start_time
                self.logger.info(f"Decompression completed in {decompression_time:.2f} seconds for {emails_to_process_total} emails")
                
                # Force garbage collection after decompression
                log_memory_cleanup(self.logger, "After Email Decompression")
                if decompression_count > 0:
                    self.logger.info(f"Decompressed {decompression_count} emails")
                
                # Continue with filtering and post-processing
                log_memory_usage(self.logger, "Before Email Filtering")
                
                filtered_emails = []
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
                
                # Process the emails in batches
                email_batches = [all_processed_emails[i:i+batch_size] for i in range(0, len(all_processed_emails), batch_size)]
                all_processed_emails = None  # Clear full list
                
                self.logger.debug(f"Timezone: {datetime.now().astimezone().tzinfo}")
                self.logger.debug(f"Adjusted days: {adjusted_days if 'adjusted_days' in locals() else 'N/A'}")
                if local_midnight_cutoff:
                    self.logger.debug(f"Local midnight cutoff: {local_midnight_cutoff}")
                
                # Process each batch to reduce memory pressure
                for batch_idx, email_batch in enumerate(email_batches):
                    batch_filtered = []
                    
                    for email in email_batch:
                        # Process raw_message regardless of current type
                        if 'raw_message' in email:
                            try:
                                # Handle string raw_message (base64 encoded, not yet decompressed)
                                if isinstance(email['raw_message'], str):
                                    # Only non-compressed strings need base64 decoding
                                    # Compressed strings were already handled in the decompression loop
                                    if not email['raw_message'].startswith('COMPRESSED:'):
                                        raw_msg = base64.b64decode(email['raw_message'])
                                        email['raw_message'] = raw_msg
                                        del raw_msg  # Explicitly free memory
                                
                                # Now extract headers if we have bytes (either from decompression or base64 decoding)
                                if isinstance(email['raw_message'], bytes):
                                    # Extract headers from the message bytes
                                    email_msg = message_from_bytes(email['raw_message'])
                                    
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
                                            # Parse email date
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
                                                batch_filtered.append(email)
                                                # Clear references to large objects to free memory
                                                email_msg = None
                                                continue
                                            
                                            if not email_date:
                                                # Skip emails with unparseable dates
                                                self.logger.warning(f"Couldn't parse date: {date_str}")
                                                # Still include the email
                                                batch_filtered.append(email)
                                                # Clear references to large objects to free memory
                                                email_msg = None
                                                continue
                                            
                                            # Convert to local timezone for comparison
                                            local_email_date = email_date.astimezone(local_tz)
                                            
                                            # Only include emails at or after our local midnight cutoff
                                            if local_email_date >= local_midnight_cutoff:
                                                batch_filtered.append(email)
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
                                            batch_filtered.append(email)
                                    else:
                                        # No filtering needed, include the email
                                        batch_filtered.append(email)
                                    
                                    # Clear reference to parsed email message - critical for memory!
                                    email_msg = None
                                else:
                                    # If we don't have bytes after processing, include as is
                                    self.logger.warning(f"Email {email.get('id', 'unknown')} has non-bytes raw_message after processing")
                                    batch_filtered.append(email)
                            except Exception as e:
                                self.logger.error(f"Failed to process raw_message: {e}")
                                # If processing fails, set to None to avoid parsing errors
                                email['raw_message'] = None
                                # Still include the email with the error
                                batch_filtered.append(email)
                        else:
                            # No raw message to process, include as is
                            self.logger.debug(f"Email {email.get('id', 'unknown')} has no raw_message")
                            batch_filtered.append(email)
                    
                    # Add filtered emails from this batch
                    filtered_emails.extend(batch_filtered)
                    batch_filtered = None
                    
                    # Every few batches, force cleanup
                    if (batch_idx + 1) % 2 == 0 or batch_idx == len(email_batches) - 1:
                        log_memory_cleanup(self.logger, f"After filtering batch {batch_idx+1}/{len(email_batches)}")
                
                # Force garbage collection after processing all emails
                email_batches = None
                log_memory_cleanup(self.logger, "After Email Filtering")
                
                # Calculate and log the total size of raw message data
                total_raw_size = sum(len(email.get('raw_message', b'')) for email in filtered_emails if email.get('raw_message') is not None)
                self.logger.info(f"Total size of raw message data: {total_raw_size / 1024 / 1024:.2f} MB")
                
                # Calculate memory usage per email to identify potential issues
                avg_size_per_email = total_raw_size / len(filtered_emails) if filtered_emails else 0
                self.logger.info(f"Average raw message size: {avg_size_per_email / 1024:.1f} KB per email")
                
                # Memory profiling before detailed processing
                log_memory_usage(self.logger, "Before Email Sample Analysis")
                
                # Calculate compressed size benefits if any
                try:
                    # Take a representative sample of emails for calculation
                    sample_count = min(5, len(filtered_emails))
                    if sample_count > 0:
                        compression_samples = filtered_emails[:sample_count]
                        compressed_sizes = []
                        original_sizes = []
                        
                        for sample in compression_samples:
                            if isinstance(sample.get('raw_message'), bytes):
                                original_size = len(sample['raw_message'])
                                compressed = gzip.compress(sample['raw_message'], compresslevel=6)
                                compressed_size = len(compressed)
                                
                                original_sizes.append(original_size)
                                compressed_sizes.append(compressed_size)
                                
                                # Explicitly release compressed data
                                del compressed
                        
                        if original_sizes:
                            total_original = sum(original_sizes)
                            total_compressed = sum(compressed_sizes)
                            ratio = (total_original - total_compressed) / total_original * 100 if total_original > 0 else 0
                            
                            self.logger.info(f"Compression analysis (sample of {sample_count} emails):")
                            self.logger.info(f"  Original: {total_original/1024:.1f}KB, Compressed: {total_compressed/1024:.1f}KB")
                            self.logger.info(f"  Compression ratio: {ratio:.1f}%, Memory saved: {(total_original-total_compressed)/1024/1024:.2f}MB")
                        
                        # Clear sample data
                        compression_samples = None
                        original_sizes = None
                        compressed_sizes = None
                except Exception as e:
                    self.logger.debug(f"Error calculating compression stats: {e}")
                
                if local_midnight_cutoff:
                    self.logger.info(
                        f"Fetched {emails_to_process_total} emails from Gmail API, filtered to {len(filtered_emails)} "
                        f"(filtered out {filtered_out} before {local_midnight_cutoff.strftime('%Y-%m-%d %H:%M:%S')})"
                    )
                else:
                    self.logger.info(f"Fetched {len(filtered_emails)} emails from Gmail API for {user}")
                
                # Log memory usage after all processing
                log_memory_usage(self.logger, "After Email Processing - Main Process")
                
                # Force garbage collection before returning to minimize memory footprint
                log_memory_cleanup(self.logger, "Before Optimization")
                
                # Optimize memory: clear fields not needed for processing to reduce RAM usage
                optimized_emails = []
                fields_to_keep = {'id', 'threadId', 'labelIds', 'raw_message', 'Message-ID', 'subject', 'from', 'to', 'date'}
                
                # Process in batches to avoid large memory allocation
                email_batches = [filtered_emails[i:i+batch_size] for i in range(0, len(filtered_emails), batch_size)]
                filtered_emails = None  # Clear the original list
                
                for batch_idx, email_batch in enumerate(email_batches):
                    for email in email_batch:
                        # Create slimmer dict with only necessary fields
                        optimized = {k: v for k, v in email.items() if k in fields_to_keep}
                        optimized_emails.append(optimized)
                    
                    # Free batch memory
                    email_batch = None
                    
                    # Force cleanup every few batches
                    if (batch_idx + 1) % 3 == 0 or batch_idx == len(email_batches) - 1:
                        log_memory_cleanup(self.logger, f"After optimizing batch {batch_idx+1}/{len(email_batches)}")
                
                # Clear reference to the email batches
                email_batches = None
                
                # Force final garbage collection 
                log_memory_cleanup(self.logger, "Before Returning Email Data")
                
                return optimized_emails
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse subprocess output: {e}")
                self.logger.debug(f"Subprocess output: {stdout[:500]}...")
                raise GmailAPIError(f"Failed to parse subprocess output: {e}")
                
        except Exception as e:
            self.logger.error(f"Error in fetch_emails: {str(e)}")
            raise
        finally:
            # Remove temp credentials file
            if credentials_path:
                try:
                    os.unlink(credentials_path)
                    self.logger.debug("Removed temporary credentials file")
                except Exception as e:
                    self.logger.warning(f"Failed to remove temporary credentials file: {e}")
            
            # Explicitly close process if still running
            try:
                if 'process' in locals() and process and process.returncode is None:
                    process.terminate()
                    self.logger.debug("Terminated subprocess")
            except Exception as e:
                self.logger.debug(f"Error terminating subprocess: {e}")
            
            # Final garbage collection
            try:
                gc.collect()
                gc.collect()
            except Exception:
                pass
                
            # Log memory usage after all operations
            log_memory_usage(self.logger, "After Gmail Client Subprocess - Main Process")
    
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