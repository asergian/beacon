# Email Pipeline Module

The Email Pipeline module orchestrates the complete email processing workflow from fetching to analysis.

## Overview

This module serves as the coordinator for the entire email processing system, managing the sequence of operations from fetching emails from providers, parsing them, analyzing content, to storing and delivering results. It provides both streaming and batch processing capabilities with comprehensive error handling and performance monitoring.

## Directory Structure

```
pipeline/
├── __init__.py           # Package exports
├── orchestrator.py       # Main pipeline implementation
├── helpers/              # Helper functions for pipeline stages
│   ├── context.py        # User context management
│   ├── fetching.py       # Email fetching utilities
│   ├── processing.py     # Processing utilities
│   └── stats.py          # Statistics and reporting
└── README.md             # This documentation
```

## Components

### Email Pipeline
The main pipeline class that coordinates the processing workflow, handling batch processing, caching, and result delivery. Provides both streaming and non-streaming interfaces.

### Pipeline Helpers
Modular components that implement specific stages of the pipeline, including context setup, email fetching, processing orchestration, and statistics tracking.

## Usage Examples

```python
# Standard usage with all components
from app.email.pipeline.orchestrator import create_pipeline
from app.email.models.analysis_command import AnalysisCommand

# Create pipeline with components
pipeline = create_pipeline(connection, parser, processor, cache)

# Non-streaming usage (get all results at once)
command = AnalysisCommand(days_back=3, cache_duration_days=7)
result = await pipeline.get_analyzed_emails(command)

# Process results
for email in result.emails:
    print(f"Email from {email.sender}: {email.subject}")
    print(f"Priority: {email.priority}")
    print(f"Summary: {email.summary}")

# Streaming usage (get results as they become available)
async for update in pipeline.get_analyzed_emails_stream(command):
    if update["type"] == "email":
        email = update["data"]
        print(f"Received email: {email.subject}")
    elif update["type"] == "status":
        print(f"Status update: {update['data']['message']}")
    elif update["type"] == "stats":
        print(f"Process stats: {update['data']}")
```

## Internal Design

The pipeline module follows these design principles:
- Clear separation of pipeline stages for maintainability
- Streaming architecture for progressive result delivery
- Comprehensive error handling and recovery
- Performance monitoring and optimization
- Caching to avoid redundant processing

## Dependencies

Internal:
- `app.email.clients`: For email fetching
- `app.email.parsing`: For email parsing
- `app.email.processing`: For email analysis
- `app.email.storage`: For email caching
- `app.utils.memory_profiling`: For memory management
- `app.models.activity`: For activity logging

External:
- `asyncio`: For asynchronous processing
- `datetime`: For date range calculations

## Additional Resources

- [Email Processing Documentation](../../../docs/sphinx/source/email_processing.html)
- [Memory Management Documentation](../../../docs/sphinx/source/memory_management.html)
- [API Reference](../../../docs/sphinx/source/api.html) 