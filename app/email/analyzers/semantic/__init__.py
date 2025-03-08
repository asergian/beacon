"""
Semantic analysis package for email processing.

This package provides utilities for semantic analysis of emails
using LLMs to extract meaning, priority, action items, and more.
The semantic analyzer uses a modular approach with utilities and processors
to perform various aspects of email analysis.
"""

from .analyzer import SemanticAnalyzer

__all__ = ['SemanticAnalyzer'] 