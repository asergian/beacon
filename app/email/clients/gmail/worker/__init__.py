"""Gmail worker package for memory-isolated email processing.

This package provides modules for fetching and processing emails from 
the Gmail API in a separate process to isolate memory-intensive operations.

The Gmail worker package is designed as a standalone process that can be
invoked by the main application to handle memory-intensive email operations
in isolation. This approach prevents memory leaks and excessive resource
consumption from affecting the main application.

Modules:
    api_client.py: Gmail API client implementation with batching and memory optimization
    email_parser.py: Functions for parsing and decoding email content
    main.py: Command-line interface and execution entry point
    utils/: Utility modules for supporting functions
        - date_utils.py: Date/time handling and timezone conversions
        - file_utils.py: File input/output operations
        - logging_utils.py: Standardized logging configuration
        - memory_management.py: Memory tracking and optimization
        - processing_utils.py: Email filtering and processing

Key Features:
    - Process isolation for memory containment
    - Efficient email batch processing
    - Robust error handling and recovery
    - Memory usage monitoring
    - Timeout protection
    - Standardized JSON communication protocol
"""

# Ensure the project root is in the Python path
import os
import sys

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../../'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Version information
__version__ = '1.0.0' 