from dataclasses import dataclass, field

@dataclass
class ProcessingConfig:
    """Configuration for email processing."""
    URGENCY_KEYWORDS: set = field(default_factory=lambda: {'urgent', 'asap', 'deadline', 'immediate', 'priority'})
    BASE_PRIORITY_SCORE: int = 50
    VIP_SCORE_BOOST: int = 20
    URGENCY_SCORE_BOOST: int = 15
    ACTION_SCORE_BOOST: int = 10
    MAX_PRIORITY: int = 100 