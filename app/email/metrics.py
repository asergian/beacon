from typing import Dict
from datetime import timedelta

class MetricsCollector:
    """Collects and reports metrics"""
    
    def __init__(self, metrics_client):
        self.client = metrics_client

    async def record_analysis(self, stats: Dict, duration: timedelta):
        await self.client.gauge("email_analysis.processed", stats["processed"])
        await self.client.gauge("email_analysis.cached", stats["cached"])
        await self.client.gauge("email_analysis.errors", stats["errors"])
        await self.client.timing("email_analysis.duration", duration.total_seconds()) 