"""
Token handling utilities for the semantic analyzer.

This module contains utility functions for handling token counting and text truncation
used by the semantic analyzer.
"""
import re
import logging
import tiktoken
from typing import Optional


class TokenHandler:
    """Handles token counting and text truncation for LLM processing."""
    
    def __init__(self, encoding_name: str = "cl100k_base"):
        """Initialize the token handler.
        
        Args:
            encoding_name: The name of the tiktoken encoding to use
        """
        self.logger = logging.getLogger(__name__)
        try:
            self.encoding = tiktoken.get_encoding(encoding_name)
        except Exception as e:
            self.logger.error(f"Failed to get tiktoken encoding: {e}")
            self.encoding = None
            
    def count_tokens(self, text: str) -> int:
        """Count the number of tokens in a text string.
        
        Args:
            text: The text to count tokens for
            
        Returns:
            Number of tokens
        """
        if not self.encoding:
            # Fallback method if tiktoken fails
            return len(text.split()) * 1.5  # Rough estimate
        return len(self.encoding.encode(text))
        
    def truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """Truncate text to a maximum number of tokens while preserving sentence boundaries.
        
        Args:
            text: The text to truncate
            max_tokens: Maximum number of tokens to keep
            
        Returns:
            Truncated text ending at a sentence boundary, with a [truncated] marker if needed
        """
        if not self.encoding:
            # Fallback for when tiktoken isn't available (uses character-based truncation)
            self.logger.warning("Tiktoken unavailable, falling back to character-based truncation")
            return self._truncate_by_chars(text, max_tokens * 4)  # Rough estimate
            
        # First encode the entire text
        tokens = self.encoding.encode(text)
        
        # If we're already under the limit, return the full text
        if len(tokens) <= max_tokens:
            return text
            
        # Get the text from the truncated tokens
        truncated_text = self.encoding.decode(tokens[:max_tokens])
        
        # Split into sentences (accounting for common sentence endings)
        sentences = re.split(r'(?<=[.!?])\s+', truncated_text)
        
        # If we only have one sentence or empty text, return the truncated text as is
        if len(sentences) <= 1:
            return truncated_text + " [truncated]"
            
        # Remove the last (potentially incomplete) sentence
        complete_text = ' '.join(sentences[:-1])
        
        # Verify we haven't removed too much
        final_tokens = self.encoding.encode(complete_text)
        if len(final_tokens) < max_tokens * 0.7:  # If we've lost too much text
            # Use the original truncated text but try to end at a punctuation mark
            for punct in ['. ', '! ', '? ', '. \n', '! \n', '? \n']:
                last_punct = truncated_text.rfind(punct)
                if last_punct > len(truncated_text) * 0.7:  # Don't cut off too much
                    return truncated_text[:last_punct + 1] + " [truncated]"
            return truncated_text + " [truncated]"
            
        return complete_text + " [truncated]"
        
    def _truncate_by_chars(self, text: str, max_chars: int) -> str:
        """Fallback method to truncate by character count when tiktoken is unavailable.
        
        Args:
            text: The text to truncate
            max_chars: Maximum number of characters
            
        Returns:
            Truncated text
        """
        if len(text) <= max_chars:
            return text
            
        # Try to truncate at sentence boundary
        truncated = text[:max_chars]
        for punct in ['. ', '! ', '? ', '. \n', '! \n', '? \n']:
            last_punct = truncated.rfind(punct)
            if last_punct > max_chars * 0.7:  # Don't cut off too much
                return text[:last_punct + 1] + " [truncated]"
                
        # If no good sentence boundary, truncate at word boundary
        last_space = truncated.rfind(' ')
        if last_space > max_chars * 0.8:
            return text[:last_space] + " [truncated]"
            
        return truncated + " [truncated]" 