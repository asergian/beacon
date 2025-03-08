"""Logging utilities for the Gmail worker module.

This module provides utility functions for logging configuration and management.
"""

import logging
from typing import Optional

def get_logger(name: str = 'gmail_worker') -> logging.Logger:
    """Get a logger instance with the specified name.
    
    This provides a standardized way to get logger instances across the module.
    Ensures consistent logger naming throughout the Gmail worker.
    
    Args:
        name: str: Name for the logger, defaults to 'gmail_worker'. This will be
            used as the logger's identifier in the logging system.
        
    Returns:
        logging.Logger: Logger instance configured with the specified name.
            This logger will inherit any configuration (handlers, formatters,
            levels) from the logging system.
    """
    return logging.getLogger(name) 