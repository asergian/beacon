"""Email priority scoring utilities.

This module provides functionality for calculating priority scores and levels for emails
based on various factors like sender importance, urgency, action requirements, and
content analysis. It helps in ranking and categorizing emails by their relative importance.
"""

from typing import Set, Tuple, Dict, Union
from ..models.analysis_settings import ProcessingConfig
from ..core.email_parsing import EmailMetadata

class PriorityScorer:
    """Calculates priority scores for emails based on various factors.
    
    This class analyzes various email attributes and content analysis results
    to determine an email's priority score and level (HIGH/MEDIUM/LOW).
    It considers factors such as sender importance, urgency indicators,
    action requirements, and content characteristics.
    
    Attributes:
        PRIORITY_HIGH: String constant representing high priority level
        PRIORITY_MEDIUM: String constant representing medium priority level
        PRIORITY_LOW: String constant representing low priority level
        vip_senders: Set of email addresses considered high priority
        config: Configuration settings for priority score calculations
        priority_threshold: Threshold value for determining priority levels
    """

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
        """Set the priority threshold for determining priority levels.
        
        Args:
            threshold: Integer value representing the threshold (typically 30, 50, or 70)
                      Lower thresholds make more emails high priority, higher thresholds
                      make fewer emails high priority
        """
        self.priority_threshold = threshold

    def score(self, email_data: Union[EmailMetadata, str], nlp_results: Dict, llm_results: Dict) -> Tuple[int, str]:
        """Calculate the priority score and level for an email.
        
        Analyzes email metadata and analysis results to calculate a numeric
        priority score and corresponding priority level.
        
        Args:
            email_data: Either EmailMetadata object or sender string
            nlp_results: Dictionary containing NLP analysis results
            llm_results: Dictionary containing LLM analysis results
            
        Returns:
            Tuple containing:
                - Integer priority score (typically 0-100)
                - String priority level ("HIGH", "MEDIUM", or "LOW")
        """
        try:
            # Extract sender from email_data
            sender = self._extract_sender(email_data)
            
            # Calculate base score with all factors
            score = self._calculate_base_score()
            score = self._apply_sender_boost(score, sender)
            score = self._apply_urgency_factors(score, nlp_results, llm_results)
            score = self._apply_content_factors(score, nlp_results)
            score = self._apply_email_pattern_penalties(score, nlp_results)
            
            # Normalize the score to ensure it's within bounds
            score = self._normalize_score(score)
            
            # Determine priority level based on score and threshold
            priority_level = self._determine_priority_level(score)
            
            return score, priority_level
            
        except Exception as e:
            print(f"Error calculating priority: {e}")
            return self.config.BASE_PRIORITY_SCORE, self.PRIORITY_LOW
    
    def _extract_sender(self, email_data: Union[EmailMetadata, str]) -> str:
        """Extract sender information from email data.
        
        Args:
            email_data: Either EmailMetadata object or sender string
            
        Returns:
            String containing the sender's email address
        """
        return str(email_data.sender) if isinstance(email_data, EmailMetadata) else str(email_data)
    
    def _calculate_base_score(self) -> int:
        """Get the base priority score from configuration.
        
        Returns:
            Integer base score to start the priority calculation
        """
        return self.config.BASE_PRIORITY_SCORE
    
    def _apply_sender_boost(self, score: int, sender: str) -> int:
        """Apply boost for VIP senders.
        
        Args:
            score: Current priority score
            sender: Email sender address
            
        Returns:
            Updated priority score with VIP boost applied if applicable
        """
        if sender in self.vip_senders:
            score += self.config.VIP_SCORE_BOOST
        return score
    
    def _apply_urgency_factors(self, score: int, nlp_results: Dict, llm_results: Dict) -> int:
        """Apply boosts for urgency and action requirements.
        
        Args:
            score: Current priority score
            nlp_results: Dictionary containing NLP analysis results
            llm_results: Dictionary containing LLM analysis results
            
        Returns:
            Updated priority score with urgency factors applied
        """
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
            
        return score
    
    def _apply_content_factors(self, score: int, nlp_results: Dict) -> int:
        """Apply boosts based on content analysis (questions and sentiment).
        
        Args:
            score: Current priority score
            nlp_results: Dictionary containing NLP analysis results
            
        Returns:
            Updated priority score with content factors applied
        """
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
                
        return score
    
    def _apply_email_pattern_penalties(self, score: int, nlp_results: Dict) -> int:
        """Apply penalties for automated or bulk email patterns.
        
        Args:
            score: Current priority score
            nlp_results: Dictionary containing NLP analysis results
            
        Returns:
            Updated priority score with pattern penalties applied
        """
        email_patterns = nlp_results.get('email_patterns', {})
        if email_patterns.get('is_automated', False):
            score += self.config.AUTOMATED_PENALTY
        if email_patterns.get('is_bulk', False):
            score += self.config.BULK_PENALTY
            
        return score
    
    def _normalize_score(self, score: int) -> int:
        """Ensure score stays within defined minimum and maximum bounds.
        
        Args:
            score: Current priority score
            
        Returns:
            Normalized priority score within allowed bounds
        """
        return max(self.config.MIN_PRIORITY, min(score, self.config.MAX_PRIORITY))
    
    def _determine_priority_level(self, score: int) -> str:
        """Determine priority level based on score and threshold setting.
        
        This converts the numeric score into a categorical priority level
        (HIGH, MEDIUM, or LOW) based on the configured threshold.
        
        Args:
            score: Calculated priority score
            
        Returns:
            String priority level ("HIGH", "MEDIUM", or "LOW")
        """
        if self.priority_threshold == 30:  # Low threshold
            if score >= 75:
                return self.PRIORITY_HIGH
            elif score >= 45:
                return self.PRIORITY_MEDIUM
            else:
                return self.PRIORITY_LOW
        elif self.priority_threshold == 70:  # High threshold
            if score >= 85:
                return self.PRIORITY_HIGH
            elif score >= 65:
                return self.PRIORITY_MEDIUM
            else:
                return self.PRIORITY_LOW
        else:  # Medium threshold (default: 50)
            if score >= 80:
                return self.PRIORITY_HIGH
            elif score >= 55:
                return self.PRIORITY_MEDIUM
            else:
                return self.PRIORITY_LOW

    def _is_automated_email(self, sender: str, subject: str) -> bool:
        """Check if the email appears to be automated.
        
        Args:
            sender: Email sender address
            subject: Email subject line
            
        Returns:
            Boolean indicating whether the email appears to be automated
        """
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
        """Check if the email appears to be a bulk/marketing email.
        
        Args:
            subject: Email subject line
            body: Email body text
            
        Returns:
            Boolean indicating whether the email appears to be bulk/marketing
        """
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