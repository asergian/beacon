"""Utility functions for content analysis.

This package provides utility functions:
- spacy_utils: SpaCy model management and cleanup
- pattern_matchers: Text pattern matching and analysis
"""

from .spacy_utils import load_optimized_model, cleanup_doc
from .pattern_matchers import (
    analyze_sentiment,
    detect_email_patterns,
    check_urgency,
    VALID_ENTITY_LABELS
)

__all__ = [
    'load_optimized_model',
    'cleanup_doc',
    'analyze_sentiment',
    'detect_email_patterns',
    'check_urgency',
    'VALID_ENTITY_LABELS'
]
