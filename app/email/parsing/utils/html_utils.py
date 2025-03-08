"""
Utilities for processing HTML content in email messages.

This module provides functions for handling HTML content in email messages,
including stripping HTML tags, converting plain text to HTML, and processing
URLs within content.

Example:
    ```python
    from app.email.parsing.utils.html_utils import strip_html, text_to_html
    
    plain_text = strip_html("<p>Hello <b>World</b></p>")
    # Returns: "Hello World"
    
    html_content = text_to_html("Visit https://example.com")
    # Returns HTML with a clickable link
    ```
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
    
    Converts HTML content to plain text by removing tags and
    replacing HTML entities with their character equivalents.
    
    Args:
        html_content: HTML content string to process
        
    Returns:
        str: Plain text with HTML tags removed and entities converted
        
    Examples:
        >>> strip_html("<p>Hello <b>World</b></p>")
        "Hello World"
        >>> strip_html("&lt;tag&gt; with entities")
        "< tag > with entities"
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
    
    Identifies URLs in plain text and converts them to HTML anchor tags
    with appropriate attributes for security and usability.
    
    Args:
        text: Plain text that may contain URLs
        
    Returns:
        str: Text with URLs converted to HTML links
        
    Examples:
        >>> convert_urls_to_links("Visit https://example.com for more info")
        'Visit <a href="https://example.com" target="_blank" rel="noopener noreferrer">https://example.com</a> for more info'
    """
    # URL pattern for http/https/www URLs
    url_pattern = r'(https?://[^\s<>"]+|www\.[^\s<>"]+)'
    
    def replace_with_link(match: Match[str]) -> str:
        """
        Convert a matched URL into an HTML link.
        
        Args:
            match: Regex match object containing the URL
            
        Returns:
            str: HTML anchor tag with the URL
        """
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
    
    Transforms plain text into HTML format by escaping special characters,
    converting URLs to links, and adding appropriate HTML structure
    and formatting.
    
    Args:
        plain_text: Plain text content to convert
        
    Returns:
        str: HTML-formatted version of the text
        
    Examples:
        >>> text_to_html("Hello\nWorld\nhttps://example.com")
        # Returns HTML with line breaks and a clickable link
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