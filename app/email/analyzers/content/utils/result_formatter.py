"""Utilities for formatting NLP analysis results.

This module provides utilities for formatting and standardizing NLP analysis results,
including default responses, error handling, and result structure validation.

The module handles:
- Default response creation
- Error response formatting
- Result structure validation
- Field mapping and normalization
"""

from typing import Dict, List, Any

def create_error_response() -> Dict[str, Any]:
    """Create a default error response with empty fields.
    
    Returns:
        Dictionary containing default values for all analysis fields.
    """
    return {
        'entities': {},
        'key_phrases': [],
        'sentence_count': 0,
        'urgency': False,
        'sentiment_analysis': {
            'scores': {
                'positive': 0.0,
                'negative': 0.0,
                'patterns': {
                    'gratitude': False,
                    'agreement': False,
                    'dissatisfaction': False,
                    'demand': False
                }
            },
            'is_positive': False,
            'is_strong_sentiment': False,
            'has_gratitude': False,
            'has_dissatisfaction': False
        },
        'email_patterns': {
            'is_bulk': False,
            'is_automated': False,
            'bulk_indicators': [],
            'automated_indicators': []
        },
        'questions': {
            'has_questions': False,
            'direct_questions': [],
            'rhetorical_questions': [],
            'request_questions': [],
            'question_count': 0
        },
        'time_sensitivity': {
            'has_deadline': False,
            'deadline_phrases': [],
            'time_references': []
        },
        'structural_elements': {
            'verbs': [],
            'named_entities_categories': [],
            'dependencies': []
        },
        'error': 'Processing failed'
    }

def format_nlp_result(nlp_result: Dict[str, Any], text: str = "") -> Dict[str, Any]:
    """Format raw NLP result into standardized structure.
    
    Args:
        nlp_result: Raw result dictionary from NLP processing
        text: Original text (for additional processing if needed)
        
    Returns:
        Formatted result dictionary with all required fields.
        
    The function handles the following fields from the NLP worker:
        - entities: Dict[str, List[Dict]] mapping entity labels to entity info
        - key_phrases: List[Dict] of noun phrases with text and position
        - sentence_count: int
        - questions: List[str] of question sentences
        - sentiment: Dict with is_positive, is_negative, and pattern flags
        - email_type: Dict with is_bulk and is_automated flags
        - urgency: Dict with is_urgent and has_deadline flags
        - is_question: bool indicating if text contains question words
    """
    if "error" in nlp_result and not nlp_result.get("entities"):
        return create_error_response()
    
    # Preserve entity structure from worker
    entities = nlp_result.get('entities', {})
    
    # Get urgency information
    urgency_info = nlp_result.get('urgency', {})
    is_urgent = urgency_info.get('is_urgent', False)
    
    # Get sentiment information
    sentiment = nlp_result.get('sentiment', {})
    sentiment_patterns = sentiment.get('patterns', {})
    
    # Get email type information
    email_type = nlp_result.get('email_type', {})
    
    return {
        'entities': entities,  # Preserve full entity information
        'key_phrases': nlp_result.get('key_phrases', []),
        'sentence_count': nlp_result.get('sentence_count', 0),
        'urgency': is_urgent,
        'sentiment_analysis': _format_sentiment(sentiment),
        'email_patterns': _format_email_patterns(email_type),
        'questions': _format_questions(nlp_result.get('questions', [])),
        'time_sensitivity': _format_time_sensitivity(nlp_result),
        'structural_elements': _format_structural_elements(nlp_result)
    }

def _format_sentiment(sentiment: Dict[str, Any]) -> Dict[str, Any]:
    """Format sentiment analysis results.
    
    Args:
        sentiment: Raw sentiment dictionary with is_positive, is_negative, and patterns
        
    Returns:
        Formatted sentiment dictionary with scores and pattern flags
    """
    is_positive = sentiment.get('is_positive', False)
    is_negative = sentiment.get('is_negative', False)
    patterns = sentiment.get('patterns', {})
    
    return {
        'scores': {
            'positive': 0.5 if is_positive else 0.0,
            'negative': 0.5 if is_negative else 0.0,
            'patterns': patterns
        },
        'is_positive': is_positive,
        'is_strong_sentiment': is_positive != is_negative,  # True if clearly positive or negative
        'has_gratitude': patterns.get('gratitude', False),
        'has_dissatisfaction': patterns.get('dissatisfaction', False)
    }

def _format_email_patterns(email_type: Dict[str, Any]) -> Dict[str, Any]:
    """Format email pattern detection results.
    
    Args:
        email_type: Raw email type dictionary with is_bulk and is_automated flags
        
    Returns:
        Formatted email patterns dictionary
    """
    return {
        'is_bulk': email_type.get('is_bulk', False),
        'is_automated': email_type.get('is_automated', False),
        'bulk_indicators': email_type.get('bulk_indicators', []),
        'automated_indicators': email_type.get('automated_indicators', [])
    }

def _format_questions(questions: List[str]) -> Dict[str, Any]:
    """Format question detection results.
    
    Args:
        questions: List of detected questions from the worker
        
    Returns:
        Formatted questions dictionary with categorized questions
    """
    return {
        'has_questions': len(questions) > 0,
        'direct_questions': questions,  # All questions are considered direct
        'rhetorical_questions': [],  # Not implemented in worker
        'request_questions': [],  # Not implemented in worker
        'question_count': len(questions)
    }

def _format_time_sensitivity(result: Dict[str, Any]) -> Dict[str, Any]:
    """Format time sensitivity results.
    
    Args:
        result: Raw NLP result dictionary
        
    Returns:
        Formatted time sensitivity dictionary
    """
    urgency = result.get('urgency', {})
    return {
        'has_deadline': urgency.get('has_deadline', False),
        'deadline_phrases': [],  # Not implemented in worker
        'time_references': []  # Not implemented in worker
    }

def _format_structural_elements(result: Dict[str, Any]) -> Dict[str, Any]:
    """Format structural elements results.
    
    Args:
        result: Raw NLP result dictionary
        
    Returns:
        Formatted structural elements dictionary
    """
    return {
        'verbs': [],  # Not implemented in worker
        'named_entities_categories': list(result.get('entities', {}).keys()),
        'dependencies': []  # Not implemented in worker
    } 