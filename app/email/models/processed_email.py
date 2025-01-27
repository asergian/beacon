from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

@dataclass
class ProcessedEmail:
    """Represents a fully processed email with all extracted information."""
    id: str
    subject: str
    sender: str
    body: str
    date: datetime
    needs_action: bool
    category: str
    action_items: List[Dict[str, Optional[str]]]
    summary: str
    priority: int
    priority_level: str

    def dict(self) -> Dict:
        """Convert the ProcessedEmail to a dictionary."""
        return {
            'id': self.id,
            'subject': self.subject,
            'sender': self.sender,
            'body': self.body,
            'date': self.date,
            'needs_action': self.needs_action,
            'category': self.category,
            'action_items': self.action_items,
            'summary': self.summary,
            'priority': self.priority,
            'priority_level': self.priority_level
        } 