# Semantic Email Analyzer

This module provides semantic analysis capabilities for emails using Large Language Models (LLMs). It analyzes email content to extract meaningful insights, determine priority, identify action items, and provide structured summaries.

## Module Structure

```
semantic/
├── __init__.py              # Package exports
├── analyzer.py              # Main analyzer class
├── README.md               # This file
├── utilities/              # Utility functions and classes
│   ├── __init__.py
│   ├── text_processor.py   # Text processing utilities
│   ├── token_handler.py    # Token counting and truncation
│   ├── settings_util.py    # User settings management
│   ├── cost_calculator.py  # LLM cost calculations
│   ├── llm_client.py       # OpenAI client operations
│   └── email_validator.py  # Email validation and preprocessing
└── processors/             # Core processing components
    ├── __init__.py
    ├── prompt_creator.py   # LLM prompt generation
    ├── response_parser.py  # LLM response parsing
    └── batch_processor.py  # Batch processing logic
```

## Components

### SemanticAnalyzer

The main class that orchestrates the email analysis process. It:
- Processes individual emails and batches
- Manages user settings and configurations
- Coordinates between different components
- Handles LLM interactions and cost tracking

### Utilities

#### TokenHandler
- Manages token counting and text truncation
- Provides fallback mechanisms when tiktoken is unavailable
- Ensures text stays within token limits while preserving meaning

#### TextProcessor
- Handles HTML stripping and text sanitization
- Formats data structures for LLM consumption
- Selects important entities, keywords, and patterns

#### SettingsUtil
- Retrieves and manages user settings with proper defaults
- Handles configuration access and validation
- Provides easy access to common settings like model type and context length

#### CostCalculator
- Manages LLM cost calculations for different models
- Formats usage statistics for responses
- Tracks token usage and associated costs

#### LLMClient
- Handles OpenAI client operations
- Provides consistent error handling for API requests
- Manages completion requests with appropriate parameters

#### EmailValidator
- Validates email data structure and required fields
- Preprocesses emails by cleaning HTML and truncating content
- Ensures consistent data format for analysis

### Processors

#### PromptCreator
- Generates structured prompts for LLM analysis
- Handles custom category formatting
- Manages summary length constraints
- Formats analysis context

#### ResponseParser
- Parses and validates LLM responses
- Normalizes categories and action items
- Handles custom category validation
- Provides fallback responses when AI is disabled

#### BatchProcessor
- Manages batch processing of multiple emails
- Handles parallel processing with asyncio
- Tracks token usage and costs
- Provides detailed processing statistics

## Code Organization

The semantic analyzer module follows these organizational principles:

1. **Small, focused methods**: Each method has a single responsibility
2. **Proper error handling**: Consistent error handling patterns throughout
3. **Utility extraction**: Common operations are extracted into dedicated utility modules
4. **Separation of concerns**: Clear boundaries between data validation, LLM operations, and business logic
5. **Consistent logging**: Structured logging with appropriate log levels

## Usage

```python
from app.email.analyzers.semantic import SemanticAnalyzer

# Initialize the analyzer
analyzer = SemanticAnalyzer()

# Analyze a single email
result = await analyzer.analyze(email_data, nlp_results)

# Process a batch of emails
batch_results = await analyzer.analyze_batch(emails, max_batch_size=20)
```

## Response Format

The analyzer returns structured data including:
- Action requirements (`needs_action`)
- Email category (`category`)
- Action items with due dates (`action_items`)
- Concise summary (`summary`)
- Priority score (`priority`)
- Processing statistics (tokens, cost)

## Configuration

The analyzer respects user settings for:
- AI feature enablement
- Model selection
- Context length
- Summary length preferences
- Custom categories

## Error Handling

The module provides comprehensive error handling for:
- LLM processing failures
- Invalid input data
- Token encoding issues
- API connection problems

All errors are properly logged and wrapped in `LLMProcessingError` for consistent handling.

## Dependencies

- `tiktoken`: For token counting and management
- `flask`: For context and configuration management
- `asyncio`: For parallel processing in batches

## Documentation

All components are documented using Google-style docstrings and can be processed by documentation tools like Sphinx with the Napoleon extension. 