# Semantic Analyzer Module

The Semantic Analyzer module provides LLM-based analysis of emails for understanding context, generating summaries, and extracting action items.

## Overview

This module leverages Large Language Models (LLMs) to provide deep semantic understanding of email content. It extracts insights, categorizes emails, identifies action items, and generates concise summaries. The module handles the complete workflow of preparing emails for LLM processing, generating appropriate prompts, parsing responses, and formatting results in a structured manner.

## Directory Structure

```
semantic/
├── __init__.py              # Package exports
├── analyzer.py              # Main analyzer implementation
├── processors/              # Processing components
│   ├── __init__.py          # Processor exports
│   ├── batch_processor.py   # Batch processing logic
│   ├── prompt_creator.py    # LLM prompt generation
│   └── response_parser.py   # LLM response parsing
├── utilities/               # Helper functions and classes
│   ├── __init__.py          # Utility exports
│   ├── cost_calculator.py   # LLM cost tracking
│   ├── email_validator.py   # Email validation
│   ├── llm_client.py        # OpenAI client wrapper
│   ├── settings_util.py     # User settings management
│   ├── text_processor.py    # Text preprocessing
│   └── token_handler.py     # Token counting and limits
└── README.md                # This documentation
```

## Components

### Semantic Analyzer
The main analyzer class that orchestrates the entire semantic analysis process. It coordinates between different processors and utilities to deliver comprehensive email insights.

### Processors
Components responsible for specific aspects of the analysis pipeline:
- Prompt Creator: Generates structured prompts for LLM analysis
- Response Parser: Interprets and structures LLM responses
- Batch Processor: Handles processing of multiple emails efficiently

### Utilities
Helper functions and classes for various tasks:
- Token management and counting
- Text preprocessing and sanitization
- LLM client operations and error handling
- Cost calculation and tracking
- User settings management

## Usage Examples

```python
# Basic usage with a single email
from app.email.analyzers.semantic.analyzer import SemanticAnalyzer
from app.email.models.processed_email import ProcessedEmail

# Initialize the analyzer
analyzer = SemanticAnalyzer()

# Analyze a single email with NLP results from the content analyzer
email_metadata = ProcessedEmail(
    id="email_123",
    subject="Project Update Meeting",
    sender="colleague@example.com",
    body="Let's meet tomorrow to discuss the project progress. I need your input on the timeline.",
    # other fields...
)
nlp_results = {
    "entities": ["project", "timeline"],
    "keywords": ["meet", "discuss", "progress", "input"],
    # other NLP results...
}

# Perform semantic analysis
result = await analyzer.analyze(email_metadata, nlp_results)

print(f"Category: {result.category}")
print(f"Priority: {result.priority}")
print(f"Summary: {result.summary}")
print(f"Action items: {result.action_items}")

# Batch processing multiple emails
emails = [email1, email2, email3]
nlp_results_list = [nlp_results1, nlp_results2, nlp_results3]

batch_results = await analyzer.analyze_batch(
    emails=emails,
    nlp_results=nlp_results_list,
    max_batch_size=5
)

for result in batch_results:
    print(f"Email {result.id}: {result.summary}")
```

## Internal Design

The semantic analyzer module follows these design principles:
- Structured prompt engineering for consistent LLM responses
- Proper token management to control costs
- Robust error handling and fallback mechanisms
- Asynchronous processing for concurrent requests
- Response validation and normalization

## Dependencies

Internal:
- `app.services.openai_service`: For OpenAI client access
- `app.models.user`: For user settings and preferences
- `app.utils.async_helpers`: For asynchronous operations

External:
- `openai`: For LLM API access
- `tiktoken`: For token counting
- `asyncio`: For asynchronous processing
- `json`: For structured data handling

## Additional Resources

- [OpenAI API Documentation](https://platform.openai.com/docs/api-reference)
- [Prompt Engineering Guide](https://platform.openai.com/docs/guides/prompt-engineering)
- [Email Processing Documentation]({doc}`email_processing`)
- [API Reference]({doc}`api`) 