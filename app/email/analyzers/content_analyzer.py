import spacy
import re
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
        """Analyzes the text for entities, urgency, and additional linguistic features.
        
        Returns:
            Dict containing analyzed features including entities, key phrases,
            sentiment indicators, and structural elements useful for LLM processing.
        """
        doc = self.nlp(text)
        return {
            'entities': dict(list((ent.label_, ent.text) for ent in doc.ents)[:5]),  # Top 5 entities
            'key_phrases': [chunk.text for chunk in doc.noun_chunks][:3],  # Top 3 phrases
            'urgency': self._check_urgency(text),
            'sentence_count': len(list(doc.sents)),
            'sentiment_indicators': {
                'negations': [token.text for token in doc if token.dep_ == 'neg'][:2],  # Limit to 2 negations
                'questions': any(sent.root.tag_ == 'VBZ' and sent[-1].text == '?' for sent in doc.sents)
            },
            'structural_elements': {
                'verbs': [token.lemma_ for token in doc if token.pos_ == 'VERB'][:5],  # Top 5 verbs
                'named_entities_categories': list(set(ent.label_ for ent in doc.ents))[:3],  # Top 3 entity types
                'dependencies': [(token.text, token.dep_) for token in doc if token.dep_ in ('ROOT', 'dobj', 'iobj')][:3]  # Top 3 dependencies
            }
        }
        
    def _check_urgency(self, text: str) -> bool:
        """Checks if the text contains urgency keywords."""
        config = ProcessingConfig()
        # Clean the text by replacing special characters with spaces
        cleaned_text = re.sub(r'[^\w\s]', ' ', text.lower())
        words = cleaned_text.split()
        
        # Check for exact matches first
        if config.URGENCY_KEYWORDS & set(words):
            return True
            
        # Check for words that start with urgency keywords
        for word in words:
            for keyword in config.URGENCY_KEYWORDS:
                if word.startswith(keyword):
                    return True
        
        return False 