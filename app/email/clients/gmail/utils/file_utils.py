"""File utility functions for the Gmail client.

This module provides utilities for file management, particularly
temporary files used in Gmail API client operations.
"""

import os
import tempfile
from typing import Optional, List


class TempFileManager:
    """Context manager for handling temporary files.
    
    This class manages a set of temporary files and ensures they're all
    cleaned up when the context is exited, even if an exception occurs.
    """
    
    def __init__(self, logger=None):
        """Initialize with an optional logger.
        
        Args:
            logger: Optional logger instance for reporting file operations
        """
        self.files: List[str] = []
        self.logger = logger
        
    def __enter__(self):
        """Enter the context manager.
        
        Returns:
            self: The context manager instance
        """
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the context manager and clean up all files.
        
        Args:
            exc_type: Exception type if an exception occurred
            exc_val: Exception value if an exception occurred
            exc_tb: Exception traceback if an exception occurred
            
        Returns:
            bool: False to allow exceptions to propagate
        """
        for file_path in self.files:
            if os.path.exists(file_path):
                try:
                    os.unlink(file_path)
                except Exception as e:
                    if self.logger:
                        self.logger.warning(f"Error removing temporary file {file_path}: {e}")
        
        # Don't suppress exceptions
        return False
        
    def create_file(self, content=None, suffix=None):
        """Create a temporary file with optional content.
        
        Args:
            content: Optional content to write to the file
            suffix: Optional file suffix
            
        Returns:
            str: Path to the temporary file
        """
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix=suffix) as f:
            file_path = f.name
            if content:
                f.write(content)
            self.files.append(file_path)
            return file_path 