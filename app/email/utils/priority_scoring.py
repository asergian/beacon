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
        
    def score(self, email_data: Union[EmailMetadata, str], nlp_results: Dict, llm_results: Dict) -> Tuple[int, str]:
        """Calculate the priority score and level for an email.
        
        Args:
            email_data: Either an EmailMetadata object or a sender email string
            nlp_results: Results from NLP analysis
            llm_results: Results from LLM analysis
            
        Returns:
            Tuple of (priority_score, priority_level)
        """
        try:
            score = self.config.BASE_PRIORITY_SCORE
            
            # Extract sender from email_data
            if isinstance(email_data, EmailMetadata):
                sender = str(email_data.sender)  # Ensure sender is a string
            else:
                sender = str(email_data)  # Convert to string if it's not already
            
            # Safety checks for results
            nlp_results = {} if nlp_results is None else dict(nlp_results)
            llm_results = {} if llm_results is None else dict(llm_results)
            
            # Calculate score based on factors
            if sender in self.vip_senders:
                score += self.config.VIP_SCORE_BOOST
            if nlp_results.get('urgency', False):
                score += self.config.URGENCY_SCORE_BOOST
            if llm_results.get('needs_action', False):
                score += self.config.ACTION_SCORE_BOOST
                
            # Ensure score doesn't exceed maximum
            score = min(score, self.config.MAX_PRIORITY)
            
            # Determine priority level
            if score >= 80:
                priority_level = self.PRIORITY_HIGH
            elif score >= 60:
                priority_level = self.PRIORITY_MEDIUM
            else:
                priority_level = self.PRIORITY_LOW
                
            return score, priority_level
            
        except Exception as e:
            # Log error and return default values
            print(f"Error calculating priority: {e}")
            return self.config.BASE_PRIORITY_SCORE, self.PRIORITY_LOW 