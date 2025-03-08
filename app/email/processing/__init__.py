"""Email processing package for analyzing and processing emails.

This package contains components for the email processing pipeline, including:
- Analysis of email content using NLP and LLM techniques
- Email prioritization and categorization
- Metadata extraction and enrichment
- Processing pipeline orchestration

The main class is EmailProcessor which orchestrates the entire email analysis workflow.
"""

from app.email.processing.processor import (
    EmailProcessor,
    EmailProcessingError,
    LLMProcessingError,
    NLPProcessingError,
)

__all__ = [
    'EmailProcessor',
    'EmailProcessingError',
    'LLMProcessingError',
    'NLPProcessingError',
]
