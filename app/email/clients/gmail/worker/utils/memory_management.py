"""Memory management utilities for Gmail worker process.

This module provides functions for tracking and optimizing memory usage
in the Gmail worker process.
"""

import gc
import logging
import os
import socket
from typing import Optional

from .logging_utils import get_logger

# Configure garbage collection for better memory management
gc.set_threshold(700, 10, 5)  # More aggressive than default (700, 10, 10)

# Set lower connection timeout for faster failure/retry
socket.setdefaulttimeout(10)  # 10 seconds instead of default 60


def get_process_memory() -> int:
    """Get the current memory usage of the process in MB.
    
    Returns:
        Current memory usage in MB or 0 if unavailable.
    """
    try:
        # Try to get memory usage using ps command
        return int(os.popen(f'ps -p {os.getpid()} -o rss=').read().strip()) // 1024
    except Exception:
        return 0


def log_memory_usage(logger: Optional[logging.Logger] = None, 
                     label_or_message: str = "Current") -> int:
    """Log current memory usage with a label.
    
    Args:
        logger: Logger instance to use
        label_or_message: Label or message to identify the log entry
        
    Returns:
        Current memory usage in MB
    """
    try:
        # Get process memory usage in KB and MB
        memory_kb = os.popen(f'ps -p {os.getpid()} -o rss=').read().strip()
        memory_mb = int(memory_kb) // 1024
        
        if logger:
            logger.info(f"{label_or_message} memory usage: {memory_kb} KB ({memory_mb} MB)")
        
        return memory_mb
    except Exception as e:
        if logger:
            logger.warning(f"Could not get memory usage: {e}")
        return 0


def log_memory_cleanup(logger: Optional[logging.Logger] = None, 
                      label_or_message: str = "After cleanup") -> None:
    """Force garbage collection and log memory usage.
    
    Args:
        logger: Logger instance to use
        label_or_message: Label or message to identify the log entry
    """
    try:
        # Log memory before collection
        if logger:
            log_memory_usage(logger, f"{label_or_message} (before GC)")
        
        # Force garbage collection
        collected = gc.collect()
        if logger:
            logger.info(f"Garbage collection collected {collected} objects")
        
        # Run twice for better cleanup
        gc.collect()
        
        # Log memory after collection
        if logger:
            log_memory_usage(logger, f"{label_or_message} (after GC)")
    except Exception as e:
        if logger:
            logger.warning(f"Error during memory cleanup: {e}")


# Global tracking variables
TOTAL_PROCESSED_BYTES = 0
EMAILS_PROCESSED = 0
MAX_EMAIL_SIZE = 0


def track_email_processing(email_size: int) -> None:
    """Track email processing statistics.
    
    Args:
        email_size: Size of the email in bytes
    """
    global TOTAL_PROCESSED_BYTES, EMAILS_PROCESSED, MAX_EMAIL_SIZE
    
    TOTAL_PROCESSED_BYTES += email_size
    EMAILS_PROCESSED += 1
    MAX_EMAIL_SIZE = max(MAX_EMAIL_SIZE, email_size)


def get_processing_stats() -> dict:
    """Get the current email processing statistics.
    
    Retrieves statistics about email processing including total bytes processed,
    number of emails processed, maximum email size, and current memory usage.
    
    Returns:
        dict: Dictionary with processing statistics containing the following keys:
            - total_bytes: Total bytes processed
            - emails_processed: Number of emails processed
            - max_email_size: Size of the largest email processed
            - current_memory: Current memory usage in MB
    """
    return {
        "total_bytes": TOTAL_PROCESSED_BYTES,
        "emails_processed": EMAILS_PROCESSED,
        "max_email_size": MAX_EMAIL_SIZE,
        "current_memory": get_process_memory()
    }


def cleanup_resources(logger: Optional[logging.Logger] = None) -> None:
    """Clean up all resources before exiting the process.
    
    This function performs a thorough cleanup of various resources:
    - Forces garbage collection
    - Closes httplib2 connections
    - Resets HTTP connection pools
    - Frees Google API client instances
    - Logs final memory usage
    
    Args:
        logger: Logger instance to use
    """
    if logger is None:
        logger = get_logger('gmail_worker')
        
    try:
        # Force final garbage collection
        gc.collect()
        gc.collect()
        
        # Close any remaining httplib2 connections - safely check for attributes first
        try:
            # Check if httplib2 exists and has SCHEMES attribute
            import httplib2
            if hasattr(httplib2, 'SCHEMES') and httplib2.SCHEMES:
                for scheme, conn in httplib2.SCHEMES.items():
                    if hasattr(conn, 'connections'):
                        conn.connections.clear()
                        logger.debug(f"Cleared {scheme} connections")
            
            # For open HTTP connections
            if hasattr(httplib2, 'Http'):
                for attr in dir(httplib2.Http):
                    if attr.startswith('_conn_') and hasattr(httplib2.Http, attr):
                        setattr(httplib2.Http, attr, {})
                        logger.debug(f"Reset httplib2.Http.{attr}")
        except Exception as e:
            logger.warning(f"Could not clean httplib2 connections: {e}")
            
        # Attempt to free the Google API client
        try:
            import sys
            # Access any 'service' variable in the caller's globals
            frame = sys._getframe(1)
            caller_globals = frame.f_globals
            service_vars = [var for var in caller_globals if 'service' in var and isinstance(caller_globals[var], object)]
            for var_name in service_vars:
                service_obj = caller_globals[var_name]
                if hasattr(service_obj, '_http') and service_obj._http:
                    # Close any http connections
                    if hasattr(service_obj._http, 'close'):
                        service_obj._http.close()
                # Set to None to free reference
                caller_globals[var_name] = None
                logger.debug(f"Freed service reference: {var_name}")
        except Exception as e:
            logger.warning(f"Error cleaning up Google API service: {e}")
        
        # Log final memory usage
        logger.info(f"Final memory usage before exit: {os.popen(f'ps -p {os.getpid()} -o rss=').read().strip()} KB")
    except Exception as e:
        logger.error(f"Error during final cleanup: {e}") 