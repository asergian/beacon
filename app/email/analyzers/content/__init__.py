"""Content analysis module for email processing.

This module provides NLP-based content analysis capabilities:
- Named Entity Recognition
- Key Phrase Extraction
- Sentiment Analysis
- Email Pattern Detection
- Urgency Analysis

The module is designed to handle memory-intensive NLP operations efficiently
through process isolation and careful resource management.
"""

from .core.nlp_analyzer import ContentAnalyzer
from .core.nlp_subprocess_analyzer import ContentAnalyzerSubprocess
from .utils.pattern_matchers import (
    analyze_sentiment,
    detect_email_patterns,
    check_urgency,
    VALID_ENTITY_LABELS
)
from .utils.spacy_utils import load_optimized_model, cleanup_doc

__all__ = [
    'ContentAnalyzer',
    'ContentAnalyzerSubprocess',
    'analyze_sentiment',
    'detect_email_patterns',
    'check_urgency',
    'VALID_ENTITY_LABELS',
    'load_optimized_model',
    'cleanup_doc'
] 