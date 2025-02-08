from typing import Set, Tuple, Dict, Union
from ..models.analysis_settings import ProcessingConfig
from ..core.email_parsing import EmailMetadata

class PriorityScorer:
    """Calculates priority scores for emails based on various factors."""

    # Priority level constants
    PRIORITY_HIGH = "HIGH"
    PRIORITY_MEDIUM = "MEDIUM"
    PRIORITY_LOW = "LOW"

    def __init__(self, vip_senders: Set[str], config: ProcessingConfig):
        """Initialize the PriorityScorer.

        Args:
            vip_senders: Set of VIP sender addresses
            config: Configuration for priority calculation
        """
        self.vip_senders = vip_senders
        self.config = config
        # Default priority threshold (medium)
        self.priority_threshold = 50

    def set_priority_threshold(self, threshold: int):
        """Set the priority threshold for determining priority levels."""
        self.priority_threshold = threshold

    def score(self, email_data: Union[EmailMetadata, str], nlp_results: Dict, llm_results: Dict) -> Tuple[int, str]:
        """Calculate the priority score and level for an email."""
        try:
            # Start with base score
            score = self.config.BASE_PRIORITY_SCORE
            
            # Extract sender from email_data
            sender = str(email_data.sender) if isinstance(email_data, EmailMetadata) else str(email_data)
            
            # Major factors
            if sender in self.vip_senders:
                score += self.config.VIP_SCORE_BOOST
            
            # Urgency from NLP results
            if nlp_results.get('urgency', False):
                score += self.config.URGENCY_SCORE_BOOST
            
            # Action needed from LLM results
            if llm_results.get('needs_action', False):
                score += self.config.ACTION_SCORE_BOOST
            
            # Time sensitivity and deadlines
            time_sensitivity = nlp_results.get('time_sensitivity', {})
            if time_sensitivity.get('has_deadline', False):
                score += self.config.DEADLINE_BOOST
            
            # Question analysis
            questions = nlp_results.get('questions', {})
            if questions.get('has_questions', False):
                score += self.config.QUESTION_BOOST
                # Additional boost for request questions
                if questions.get('request_questions'):
                    score += 5
            
            # Sentiment analysis
            sentiment = nlp_results.get('sentiment_analysis', {})
            if sentiment.get('is_strong_sentiment', False):
                score += self.config.SENTIMENT_BOOST
                # Additional boost for dissatisfaction
                if sentiment.get('has_dissatisfaction', False):
                    score += 5
            
            # Email pattern penalties
            email_patterns = nlp_results.get('email_patterns', {})
            if email_patterns.get('is_automated', False):
                score += self.config.AUTOMATED_PENALTY
            if email_patterns.get('is_bulk', False):
                score += self.config.BULK_PENALTY
            
            # Ensure score stays within bounds
            score = max(self.config.MIN_PRIORITY, min(score, self.config.MAX_PRIORITY))
            
            # Determine priority level based on threshold setting
            if self.priority_threshold == 30:  # Low threshold
                if score >= 75:
                    priority_level = self.PRIORITY_HIGH
                elif score >= 45:
                    priority_level = self.PRIORITY_MEDIUM
                else:
                    priority_level = self.PRIORITY_LOW
            elif self.priority_threshold == 70:  # High threshold
                if score >= 85:
                    priority_level = self.PRIORITY_HIGH
                elif score >= 65:
                    priority_level = self.PRIORITY_MEDIUM
                else:
                    priority_level = self.PRIORITY_LOW
            else:  # Medium threshold (default: 50)
                if score >= 80:
                    priority_level = self.PRIORITY_HIGH
                elif score >= 55:
                    priority_level = self.PRIORITY_MEDIUM
                else:
                    priority_level = self.PRIORITY_LOW
            
            return score, priority_level
            
        except Exception as e:
            print(f"Error calculating priority: {e}")
            return self.config.BASE_PRIORITY_SCORE, self.PRIORITY_LOW

    def _is_automated_email(self, sender: str, subject: str) -> bool:
        """Check if the email appears to be automated."""
        automated_indicators = {
            'noreply', 'no-reply', 'donotreply', 'do-not-reply',
            'notification', 'alert', 'system', 'mailer-daemon',
            'automated', 'auto-confirm', 'auto-response'
        }
        
        sender_lower = sender.lower()
        subject_lower = subject.lower()
        
        # Check sender address for automated indicators
        if any(indicator in sender_lower for indicator in automated_indicators):
            return True
            
        # Check subject for automated indicators
        if any(indicator in subject_lower for indicator in automated_indicators):
            return True
            
        return False

    def _is_bulk_email(self, subject: str, body: str) -> bool:
        """Check if the email appears to be a bulk/marketing email."""
        bulk_indicators = {
            'unsubscribe', 'newsletter', 'subscription', 'marketing',
            'promotional', 'offer', 'discount', 'sale', 'deal',
            'campaign', 'blast', 'announcement'
        }
        
        text = (subject + ' ' + body).lower()
        
        # Check for bulk email indicators
        if any(indicator in text for indicator in bulk_indicators):
            return True
            
        # Check for typical marketing patterns
        if 'view in browser' in text or 'view as webpage' in text:
            return True
            
        return False 