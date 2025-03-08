"""Processed email model for representing analyzed emails.

This module contains the ProcessedEmail dataclass which represents a fully processed
email with all extracted information and analysis results.
"""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

@dataclass
class ProcessedEmail:
    """Represents a fully processed email with all extracted information.
    
    This class stores both raw email data and the results of various analyses
    performed on the email, including NLP analysis, LLM processing, and
    priority scoring.
    
    Attributes:
        id: Unique identifier for the email
        subject: Email subject line
        sender: Email sender address
        body: Email body content
        date: Timestamp when the email was sent
        urgency: Flag indicating if email contains urgency markers
        entities: Dictionary of named entities extracted from email
        key_phrases: List of key phrases extracted from email
        sentence_count: Number of sentences in the email
        sentiment_indicators: Dictionary of sentiment indicators by type
        structural_elements: Dictionary of structural elements identified in email
        needs_action: Flag indicating if email requires action
        category: Primary email category classification
        action_items: List of action items extracted from email
        summary: Brief summary of email content
        custom_categories: Custom categorization tags applied to email
        priority: Numeric priority score (0-100)
        priority_level: Text representation of priority (Low/Medium/High)
    """
    # Basic email metadata
    id: str
    subject: str
    sender: str
    body: str
    date: datetime

    # Content analysis
    urgency: Optional[bool] = False
    entities: Optional[Dict[str, Any]] = None
    key_phrases: Optional[List[str]] = None
    sentence_count: Optional[int] = None
    sentiment_indicators: Optional[Dict[str, List[str]]] = None
    structural_elements: Optional[Dict[str, List[str]]] = None

    # LLM analysis
    needs_action: Optional[bool] = False
    category: Optional[str] = "Informational"
    action_items: Optional[List[Dict[str, Optional[str]]]] = None
    summary: Optional[str] = None
    custom_categories: Optional[Dict[str, Optional[str]]] = None

    # Priority and classification
    priority: Optional[int] = 50
    priority_level: Optional[str] = "Medium"

    def __post_init__(self):
        """Initialize default values for optional fields and normalize date.
        
        Performs the following operations:
        - Initializes empty collections for None values
        - Ensures date is a proper datetime with timezone information
        - Normalizes date to UTC timezone if needed
        """
        if self.entities is None:
            self.entities = {}
        if self.key_phrases is None:
            self.key_phrases = []
        if self.sentiment_indicators is None:
            self.sentiment_indicators = {}
        if self.structural_elements is None:
            self.structural_elements = {}
        if self.action_items is None:
            self.action_items = []
        if self.custom_categories is None:
            self.custom_categories = {}
            
        # Ensure date is datetime with timezone
        if isinstance(self.date, str):
            try:
                # Parse the date string and ensure it has timezone info
                # Handle both ISO format and 'Z' UTC indicator
                date_str = self.date.replace('Z', '+00:00')
                if not any(x in date_str for x in ['+', '-']):
                    date_str += '+00:00'
                parsed_date = datetime.fromisoformat(date_str)
                self.date = parsed_date.astimezone(timezone.utc)
            except ValueError:
                # If parsing fails, use current time in UTC
                self.date = datetime.now(timezone.utc)
        elif isinstance(self.date, datetime):
            # If it's already a datetime but has no timezone, assume UTC
            if self.date.tzinfo is None:
                self.date = self.date.replace(tzinfo=timezone.utc)
            else:
                # Convert to UTC if it has a different timezone
                self.date = self.date.astimezone(timezone.utc)

    def dict(self) -> Dict:
        """Convert the ProcessedEmail to a dictionary.
        
        Returns:
            Dict: A dictionary representation of the ProcessedEmail object with the date
                 converted to an ISO format string with timezone information.
        """
        data = asdict(self)
        # Convert datetime to ISO format string with timezone
        if isinstance(data['date'], datetime):
            # Ensure date is in UTC and format with Z suffix
            utc_date = data['date'].astimezone(timezone.utc)
            data['date'] = utc_date.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        return data 