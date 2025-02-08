"""Analysis command model for email processing."""

from dataclasses import dataclass
from typing import List, Optional

@dataclass
class AnalysisCommand:
    """Command object for configuring email analysis.
    
    Attributes:
        days_back: Number of days to fetch emails for (1 = today, 2 = today and yesterday, etc.)
        cache_duration_days: Number of days to keep emails in cache (1 = last 24 hours)
        batch_size: Optional batch size for processing
        priority_threshold: Optional minimum priority level to include
        categories: Optional list of categories to include
    """
    days_back: int = 1  # Default to today only
    cache_duration_days: int = 7
    batch_size: Optional[int] = None
    priority_threshold: Optional[float] = None
    categories: Optional[List[str]] = None 