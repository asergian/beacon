"""Base email analyzer interface.

This module defines the base interface for all email analyzers in the system.
Analyzers process email content to extract insights, sentiment, and other information.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any


class BaseAnalyzer(ABC):
    """Base interface for all email analyzers.
    
    All analyzers should implement this interface to ensure consistent API
    across different analyzer implementations.
    """
    
    @abstractmethod
    async def analyze_batch(self, texts: List[str]) -> List[Dict[str, Any]]:
        """Analyze a batch of text content.
        
        Args:
            texts: A list of text content to analyze
            
        Returns:
            A list of analysis results, one for each input text
        """
        pass 