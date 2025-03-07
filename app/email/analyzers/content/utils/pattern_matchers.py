"""Pattern matching utilities for email content analysis.

This module provides pattern matching functionality for detecting various aspects
of email content such as sentiment, urgency, and email type. It uses pre-compiled
regex patterns and optimized sets for efficient text analysis.

Key Components:
1. Sentiment Analysis
   - Positive/negative sentiment detection
   - Gratitude and agreement recognition
   - Dissatisfaction and demand identification

2. Email Type Detection
   - Bulk email identification (marketing, newsletters)
   - Automated message detection (system notifications, no-reply)
   - HTML content indicators

3. Urgency Assessment
   - Direct urgency indicators
   - Deadline detection
   - Time-sensitive phrase analysis

The module uses pre-compiled patterns and pre-defined sets for optimal performance,
making it suitable for high-throughput email processing pipelines.

Usage:
    from .pattern_matchers import analyze_sentiment, detect_email_patterns, check_urgency
    sentiment = analyze_sentiment(text.lower())
    patterns = detect_email_patterns(text.lower())
    is_urgent = check_urgency(text.lower())
"""

import re
from typing import Dict, Set

# Pre-compiled regex patterns for sentiment and content analysis
POSITIVE_PATTERNS = {
    'gratitude': re.compile(r'\b(thank|thanks|grateful|appreciate|appreciated)\b'),
    'positive': re.compile(r'\b(great|excellent|good|wonderful|fantastic|amazing|helpful|pleased|happy|excited)\b'),
    'agreement': re.compile(r'\b(agree|approved|confirmed|sounds good|perfect)\b')
}

NEGATIVE_PATTERNS = {
    'urgency': re.compile(r'\b(urgent|asap|emergency|immediate|critical)\b'),
    'dissatisfaction': re.compile(r'\b(disappointed|concerned|worried|unfortunately|issue|problem|error|failed|wrong)\b'),
    'demand': re.compile(r'\b(must|need|require|mandatory|asap)\b')
}

BULK_PATTERNS = {
    'marketing': re.compile(r'\b(subscribe|unsubscribe|newsletter|marketing|offer|promotion|discount|sale|deal)\b'),
    'mass_email': re.compile(r'\b(view in browser|email preferences|opt out|mailing list)\b')
}

AUTOMATED_PATTERNS = {
    'system': re.compile(r'\b(system|automated|automatic|bot|daemon|notification)\b'),
    'noreply': re.compile(r'\b(no[- ]?reply|do[- ]?not[- ]?reply|auto[- ]?generated)\b')
}

# Pre-defined sets for faster lookups
VALID_ENTITY_LABELS: Set[str] = {'PERSON', 'ORG', 'GPE', 'DATE', 'TIME', 'MONEY', 'PERCENT', 'PRODUCT', 'EVENT', 'WORK_OF_ART'}
HTML_INDICATORS: Set[str] = {'<', '>', '/', 'http', 'www', 'html', 'css'}
QUESTION_WORDS: Set[str] = {'what', 'when', 'where', 'who', 'why', 'how'}
MODAL_VERBS: Set[str] = {'could', 'would', 'can', 'will', 'should'}
DEADLINE_WORDS: Set[str] = {'deadline', 'due', 'by', 'until', 'before'}


def analyze_sentiment(text_lower: str) -> Dict:
    """Analyze sentiment in text using pattern matching.
    
    Args:
        text_lower: Lowercase text to analyze
        
    Returns:
        Dictionary with sentiment analysis results
    """
    sentiment = {
        'is_positive': False,
        'is_negative': False,
        'gratitude': False,
        'agreement': False,
        'dissatisfaction': False,
        'demand': False
    }
    
    # Check positive patterns
    for pattern_name, pattern in POSITIVE_PATTERNS.items():
        if pattern.search(text_lower):
            sentiment['is_positive'] = True
            sentiment[pattern_name] = True
    
    # Check negative patterns
    for pattern_name, pattern in NEGATIVE_PATTERNS.items():
        if pattern.search(text_lower):
            sentiment['is_negative'] = True
            if pattern_name != 'urgency':  # Urgency is handled separately
                sentiment[pattern_name] = True
    
    return sentiment


def detect_email_patterns(text_lower: str) -> Dict:
    """Detect patterns indicating email type (bulk, automated, etc).
    
    Args:
        text_lower: Lowercase text to analyze
        
    Returns:
        Dictionary with detected email patterns
    """
    patterns = {
        'is_bulk': False,
        'is_automated': False,
    }
    
    # Check for bulk email indicators
    for pattern in BULK_PATTERNS.values():
        if pattern.search(text_lower):
            patterns['is_bulk'] = True
            break
    
    # Check for automated email indicators
    for pattern in AUTOMATED_PATTERNS.values():
        if pattern.search(text_lower):
            patterns['is_automated'] = True
            break
    
    return patterns


def check_urgency(text_lower: str) -> bool:
    """Check if text contains urgency indicators.
    
    Args:
        text_lower: Lowercase text to analyze
        
    Returns:
        True if text appears urgent, False otherwise
    """
    # Direct urgency words
    if NEGATIVE_PATTERNS['urgency'].search(text_lower):
        return True
        
    # Check for deadline words near time indicators
    has_deadline = any(word in text_lower for word in DEADLINE_WORDS)
    time_indicators = ('today', 'tomorrow', 'asap', 'soon', 'eod', 'cob')
    has_time = any(indicator in text_lower for indicator in time_indicators)
    
    return has_deadline and has_time