"""NLP model initialization and configuration."""

import spacy
import logging
from typing import Optional

logger = logging.getLogger(__name__)

def create_nlp_model(model_name: str = "en_core_web_sm") -> Optional[spacy.language.Language]:
    """Creates and loads the spaCy NLP model.
    
    Args:
        model_name: Name of the spaCy model to load
        
    Returns:
        Loaded spaCy model or None if loading fails
        
    Raises:
        RuntimeError: If model loading fails
    """
    try:
        logger.info(f"Loading spaCy model: {model_name}")
        return spacy.load(model_name)
    except Exception as e:
        logger.error(f"Failed to load spaCy model {model_name}: {e}")
        raise RuntimeError(f"NLP model initialization failed: {str(e)}") 