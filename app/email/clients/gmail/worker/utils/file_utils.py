"""File utility functions for the Gmail worker module.

This module provides utility functions for handling file operations.
"""

import logging
import os

# Set up logger for this module
logger = logging.getLogger('gmail_worker')


def parse_content_from_file(content_path: str) -> str:
    """Parse content from a file path.
    
    Args:
        content_path: Path to the file with @ prefix
        
    Returns:
        File contents as string
    """
    if content_path and content_path.startswith("@"):
        # Read content from file
        file_path = content_path[1:]
        with open(file_path, 'r') as f:
            return f.read()
    return content_path 