# Email Utilities Module

The Email Utilities module provides shared helper functions specifically for email processing operations.

## Overview

This module contains utility functions and classes that support various aspects of email processing. These utilities handle specialized tasks like message ID cleaning, priority scoring, rate limiting, and pipeline statistics tracking. They are used throughout the email module to implement common functionality in a consistent way.

## Directory Structure

```
utils/
├── __init__.py             # Package exports
├── message_id_cleaner.py   # Message ID normalization
├── pipeline_stats.py       # Processing statistics tracking
├── priority_scorer.py      # Email priority calculation
├── rate_limiter.py         # API rate limiting
└── README.md               # This documentation
```

## Components

### Message ID Cleaner
Utility for cleaning and normalizing email message IDs to ensure consistent identification regardless of format variations.

### Pipeline Statistics
Tools for tracking and reporting on email processing statistics, including volume, processing time, and success rates.

### Priority Scorer
Implements the email priority scoring algorithm, considering factors like sender importance, content analysis, and time sensitivity to determine email priority.

### Rate Limiter
Provides rate limiting functionality to manage API request rates, particularly for external services like the Gmail API and OpenAI.

## Usage Examples

```python
# Using the priority scorer
from app.email.utils.priority_scorer import PriorityScorer

scorer = PriorityScorer()
priority = scorer.calculate_priority(
    sender="important@example.com",
    subject="Urgent: Project deadline",
    content_analysis={
        "urgency": 0.8,
        "importance": 0.7,
        "entities": ["project", "deadline"]
    },
    date_received="2023-05-15T09:00:00Z"
)
print(f"Email priority score: {priority}")  # 0-100 score

# Using pipeline statistics
from app.email.utils.pipeline_stats import PipelineStats

stats = PipelineStats()
stats.start_processing()

# ... perform processing ...

stats.record_email_processed(successful=True)
stats.record_email_processed(successful=False)
stats.finish_processing()

print(f"Total processed: {stats.total_processed}")
print(f"Success rate: {stats.success_rate}%")
print(f"Processing time: {stats.processing_time_seconds}s")

# Using rate limiter
from app.email.utils.rate_limiter import RateLimiter

limiter = RateLimiter(max_requests=60, time_window=60)  # 60 requests per minute
if await limiter.can_proceed("api_calls"):
    # Make API call
    await limiter.record_request("api_calls")
else:
    # Handle rate limit exceeded
    wait_time = await limiter.get_wait_time("api_calls")
    print(f"Rate limit exceeded. Try again in {wait_time} seconds")
```

## Internal Design

The utilities module follows these design principles:
- Small, focused functions with single responsibilities
- Stateless design where possible for easy testing
- Configurable behavior through parameters
- Consistent logging and error handling
- Performance optimization for frequently used operations

## Dependencies

Internal:
- `app.utils.logging_setup`: For logging operations

External:
- `re`: For regular expression operations
- `datetime`: For date and time handling
- `asyncio`: For asynchronous rate limiting
- `redis`: For distributed rate limiting

## Additional Resources

- [Email Processing Documentation](../../../docs/email_processing.md)
- [API Reference](../../../docs/sphinx/build/html/api.html) 