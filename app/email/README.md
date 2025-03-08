# Email Module

The Email module provides comprehensive email processing capabilities including fetching, parsing, analyzing, and managing emails from various providers.

## Overview

This module forms the core of Beacon's email processing system. It handles every aspect of email management from connecting to email providers (like Gmail), fetching and parsing emails, analyzing content using NLP and LLM techniques, to processing and storing results. The email module implements a pipeline architecture that enables efficient processing of large volumes of emails with sophisticated analysis.

## Directory Structure

```
email/
├── __init__.py              # Package exports
├── README.md                # This documentation
├── analyzers/               # Email content analysis components
│   ├── content/             # NLP-based content analysis
│   └── semantic/            # LLM-based semantic analysis
├── clients/                 # Email service provider clients
│   ├── gmail/               # Gmail API client
│   └── imap/                # IMAP protocol client
├── models/                  # Email data structures and schemas
├── parsing/                 # Email parsing and extraction
├── pipeline/                # Orchestration and workflow
├── processing/              # Email processing and transformation
├── storage/                 # Caching and persistence
└── utils/                   # Email-specific utilities
```

## Components

### Email Clients
Provides interfaces to connect to different email service providers like Gmail and standard IMAP servers. Handles authentication, connection management, and raw email retrieval.

### Email Parsing
Extracts structured data from raw email content, including headers, body text, attachments, and metadata. Handles different email formats and encodings.

### Email Analysis
Analyzes email content using two approaches:
- Content Analysis: NLP-based processing for entity extraction, keyword identification, and text classification
- Semantic Analysis: LLM-based processing for deeper understanding, summarization, and action item extraction

### Email Pipeline
Orchestrates the complete email processing workflow, managing the sequence of operations from fetching to analysis. Provides both streaming and batch processing capabilities.

### Email Storage
Handles caching and persistence of email data and analysis results, with support for Redis-based caching and efficient retrieval.

## Usage Examples

```python
# Initialize email pipeline with components
from app.email.pipeline.orchestrator import create_pipeline
from app.email.clients.gmail.client import GmailClient
from app.email.parsing.parser import EmailParser
from app.email.processing.processor import EmailProcessor
from app.email.storage.redis_cache import RedisEmailCache

# Create pipeline components
client = GmailClient()
parser = EmailParser()
processor = EmailProcessor(client, analyzer, llm_analyzer, parser)
cache = RedisEmailCache()

# Initialize pipeline
pipeline = create_pipeline(client, parser, processor, cache)

# Analyze emails with command parameters
from app.email.models.analysis_command import AnalysisCommand
command = AnalysisCommand(days_back=3, cache_duration_days=7)
result = await pipeline.get_analyzed_emails(command)
```

## Internal Design

The email module follows these design principles:
- Clean separation of concerns between fetching, parsing, and analysis
- Asynchronous processing to handle I/O-bound operations efficiently
- Memory management for resource-intensive operations
- Caching to avoid redundant processing
- Error handling with graceful degradation

## Dependencies

Internal:
- `app.services.openai_service`: For LLM access
- `app.models.user`: For user settings and preferences
- `app.utils.memory_profiling`: For memory management
- `app.utils.async_helpers`: For asynchronous operations

External:
- `google-api-python-client`: For Gmail API access
- `spacy`: For NLP analysis
- `openai`: For LLM analysis
- `redis`: For caching
- `beautifulsoup4`: For HTML parsing

## Additional Resources

- [Email Processing Documentation](../../docs/email_processing.md)
- [Memory Management Documentation](../../docs/memory_management.md)
- [API Reference](../../docs/sphinx/build/html/api.html) 