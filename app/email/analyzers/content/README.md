# Content Analyzer Module

The Content Analyzer module provides NLP-based analysis of email text to extract entities, keywords, and patterns.

## Overview

This module implements natural language processing (NLP) analysis capabilities using spaCy to extract information from email content. It identifies entities, keywords, patterns, and linguistic structures to provide insights about the email content. The module is designed for efficiency and low memory consumption, with options for in-process or subprocess-based execution.

## Directory Structure

```
content/
├── __init__.py                # Package exports
├── core/                      # Core analysis functionality
│   ├── __init__.py            # Core component exports
│   ├── nlp_analyzer.py        # Main in-process analyzer
│   └── nlp_subprocess_analyzer.py # Subprocess-based analyzer
├── processing/                # Processing infrastructure
│   ├── __init__.py            # Processing component exports
│   ├── nlp_worker.py          # Worker implementation
│   └── subprocess_manager.py  # Subprocess coordination
├── utils/                     # Analysis utilities
│   ├── __init__.py            # Utility exports
│   ├── pattern_matchers.py    # Pattern recognition
│   ├── result_formatter.py    # Output formatting
│   └── spacy_utils.py         # spaCy helpers
└── README.md                  # This documentation
```

## Components

### Core Analyzers
Implements the main analysis functionality with both in-process and subprocess-based options:
- `ContentAnalyzer`: Standard in-process implementation
- `ContentAnalyzerSubprocess`: Memory-isolated subprocess implementation

### Processing Infrastructure
Provides the infrastructure for subprocess-based analysis, including worker management, interprocess communication, and task coordination.

### Analysis Utilities
Collection of helper functions and tools for pattern matching, result formatting, and spaCy integration.

## Usage Examples

```python
# Using the in-process analyzer
from app.email.analyzers.content.core.nlp_analyzer import ContentAnalyzer

analyzer = ContentAnalyzer()
results = analyzer.analyze("Please review the quarterly report by Friday. Contact John Smith for questions.")

# Access analysis results
print(f"Entities: {results.entities}")
print(f"Keywords: {results.keywords}")
print(f"Dates: {results.dates}")
print(f"Urgency: {results.urgency_score}")

# Using the subprocess-based analyzer
from app.email.analyzers.content.core.nlp_subprocess_analyzer import ContentAnalyzerSubprocess

subprocess_analyzer = ContentAnalyzerSubprocess()
results = await subprocess_analyzer.analyze_async(
    "Please review the quarterly report by Friday. Contact John Smith for questions."
)

# Access the same result structure
print(f"Entities: {results.entities}")
print(f"Keywords: {results.keywords}")
```

## Internal Design

The content analyzer module follows these design principles:
- Efficient NLP processing with optimized models
- Memory management via subprocess isolation
- Extensible pattern recognition
- Consistent result structure
- Configurable analysis depth

## Dependencies

Internal:
- `app.utils.memory_profiling`: For memory monitoring
- `app.utils.async_helpers`: For asynchronous operations

External:
- `spacy`: For NLP processing
- `numpy`: For numeric operations
- `asyncio`: For asynchronous operations
- `multiprocessing`: For subprocess management

## Additional Resources

- [spaCy Documentation](https://spacy.io/api/doc)
- [NLP Concepts Overview](https://spacy.io/usage/linguistic-features)
- [Memory Management Documentation]({doc}`memory_management`)
- [API Reference]({doc}`api`) 