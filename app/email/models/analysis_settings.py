from dataclasses import dataclass, field

@dataclass
class ProcessingConfig:
    """Configuration for email processing."""
    URGENCY_KEYWORDS: set = field(default_factory=lambda: {'urgent', 'asap', 'deadline', 'immediate', 'priority'})
    BASE_PRIORITY_SCORE: int = 30
    
    # Major factors
    VIP_SCORE_BOOST: int = 30      # VIP sender
    URGENCY_SCORE_BOOST: int = 25  # Urgent email
    ACTION_SCORE_BOOST: int = 20   # Action needed
    
    # Additional factors
    DEADLINE_BOOST: int = 15       # Has specific deadline
    DIRECT_EMAIL_BOOST: int = 10   # User is primary recipient (not CC/BCC)
    THREAD_BOOST: int = 8          # Part of an active thread
    SENTIMENT_BOOST: int = 5       # Strong sentiment (positive or negative)
    QUESTION_BOOST: int = 5        # Contains direct questions
    FOLLOWUP_BOOST: int = 5        # Follow-up to user's sent email
    
    # Penalties
    BULK_PENALTY: int = -10        # Mass email/newsletter
    AUTOMATED_PENALTY: int = -15   # Automated system email
    
    # Caps
    MAX_PRIORITY: int = 100
    MIN_PRIORITY: int = 0 