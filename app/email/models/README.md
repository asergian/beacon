# Email Models Module

The Email Models module defines the data structures and schemas used throughout the email processing system.

## Overview

This module contains the data classes and schemas that represent emails and their analysis results. It defines the structure of objects passed between different components of the email system, ensuring consistent data representation. These models include both input structures for processing commands and output structures for analysis results.

## Directory Structure

```
models/
├── __init__.py             # Package exports
├── analysis_command.py     # Processing command parameters
├── analysis_settings.py    # Analysis configuration
├── exceptions.py           # Email-specific exceptions
├── processed_email.py      # Email processing result model
└── README.md               # This documentation
```

## Components

### Analysis Command
Defines parameters for email processing operations, including time ranges, filtering criteria, and processing options. Used to control email fetching and analysis operations.

### Analysis Settings
Contains configuration settings for the email analysis process, including model selection, analysis depth, and feature flags for different analysis techniques.

### Email Exceptions
Defines custom exception classes specific to email operations, allowing for precise error handling and appropriate recovery strategies.

### Processed Email
Represents a fully processed email with all analysis results, including metadata, content analysis, semantic analysis, and derived properties like priority and action items.

## Usage Examples

```python
# Creating and using an analysis command
from app.email.models.analysis_command import AnalysisCommand

command = AnalysisCommand(
    days_back=3,               # Process emails from the last 3 days
    cache_duration_days=7,     # Cache results for 7 days
    batch_size=20,             # Process in batches of 20 emails
    priority_threshold=50,     # Only include emails with priority >= 50
    categories=["Work", "Personal"]  # Filter by these categories
)

# Working with a processed email
from app.email.models.processed_email import ProcessedEmail

email = ProcessedEmail(
    id="email_123",
    subject="Project Update Meeting",
    sender="colleague@example.com",
    recipients=["me@example.com"],
    date=datetime.now(),
    body="Let's meet to discuss the project progress...",
    category="Work",
    priority=85,
    summary="Colleague wants to schedule a project update meeting",
    action_items=[
        {"task": "Schedule meeting", "due_date": "2023-05-20"}
    ]
)

print(f"Email from {email.sender}: {email.subject}")
print(f"Priority: {email.priority}")
print(f"Action items: {email.action_items}")

# Handling email-specific exceptions
from app.email.models.exceptions import EmailProcessingError

try:
    # Process email
    result = process_email(raw_data)
except EmailProcessingError as e:
    print(f"Email processing failed: {e}")
    # Implement recovery strategy
```

## Internal Design

The models module follows these design principles:
- Clear definition of data structures with appropriate typing
- Immutable objects where appropriate to prevent unexpected changes
- Serialization support for caching and API responses
- Default values for optional fields
- Validation for critical fields

## Dependencies

Internal:
- None (models are a foundational module)

External:
- `dataclasses`: For data class definitions
- `typing`: For type annotations
- `datetime`: For date and time handling
- `pydantic`: For data validation (in some models)

## Additional Resources

- [Email Processing Documentation](../../../docs/email_processing.md)
- [API Reference](../../../docs/sphinx/build/html/api.html) 