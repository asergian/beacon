"""Email pipeline helper functions.

This package contains helper functions for the email pipeline orchestrator,
organized by functionality:

- context: User context setup and validation
- fetching: Email and cache fetching operations
- processing: Email processing and analysis functions
- stats: Statistics tracking and reporting functions

These modules help keep the main orchestrator code clean and maintainable
by separating concerns and responsibilities.
"""

from app.email.pipeline.helpers.context import setup_user_context
from app.email.pipeline.helpers.fetching import (
    send_cache_status,
    fetch_cached_emails,
    fetch_emails_from_gmail,
    filter_cached_emails
)
from app.email.pipeline.helpers.processing import (
    process_without_ai,
    process_in_batches,
    process_batch_results,
    process_all_at_once,
    apply_filters
)
from app.email.pipeline.helpers.stats import (
    generate_final_stats,
    log_activity
)

__all__ = [
    # Context
    'setup_user_context',
    # Fetching
    'send_cache_status',
    'fetch_cached_emails',
    'fetch_emails_from_gmail',
    'filter_cached_emails',
    # Processing
    'process_without_ai',
    'process_in_batches',
    'process_batch_results',
    'process_all_at_once',
    'apply_filters',
    # Stats
    'generate_final_stats',
    'log_activity'
]
