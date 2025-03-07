# Content Analysis Module

This module provides email content analysis capabilities using Natural Language Processing (NLP) and pattern matching techniques.

## Directory Structure

```
content/
├── core/                 # Core analyzer implementations
│   ├── nlp_analyzer.py           # Memory-resident analyzer
│   └── nlp_subprocess_analyzer.py # Subprocess-based analyzer
├── processing/          # Processing components
│   ├── nlp_worker.py            # Standalone worker process
│   └── subprocess_manager.py     # Subprocess management
└── utils/              # Shared utilities
    ├── spacy_utils.py           # SpaCy utilities
    └── pattern_matchers.py      # Pattern matching

```

## Components

### Core Analyzers

- **NLPAnalyzer**: Main analyzer that runs in the same process. Suitable for development and testing.
- **ContentAnalyzerSubprocess**: Memory-isolated analyzer that runs SpaCy in a separate process. Recommended for production.

### Processing

- **nlp_worker.py**: Standalone script that performs the actual NLP analysis. Runs in isolation.
- **subprocess_manager.py**: Manages worker processes, handles I/O and error conditions.

### Utilities

- **spacy_utils.py**: SpaCy model management, optimization, and cleanup utilities.
- **pattern_matchers.py**: Text pattern matching for sentiment, urgency, and email type detection.

## Memory Management

The module implements several strategies for managing memory:

1. **Process Isolation**: Heavy NLP processing runs in separate processes
2. **Document Cleanup**: Explicit cleanup of SpaCy documents
3. **Garbage Collection**: Forced GC after processing each document
4. **Text Limits**: Maximum text size limits to prevent memory issues

## Usage

### Basic Usage

```python
from app.email.analyzers.content.core import ContentAnalyzerSubprocess

analyzer = ContentAnalyzerSubprocess()
results = await analyzer.analyze_batch(texts)
```

### Development Mode

```python
from app.email.analyzers.content.core import NLPAnalyzer

analyzer = NLPAnalyzer()
results = await analyzer.analyze_batch(texts)
```

## Analysis Features

- Named Entity Recognition (NER)
- Key phrase extraction
- Sentiment analysis
- Email type classification
- Urgency detection
- Question identification
- Structural analysis

## Dependencies

- SpaCy
- Python 3.7+
- Async support 