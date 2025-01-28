from typing import Set, Tuple, Dict
from ..models.analysis_settings import ProcessingConfig

class PriorityScorer:
    """Calculates priority scores for emails based on various factors."""

    def __init__(self, vip_senders: Set[str], config: ProcessingConfig):
        """Initialize the PriorityScorer.

        Args:
            vip_senders: Set of VIP sender addresses
            config: Configuration for priority calculation
        """
        self.vip_senders = vip_senders
        self.config = config
        
    def score(self, sender: str, nlp_results: Dict, llm_results: Dict) -> Tuple[int, str]:
        """Calculate the priority score and level for an email."""
        score = self.config.BASE_PRIORITY_SCORE
        
        if sender in self.vip_senders:
            score += self.config.VIP_SCORE_BOOST
        if nlp_results['urgency']:
            score += self.config.URGENCY_SCORE_BOOST
        if llm_results['needs_action']:
            score += self.config.ACTION_SCORE_BOOST
            
        score = min(score, self.config.MAX_PRIORITY)

        # Determine priority level based on score
        if score < 60:
            priority_level = "Low"
        elif score < 80:
            priority_level = "Medium"
        else:
            priority_level = "High"

        return score, priority_level 