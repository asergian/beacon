# Email Processing Module

The Email Processing module handles the analysis and transformation of parsed emails, applying NLP and LLM techniques to extract insights.

## Overview

This module is responsible for processing parsed emails to extract insights, categorize content, identify action items, and determine priorities. It serves as a high-level coordinator, utilizing both NLP and LLM analyzers to provide comprehensive email analysis. The processor manages the complete workflow from accepting parsed emails to delivering enriched, analyzed results.

## Directory Structure

```
processing/
├── __init__.py           # Package exports
├── processor.py          # Main processor implementation
├── sender.py             # Email sending functionality
└── README.md             # This documentation
```

## Components

### Email Processor
The main component that orchestrates the email analysis workflow. It combines NLP and LLM analyzers to extract insights from emails, handling both individual and batch processing with appropriate error handling and statistics tracking.

### Email Sender
Provides functionality for sending emails, including composing messages, managing templates, and interfacing with SMTP servers. Enables response capabilities for the application.

## Usage Examples

```python
# Processing emails with the Email Processor
from app.email.processing.processor import EmailProcessor
from app.email.analyzers.content.core.nlp_analyzer import ContentAnalyzer
from app.email.analyzers.semantic.analyzer import SemanticAnalyzer
from app.email.parsing.parser import EmailParser

# Initialize analyzers
content_analyzer = ContentAnalyzer()
semantic_analyzer = SemanticAnalyzer()
parser = EmailParser()

# Create processor
processor = EmailProcessor(
    email_client=email_client,
    text_analyzer=content_analyzer,
    llm_analyzer=semantic_analyzer,
    parser=parser
)

# Process a single email
processed_email = await processor.process_email(raw_email)
print(f"Subject: {processed_email.subject}")
print(f"Priority: {processed_email.priority}")
print(f"Category: {processed_email.category}")
print(f"Action items: {processed_email.action_items}")

# Process a batch of emails
processed_emails = await processor.process_emails(raw_emails, batch_size=10)

# Sending an email
from app.email.processing.sender import EmailSender

sender = EmailSender()
await sender.send_email(
    to_address="recipient@example.com",
    subject="Hello from Beacon",
    body="This is a test email from Beacon.",
    reply_to="sender@example.com"
)
```

## Internal Design

The processing module follows these design principles:
- Orchestration of different analysis techniques
- Asynchronous processing for I/O-bound operations
- Batch processing for efficiency
- Comprehensive error handling
- Detailed statistics and performance tracking

## Dependencies

Internal:
- `app.email.analyzers`: For content and semantic analysis
- `app.email.parsing`: For email parsing
- `app.utils.memory_profiling`: For memory management
- `app.utils.logging_setup`: For logging operations

External:
- `asyncio`: For asynchronous processing
- `email`: For email construction
- `smtplib`: For SMTP operations
- `jinja2`: For email templates

## Additional Resources

- [Email Processing Documentation](../../../docs/email_processing.md)
- [Memory Management Documentation](../../../docs/memory_management.md)
- [API Reference](../../../docs/sphinx/build/html/api.html) 