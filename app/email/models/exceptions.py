"""Exception classes for email processing.

This module contains custom exception classes used in the email processing
pipeline to handle different types of errors that may occur during analysis.
"""

class EmailProcessingError(Exception):
    """Base class for all email processing errors.
    
    This exception serves as the parent class for more specific email
    processing error types and should be used for general error handling.
    """
    pass

class LLMProcessingError(EmailProcessingError):
    """Exception raised when LLM (Language Model) processing fails.
    
    This error indicates issues with the AI language model component of
    email analysis, such as API failures, timeout errors, or invalid responses.
    """
    pass

class NLPProcessingError(EmailProcessingError):
    """Exception raised when NLP (Natural Language Processing) operations fail.
    
    This error indicates issues with text analysis operations such as
    entity extraction, sentiment analysis, or key phrase identification.
    """
    pass 