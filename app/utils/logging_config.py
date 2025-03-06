"""
Logging utilities for the application.

This module provides logging configuration and utilities for the entire application,
including custom handlers, formatters, and configuration functions.
"""
import os
import logging
import logging.config
from typing import Any


class SafeStreamHandler(logging.StreamHandler):
    """A StreamHandler that safely handles string encoding.
    
    This handler ensures proper encoding when writing log messages to streams,
    preventing encoding-related errors.
    
    Args:
        None - inherits from logging.StreamHandler
    """
    def emit(self, record: logging.LogRecord) -> None:
        """Process and emit a log record with proper encoding.
        
        Args:
            record: The LogRecord to be emitted
            
        Returns:
            None
        """
        try:
            msg = self.format(record)
            stream = self.stream
            # Write with encoding if stream has encoding defined
            if hasattr(stream, 'encoding') and stream.encoding:
                stream.write(msg.encode(stream.encoding).decode(stream.encoding))
            else:
                stream.write(msg)
            stream.write(self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)


def configure_logging() -> None:
    """Configure application-wide logging.
    
    Sets up logging formatters, handlers, and loggers based on
    environment variables. Creates a custom log record factory
    to include shortened logger names.
    
    Returns:
        None
    """
    # Get the logging level from environment
    log_level = os.environ.get('LOGGING_LEVEL', 'ERROR').upper()
    
    logging.config.dictConfig({
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'standard': {
                'format': '%(asctime)s | %(shortname)-40s | %(levelname)-8s | %(message)s',
                'datefmt': '%H:%M:%S'
            },
            'operation': {
                'format': '%(asctime)s | %(shortname)-40s | %(levelname)-8s | %(message)s',
                'datefmt': '%H:%M:%S'
            }
        },
        'handlers': {
            'console': {
                'level': log_level,  # Use environment-specified level
                'formatter': 'standard',
                'class': 'app.utils.logging_config.SafeStreamHandler',
                'stream': 'ext://sys.stdout',
            },
            'operation': {
                'level': log_level,  # Use environment-specified level
                'formatter': 'operation',
                'class': 'app.utils.logging_config.SafeStreamHandler',
                'stream': 'ext://sys.stdout',
            }
        },
        'loggers': {
            '': {  # Root logger
                'handlers': ['console'],
                'level': log_level,  # Use environment-specified level
                'propagate': False
            },
            'httpx': {
                'handlers': ['console'],
                'level': 'WARNING',  # Changed from DEBUG to WARNING to reduce log verbosity
                'propagate': False
            },
            'app.email.pipeline': {
                'handlers': ['operation'],
                'level': log_level,  # Use environment-specified level
                'propagate': False
            },
            'app.email.storage.cache': {
                'handlers': ['console'],
                'level': log_level,  # Use environment-specified level
                'propagate': False
            },
            'app.email.core': {
                'handlers': ['console'],
                'level': log_level,  # Use environment-specified level
                'propagate': False
            },
            'app.email.analyzers': {
                'handlers': ['console'],
                'level': log_level,  # Use environment-specified level
                'propagate': False
            },
            'app.models': {
                'handlers': ['console'],
                'level': log_level,  # Use environment-specified level
                'propagate': False
            },
            'app.email.core.gmail_client': {
                'handlers': ['console'],
                'level': log_level,  # Use environment-specified level
                'propagate': False
            }
        }
    })

    # Patch the logger to add `shortname`
    old_factory = logging.getLogRecordFactory()

    def record_factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
        """Create a LogRecord with a shortname attribute.
        
        Args:
            *args: Variable length argument list passed to the original factory
            **kwargs: Arbitrary keyword arguments passed to the original factory
            
        Returns:
            A LogRecord with the shortname attribute added
        """
        record = old_factory(*args, **kwargs)
        parts = record.name.split(".")
        
        if len(parts) > 3:  # If the logger name is long
            record.shortname = f"{'.'.join(parts[-2:])}"
        else:
            record.shortname = record.name  # Keep full name if short enough
        return record

    logging.setLogRecordFactory(record_factory)


def format_log_message(msg: str, wrap_length: int = 100) -> str:
    """Format a log message with proper wrapping.
    
    Wraps long log messages to improve readability in log output.
    
    Args:
        msg: The message to format
        wrap_length: Maximum line length before wrapping
        
    Returns:
        The formatted message with line breaks as needed
    """
    if len(msg) <= wrap_length:
        return msg
        
    words = msg.split()
    lines = []
    current_line = []
    current_length = 0
    
    for word in words:
        if current_length + len(word) + 1 <= wrap_length:
            current_line.append(word)
            current_length += len(word) + 1
        else:
            if current_line:
                lines.append(' '.join(current_line))
            current_line = [word]
            current_length = len(word)
            
    if current_line:
        lines.append(' '.join(current_line))
        
    return '\n    '.join(lines)  # Indent continuation lines