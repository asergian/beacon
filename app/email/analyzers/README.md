# Email Analyzers Module

The Email Analyzers module provides content analysis capabilities for emails using both NLP and LLM approaches.

## Overview

This module contains the components responsible for analyzing email content to extract insights, identify entities, categorize emails, and determine priority. It implements two complementary approaches: content analysis using traditional NLP techniques, and semantic analysis using Large Language Models (LLMs).

## Directory Structure

```
analyzers/
├── __init__.py           # Package exports
├── base.py               # Base analyzer interfaces
├── content/              # NLP-based content analysis
│   ├── core/             # Core analyzer implementation
│   ├── processing/       # Processing infrastructure
│   └── utils/            # Content analysis utilities
├── semantic/             # LLM-based semantic analysis
│   ├── processors/       # Processing components
│   └── utilities/        # Semantic analysis utilities
└── README.md             # This documentation
```

## Components

### Base Analyzer
Defines the common interface for all analyzer implementations, ensuring consistent behavior across different analysis approaches.

### Content Analyzer
Implements analysis using traditional NLP techniques with spaCy. Focuses on entity extraction, keyword identification, and text classification. Optimized for efficiency and low resource usage.

### Semantic Analyzer
Implements analysis using OpenAI's language models. Provides deep semantic understanding, summarization, action item extraction, and priority determination. Offers highly accurate but more resource-intensive analysis.

## Usage Examples

```python
# Using the content analyzer
from app.email.analyzers.content.core.nlp_analyzer import ContentAnalyzer

analyzer = ContentAnalyzer()
results = analyzer.analyze("This is an email about the project deadline on Friday.")
print(f"Entities: {results.entities}")
print(f"Keywords: {results.keywords}")

# Using the semantic analyzer
from app.email.analyzers.semantic.analyzer import SemanticAnalyzer

semantic_analyzer = SemanticAnalyzer()
semantic_results = await semantic_analyzer.analyze(email_metadata, nlp_results)
print(f"Summary: {semantic_results.summary}")
print(f"Priority: {semantic_results.priority}")
print(f"Action items: {semantic_results.action_items}")
```

## Internal Design

The analyzers module follows these design principles:
- Clean separation between different analysis approaches
- Consistent interfaces for all analyzers
- Memory management for resource-intensive operations
- Asynchronous processing for LLM operations
- Caching and optimization for performance

## Dependencies

Internal:
- `app.services.openai_service`: For LLM access
- `app.utils.memory_profiling`: For memory management
- `app.utils.async_helpers`: For asynchronous operations

External:
- `spacy`: For NLP analysis
- `openai`: For LLM analysis
- `tiktoken`: For token counting
- `numpy`: For vector operations

## Additional Resources

- [Email Processing Documentation](../../../docs/sphinx/source/email_processing.html)
- [Memory Management Documentation](../../../docs/sphinx/source/memory_management.html)
- [spaCy Documentation](https://spacy.io/api/doc)
- [OpenAI API Documentation](https://platform.openai.com/docs/api-reference) 