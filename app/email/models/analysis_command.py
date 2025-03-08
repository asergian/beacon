"""Analysis command model for email processing.

This module contains the AnalysisCommand dataclass which is used to configure
parameters for email analysis operations.
"""

from dataclasses import dataclass
from typing import List, Optional

@dataclass
class AnalysisCommand:
    """Command object for configuring email analysis operations.
    
    This class is used to pass configuration parameters to the email analysis
    pipeline and control aspects like time range, caching behavior, and filtering.
    
    Attributes:
        days_back: Number of days to fetch emails for (1 = today, 2 = today and yesterday, etc.)
        cache_duration_days: Number of days to keep emails in cache
        batch_size: Optional maximum number of emails to process in a batch
        priority_threshold: Optional minimum priority level to include in results
        categories: Optional list of categories to filter results by
    """
    days_back: int = 1  # Default to today only
    cache_duration_days: int = 7
    batch_size: Optional[int] = None
    priority_threshold: Optional[float] = None
    categories: Optional[List[str]] = None 