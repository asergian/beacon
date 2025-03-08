"""
Utilities for processing HTML content in email messages.
"""

import re
import html
from typing import Match

# Regular expression to match content between HTML tags
HTML_TAG_PATTERN = re.compile(r'<[^>]*>')
# Match common HTML entities
HTML_ENTITY_PATTERN = re.compile(r'&[a-zA-Z]+;|&#\d+;')

def strip_html(html_content: str) -> str:
    """
    Remove HTML tags and convert common HTML entities to text.
    
    Args:
        html_content: HTML content string
        
    Returns:
        Plain text with HTML tags removed
    """
    if not html_content:
        return ""
        
    # Replace common HTML entities with characters
    text = html_content
    
    # Replace <br>, <p>, <div> tags with newlines for better readability
    text = re.sub(r'<br[^>]*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<\/p>\s*<p[^>]*>', '\n\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<\/div>\s*<div[^>]*>', '\n', text, flags=re.IGNORECASE)
    
    # Remove all remaining HTML tags
    text = HTML_TAG_PATTERN.sub('', text)
    
    # Replace common HTML entities
    entities = {
        '&nbsp;': ' ',
        '&lt;': '<',
        '&gt;': '>',
        '&amp;': '&',
        '&quot;': '"',
        '&apos;': "'",
        '&#39;': "'",
        '&mdash;': '—',
        '&ndash;': '–',
        '&hellip;': '…'
    }
    
    for entity, char in entities.items():
        text = text.replace(entity, char)
    
    # Replace numeric entities (like &#8212;)
    text = re.sub(r'&#(\d+);', lambda m: chr(int(m.group(1))), text)
    
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()

def convert_urls_to_links(text: str) -> str:
    """
    Convert plain text URLs to HTML links.
    
    Args:
        text: Plain text that may contain URLs
        
    Returns:
        Text with URLs converted to HTML links
    """
    # URL pattern for http/https/www URLs
    url_pattern = r'(https?://[^\s<>"]+|www\.[^\s<>"]+)'
    
    def replace_with_link(match: Match[str]) -> str:
        url = match.group(0)
        display_url = url
        
        # Add https:// to www. URLs
        if url.startswith('www.'):
            url = 'https://' + url
            
        return f'<a href="{url}" target="_blank" rel="noopener noreferrer">{display_url}</a>'
    
    return re.sub(url_pattern, replace_with_link, text)

def text_to_html(plain_text: str) -> str:
    """
    Convert plain text to simple HTML with proper formatting.
    
    Args:
        plain_text: Plain text content
        
    Returns:
        HTML-formatted version of the text
    """
    # 1. Escape HTML special characters
    escaped_text = html.escape(plain_text)
    
    # 2. Convert URLs to clickable links
    text_with_links = convert_urls_to_links(escaped_text)
    
    # 3. Convert newlines to <br> tags for proper display
    text_with_breaks = text_with_links.replace('\n', '<br>\n')
    
    # 4. Wrap in a div with appropriate styling
    formatted_html = f'<div style="font-family: Arial, sans-serif; white-space: pre-wrap;">{text_with_breaks}</div>'
    
    return formatted_html 