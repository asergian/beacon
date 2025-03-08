"""Email processing metrics collection utilities.

This module provides functionality for collecting and reporting metrics related to 
email analysis operations, such as processing counts, cache usage, and timing information.
It helps monitor system performance and track email processing statistics.

TODO: This utility is currently unused. Consider integrating it with the email processing
pipeline to track performance metrics or moving it to app/utils if it could be useful
for other parts of the application.
"""

from typing import Dict
from datetime import timedelta

class MetricsCollector:
    """Collects and reports email processing metrics.
    
    This class provides methods to record and report various metrics related to
    email analysis operations, helping monitor system performance and resource usage.
    
    Attributes:
        client: The metrics client used to store and report metrics
    """
    
    def __init__(self, metrics_client):
        """Initialize the MetricsCollector with a metrics client.
        
        Args:
            metrics_client: Client object used to store and report metrics
        """
        self.client = metrics_client

    async def record_analysis(self, stats: Dict, duration: timedelta):
        """Record metrics for an email analysis operation.
        
        This method records various statistics about email processing,
        including counts of emails processed, cache hits, errors, and 
        the total operation duration.
        
        Args:
            stats: Dictionary containing statistics with keys:
                - processed: Number of emails processed
                - cached: Number of emails with cached results
                - errors: Number of errors encountered
            duration: Time taken to complete the analysis
        """
        await self.client.gauge("email_analysis.processed", stats["processed"])
        await self.client.gauge("email_analysis.cached", stats["cached"])
        await self.client.gauge("email_analysis.errors", stats["errors"])
        await self.client.timing("email_analysis.duration", duration.total_seconds()) 