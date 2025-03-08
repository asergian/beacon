"""File utility functions for the Gmail worker module.

This module provides utility functions for handling file operations.
"""

import logging
import os

# Set up logger for this module
logger = logging.getLogger('gmail_worker')


def parse_content_from_file(content_path: str) -> str:
    """Parse content from a file path.
    
    Reads content from a file if the provided path starts with '@',
    otherwise returns the path itself. This allows flexible content handling
    where content can be provided directly or referenced from a file.
    
    Args:
        content_path: str: Path to the file with @ prefix (e.g., "@/path/to/file.txt")
            or the content itself if no @ prefix.
        
    Returns:
        str: File contents as string if content_path starts with '@', 
            otherwise returns content_path unchanged.
            
    Raises:
        IOError: If the file cannot be read (not explicitly caught)
    """
    if content_path and content_path.startswith("@"):
        # Read content from file
        file_path = content_path[1:]
        with open(file_path, 'r') as f:
            return f.read()
    return content_path 