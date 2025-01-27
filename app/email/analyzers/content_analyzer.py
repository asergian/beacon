import spacy
from typing import Dict
from ..models.analysis_settings import ProcessingConfig

class ContentAnalyzer:
    """Analyzes text using spaCy for entities and urgency."""

    def __init__(self, nlp_model: spacy.language.Language):
        """Initialize the ContentAnalyzer.

        Args:
            nlp_model: The spaCy NLP model to use.
        """
        self.nlp = nlp_model
        
    def analyze(self, text: str) -> Dict:
        """Analyzes the text for entities and urgency."""
        doc = self.nlp(text)
        return {
            'entities': {ent.label_: ent.text for ent in doc.ents},
            'key_phrases': [chunk.text for chunk in doc.noun_chunks],
            'is_urgent': self._check_urgency(text)
        }
        
    def _check_urgency(self, text: str) -> bool:
        """Checks if the text contains urgency keywords."""
        return bool(ProcessingConfig.URGENCY_KEYWORDS & set(text.lower().split())) 