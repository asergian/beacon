# Email Processing Pipeline

This module provides a unified pipeline for fetching, processing, and analyzing emails, combining various components like email fetching, parsing, and AI-powered analysis.

## Overview

The Email Pipeline is responsible for orchestrating the end-to-end process of:
1. Retrieving emails from Gmail
2. Using locally cached emails when available
3. Parsing raw emails into structured data
4. Processing emails with AI-powered analysis
5. Filtering emails based on criteria
6. Caching results for future use
7. Providing detailed analytics

The pipeline can operate in two modes:
- **Batch Mode**: Process all emails and return results at once
- **Streaming Mode**: Process emails and stream results in real-time

## Module Structure

```
app/email/pipeline/
├── orchestrator.py     # Main pipeline orchestration
├── helpers/            # Modular helper functions
│   ├── __init__.py     # Exposes helper functions
│   ├── context.py      # User context setup
│   ├── fetching.py     # Email fetching and caching
│   ├── processing.py   # Email processing functions
│   └── stats.py        # Stats generation and logging
```

## Key Components

### EmailPipeline Class

The main orchestrator class that coordinates the email processing workflow. It contains two primary methods:

- `get_analyzed_emails()`: Batch processing of emails
- `get_analyzed_emails_stream()`: Streaming processing of emails with real-time updates

### Helper Modules

- **context.py**: Functions for setting up user context, validating user information, and handling timezones
- **fetching.py**: Functions for retrieving emails from Gmail and the cache
- **processing.py**: Functions for processing emails with and without AI, including batching
- **stats.py**: Functions for generating statistics and activity logging

## Usage Examples

### Creating a Pipeline Instance

```python
from app.email.pipeline.orchestrator import create_pipeline
from ..clients.gmail.client import GmailClient
from ..parsing.parser import EmailParser
from ..processing.processor import EmailProcessor
from ..storage.redis_cache import RedisEmailCache

# Create components
gmail_client = GmailClient(...)
parser = EmailParser()
processor = EmailProcessor(...)
cache = RedisEmailCache(...)

# Create pipeline
pipeline = create_pipeline(
    connection=gmail_client,
    parser=parser,
    processor=processor,
    cache=cache
)
```

### Batch Processing

```python
from ..models.analysis_command import AnalysisCommand

# Create command with processing parameters
command = AnalysisCommand(
    days_back=7,  # Process last 7 days of emails
    cache_duration_days=3,  # Cache results for 3 days
    batch_size=10,  # Process in batches of 10 emails
    priority_threshold=50,  # Only return emails with priority >= 50
    categories=["Work", "Personal"]  # Only include these categories
)

# Process emails
result = await pipeline.get_analyzed_emails(command)

# Access results
emails = result.emails
stats = result.stats
errors = result.errors
```

### Streaming Processing

```python
# Same command as above
command = AnalysisCommand(...)

# Process emails with streaming updates
async for update in pipeline.get_analyzed_emails_stream(command):
    update_type = update.get('type')
    
    if update_type == 'status':
        # Show status message to user
        message = update['data']['message']
        print(f"Status: {message}")
        
    elif update_type == 'cached':
        # Display cached emails immediately
        cached_emails = update['data']['emails']
        print(f"Loaded {len(cached_emails)} cached emails")
        
    elif update_type == 'batch':
        # Process and display a batch of new emails
        batch_emails = update['data']['emails']
        print(f"Processed {len(batch_emails)} new emails")
        
    elif update_type == 'stats':
        # Show final statistics
        stats = update['data']
        print(f"Completed with {stats['total_processed']} emails")
```

## Processing Workflow

1. **Setup User Context**: Validate user and retrieve preferences
2. **Check Cache**: Retrieve cached emails matching the criteria
3. **Fetch from Gmail**: Get any new emails not in cache
4. **Filter Cached Emails**: Remove cached emails no longer in Gmail
5. **Process Emails**: 
   - Without AI: Create basic email objects
   - With AI: Process with NLP and LLM analysis
6. **Filter Results**: Apply user-specified filters (priority, categories)
7. **Generate Statistics**: Compile processing statistics
8. **Log Activity**: Record user activity and email statistics

## Performance Considerations

- The pipeline uses batching to handle large numbers of emails efficiently
- Memory management is implemented at key points to avoid memory leaks
- Caching is used to avoid redundant processing and improve response times
- Progress tracking enables real-time updates in streaming mode 