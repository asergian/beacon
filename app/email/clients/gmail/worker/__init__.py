"""Gmail worker package for memory-isolated email processing.

This package provides modules for fetching and processing emails from 
the Gmail API in a separate process to isolate memory-intensive operations.
"""

# Ensure the project root is in the Python path
import os
import sys

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../../'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Version information
__version__ = '1.0.0' 