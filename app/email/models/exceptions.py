class EmailProcessingError(Exception):
    """Base class for email processing errors."""
    pass

class LLMProcessingError(EmailProcessingError):
    """Raised when LLM processing fails."""
    pass

class NLPProcessingError(EmailProcessingError):
    """Raised when NLP processing fails."""
    pass 