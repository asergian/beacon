"""Utilities package for Gmail client.

This package provides utility functions for the Gmail client module
to handle subprocess operations, file management, and error handling.
"""

from .subprocess_utils import (
    GmailAPIError,
    run_subprocess,
    parse_json_response,
    handle_subprocess_result,
    build_command
)
from .file_utils import TempFileManager
from .date_utils import calculate_date_cutoff

__all__ = [
    # Exceptions
    'GmailAPIError',
    
    # Subprocess utilities
    'run_subprocess',
    'parse_json_response',
    'handle_subprocess_result',
    'build_command',
    
    # File utilities
    'TempFileManager',
    
    # Date utilities
    'calculate_date_cutoff'
] 