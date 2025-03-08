"""Gmail worker process module.

This module provides a separate process implementation for Gmail API operations,
isolating memory-intensive API calls from the main application process.

The worker runs in a separate process and communicates with the main application
through JSON-serialized data, ensuring clean memory separation between the Gmail API
operations and the application server.

Typical usage example:
    # From the main application:
    from app.email.clients.gmail.client import GmailClient
    
    client = GmailClient(credentials_json)
    emails = await client.fetch_emails("is:unread", max_results=100)

    # This internally spawns the worker process:
    # subprocess.Popen(['python', '-m', 'app.email.clients.gmail.worker.main', ...])

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

# Expose key components at the package level
from .api_client import GmailService
from .email_parser import process_message

# Version information
__version__ = '1.0.0'

__all__ = [
    'GmailService',
    'process_message'
] 