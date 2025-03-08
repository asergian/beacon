"""Email analyzers package.

This package provides various analyzers for email content, including:
- Content analyzers: Extract entities, sentiment, and linguistic features using NLP
  - Standard in-process analyzer (ContentAnalyzer)
  - Subprocess-based analyzer for better memory isolation (ContentAnalyzerSubprocess)
- Semantic analyzers: Understand email meaning and intent using LLMs (SemanticAnalyzer)

The package is organized as follows:
- content/: NLP-based content analysis
  - core/: Main analyzer implementations
    - nlp_analyzer.py: In-process content analyzer
    - nlp_subprocess_analyzer.py: Memory-isolated subprocess analyzer
  - processing/: Processing components
    - nlp_worker.py: Standalone NLP processing script
    - subprocess_manager.py: Subprocess management utilities
  - utils/: Shared utilities
    - spacy_utils.py: SpaCy model management
    - pattern_matchers.py: Text pattern matching
- semantic/: LLM-based semantic analysis
  - analyzer.py: Main semantic analyzer using LLMs

Memory Management:
The content analysis module implements several strategies for managing memory:
- Process isolation for SpaCy operations
- Document cleanup and garbage collection
- Text size limits and batch processing
"""

# Import main analyzer classes for easy access
from .base import BaseAnalyzer
from .content.core.nlp_analyzer import ContentAnalyzer
from .content.core.nlp_subprocess_analyzer import ContentAnalyzerSubprocess
from .semantic.analyzer import SemanticAnalyzer

# Define public API
__all__ = [
    'BaseAnalyzer',
    'ContentAnalyzer',
    'ContentAnalyzerSubprocess',
    'SemanticAnalyzer',
]
