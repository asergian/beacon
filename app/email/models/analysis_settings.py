"""Email analysis settings model.

This module contains the ProcessingConfig dataclass which defines settings and
thresholds used in the email processing pipeline, particularly for scoring and
prioritization of emails.
"""

from dataclasses import dataclass, field

@dataclass
class ProcessingConfig:
    """Configuration for email processing and prioritization.
    
    This class defines constants and thresholds used during email analysis
    to calculate priority scores, detect urgency, and classify emails.
    
    Attributes:
        URGENCY_KEYWORDS: Set of keywords that indicate urgency in emails
        BASE_PRIORITY_SCORE: Starting score for email priority calculation
        
        # Major scoring factors
        VIP_SCORE_BOOST: Score increase for emails from VIP senders
        URGENCY_SCORE_BOOST: Score increase for emails with urgency indicators
        ACTION_SCORE_BOOST: Score increase for emails requiring action
        
        # Additional scoring factors
        DEADLINE_BOOST: Score increase for emails with specific deadlines
        DIRECT_EMAIL_BOOST: Score increase when user is primary recipient
        THREAD_BOOST: Score increase for emails in active threads
        SENTIMENT_BOOST: Score increase for emails with strong sentiment
        QUESTION_BOOST: Score increase for emails containing questions
        FOLLOWUP_BOOST: Score increase for follow-ups to user's emails
        
        # Penalties
        BULK_PENALTY: Score decrease for mass emails/newsletters
        AUTOMATED_PENALTY: Score decrease for automated system emails
        
        # Limits
        MAX_PRIORITY: Maximum possible priority score
        MIN_PRIORITY: Minimum possible priority score
    """
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