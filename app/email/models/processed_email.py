from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

@dataclass
class ProcessedEmail:
    """Represents a fully processed email with all extracted information."""
    # Basic email metadata
    id: str
    subject: str
    sender: str
    body: str
    date: datetime

    # Content analysis
    urgency: bool
    entities: Dict[str, str]
    key_phrases: List[str]
    sentence_count: int
    sentiment_indicators: Dict[str, List[str]]
    structural_elements: Dict[str, List[str]]

    # LLM analysis
    needs_action: bool
    category: str
    action_items: List[Dict[str, Optional[str]]]
    summary: str

    # Priority and classification
    priority: int
    priority_level: str

    def dict(self) -> Dict:
        """Convert the ProcessedEmail to a dictionary."""
        return {
            # Basic email metadata  
            'id': self.id,
            'subject': self.subject,
            'sender': self.sender,
            'body': self.body,
            'date': self.date,

            # Content analysis
            'urgency': self.urgency,
            'entities': self.entities,
            'key_phrases': self.key_phrases,
            'sentence_count': self.sentence_count,
            'sentiment_indicators': self.sentiment_indicators,
            'structural_elements': self.structural_elements,

            # LLM analysis
            'needs_action': self.needs_action,
            'category': self.category,
            'action_items': self.action_items,
            'summary': self.summary,

            # Priority and classification
            'priority': self.priority,
            'priority_level': self.priority_level
        } 