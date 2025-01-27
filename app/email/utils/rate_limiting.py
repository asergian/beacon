import asyncio
from datetime import datetime, timedelta

class RateLimiter:
    """Rate limits API calls"""
    
    def __init__(self, calls_per_minute: int = 60):
        self.calls_per_minute = calls_per_minute
        self.calls = []
        self._lock = asyncio.Lock()

    async def acquire(self):
        async with self._lock:
            now = datetime.now()
            self.calls = [t for t in self.calls if now - t < timedelta(minutes=1)]
            
            if len(self.calls) >= self.calls_per_minute:
                wait_time = 60 - (now - self.calls[0]).total_seconds()
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
            
            self.calls.append(now) 