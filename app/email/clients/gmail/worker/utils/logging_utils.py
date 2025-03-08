"""Logging utilities for the Gmail worker module.

This module provides utility functions for logging configuration and management.
"""

import logging
from typing import Optional

def get_logger(name: str = 'gmail_worker') -> logging.Logger:
    """Get a logger instance with the specified name.
    
    This provides a standardized way to get logger instances across the module.
    
    Args:
        name: Name for the logger, defaults to 'gmail_worker'
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name) 