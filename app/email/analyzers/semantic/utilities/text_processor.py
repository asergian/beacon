"""
Text processing utilities for the semantic analyzer.

This module contains utility functions for processing and sanitizing text
used by the semantic analyzer.
"""
import re
from typing import Dict, List


def strip_html(html_content: str) -> str:
    """Extract readable text from HTML content.
    
    This method:
    1. Removes script and style elements
    2. Converts <br> and </p> to newlines
    3. Strips all other HTML tags
    4. Normalizes whitespace
    5. Preserves important line breaks
    
    Args:
        html_content: The HTML content to process
        
    Returns:
        Clean text extracted from HTML
    """
    from html import unescape
    
    # First unescape any HTML entities
    text = unescape(html_content)
    
    # Remove script and style elements
    text = re.sub(r'<script.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    
    # Replace <br> and </p> with newlines
    text = re.sub(r'<br[^>]*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</p>', '\n\n', text, flags=re.IGNORECASE)
    
    # Remove all other HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Fix common HTML entities that might have been missed
    text = text.replace('&nbsp;', ' ')
    text = text.replace('&amp;', '&')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    
    # Normalize whitespace while preserving paragraph breaks
    text = re.sub(r'\n\s*\n', '\n\n', text)  # Normalize paragraph breaks
    text = re.sub(r'[ \t]+', ' ', text)  # Normalize spaces and tabs
    text = re.sub(r' *\n *', '\n', text)  # Clean up spaces around newlines
    
    # Remove extra whitespace while preserving paragraph structure
    lines = [line.strip() for line in text.splitlines()]
    text = '\n'.join(line for line in lines if line)
    
    return text.strip()


def sanitize_text(text: str) -> str:
    """Sanitize text to prevent prompt injection and ensure valid formatting.
    
    Args:
        text: The text to sanitize
        
    Returns:
        Sanitized text
    """
    if not text:
        return ""
    # Remove any potential markdown or prompt injection characters
    text = re.sub(r'[`*_~<>{}[\]()#+-]', ' ', str(text))
    # Normalize whitespace
    text = ' '.join(text.split())
    return text


def format_list(items: list) -> str:
    """Safely format a list of items.
    
    Args:
        items: The list to format
        
    Returns:
        Formatted string representation
    """
    if not items:
        return "[]"
    # Limit to first 3 items and truncate each item to 50 chars
    formatted_items = [str(item)[:50] for item in items[:3]]
    return str(formatted_items)


def format_dict(d: dict) -> str:
    """Safely format a dictionary.
    
    Args:
        d: The dictionary to format
        
    Returns:
        Formatted string representation
    """
    if not d:
        return "{}"
    # Limit to first 3 items and truncate values to 50 chars
    formatted_dict = {str(k): str(v)[:50] for k, v in list(d.items())[:3]}
    return str(formatted_dict)


def select_important_entities(entities: List[Dict]) -> List[Dict]:
    """Select the most important named entities.
    
    Args:
        entities: List of entity dictionaries
        
    Returns:
        List of most important entities
    """
    # Sort entities by frequency and importance
    sorted_entities = sorted(
        entities,
        key=lambda x: (x.get('count', 1), len(x.get('text', '')), x.get('label', '') in ['PERSON', 'ORG']),
        reverse=True
    )
    # Return top 5 most important entities
    return sorted_entities[:5]


def select_important_keywords(keywords: List[str], max_keywords: int = 5) -> List[str]:
    """Select the most important keywords.
    
    Args:
        keywords: List of keywords
        max_keywords: Maximum number of keywords to return
        
    Returns:
        List of most important keywords
    """
    # Sort keywords by length (longer usually more specific) and take top N
    return sorted(keywords, key=len, reverse=True)[:max_keywords]


def select_important_patterns(patterns: dict, max_items: int = 3) -> dict:
    """Select the most important sentiment patterns.
    
    Args:
        patterns: Dictionary of patterns
        max_items: Maximum number of patterns to return
        
    Returns:
        Dictionary of most important patterns
    """
    if not patterns:
        return {}
    # Sort by value (frequency) and take top N
    sorted_patterns = sorted(patterns.items(), key=lambda x: x[1], reverse=True)
    return dict(sorted_patterns[:max_items]) 