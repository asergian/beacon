"""Analysis command model for email processing."""

from dataclasses import dataclass
from typing import List, Optional

@dataclass
class AnalysisCommand:
    """Represents a request to analyze emails"""
    days_back: int
    cache_duration_days: int
    batch_size: Optional[int] = None
    priority_threshold: Optional[int] = None
    categories: Optional[List[str]] = None 