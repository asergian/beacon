"""
Email Utilities Package.

This package contains various utility modules for handling email-related operations.

Modules:
- priority_scorer: Contains logic for scoring email priorities.
- rate_limiter: Implements rate limiting for email operations.
- pipeline_stats: Collects and manages statistics related to email processing pipelines.
- message_id_cleaner: Provides functionality for cleaning and formatting message IDs.

TODO:
- Implement additional features in the following modules:
    - pipeline_stats: Enhance metrics collection and reporting.
    - rate_limiter: Improve rate limiting logic and handling.

Used in the app:
- priority_scorer: Actively used for determining email priority in processing.
- message_id_cleaner: Utilized for ensuring message IDs are properly formatted.
"""

from .priority_scorer import *
from .rate_limiter import *
from .pipeline_stats import *
from .message_id_cleaner import *

__all__ = [
    'priority_scorer',
    'rate_limiter',
    'pipeline_stats',
    'message_id_cleaner'
]