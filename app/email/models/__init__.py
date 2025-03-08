"""Email module models.

This package contains data models used for email processing operations.

Modules:
    processed_email: Contains the ProcessedEmail dataclass representing a processed email with analysis
    analysis_command: Contains the AnalysisCommand dataclass for configuring email analysis 
    analysis_settings: Contains the ProcessingConfig dataclass with email processing settings
    exceptions: Contains exception classes for email processing errors
"""

from .processed_email import ProcessedEmail
from .analysis_command import AnalysisCommand
from .analysis_settings import ProcessingConfig
from .exceptions import EmailProcessingError, LLMProcessingError, NLPProcessingError

__all__ = [
    'ProcessedEmail',
    'AnalysisCommand',
    'ProcessingConfig',
    'EmailProcessingError',
    'LLMProcessingError',
    'NLPProcessingError'
]
