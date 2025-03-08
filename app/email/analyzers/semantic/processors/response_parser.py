"""
Response parsing functionality for the semantic analyzer.

This module handles the parsing and validation of LLM responses.
"""
import json
import logging
from typing import Dict, Any
from flask import g


class ResponseParser:
    """Parses and validates LLM responses."""
    
    def __init__(self):
        """Initialize the response parser."""
        self.logger = logging.getLogger(__name__)
        
    def parse_response(self, response_text: str) -> Dict[str, Any]:
        """Parse the LLM response into a structured format.
        
        Args:
            response_text: The raw text response from the LLM
            
        Returns:
            Structured dictionary with parsed response
            
        Raises:
            LLMProcessingError: If the response cannot be parsed properly
        """
        try:
            # First try to extract JSON if response is wrapped in markdown code blocks
            if '```json' in response_text:
                json_content = response_text.split('```json')[1].split('```')[0].strip()
            elif '```' in response_text:
                json_content = response_text.split('```')[1].split('```')[0].strip()
            else:
                json_content = response_text.strip()
                
            result = json.loads(json_content)
            
            # Apply validation and normalization
            result = self._validate_and_normalize(result)
            
            return result
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse LLM response as JSON: {e}")
            from ....models.exceptions import LLMProcessingError
            raise LLMProcessingError(f"Invalid JSON response: {e}")
        except Exception as e:
            self.logger.error(f"Error parsing LLM response: {e}")
            from ....models.exceptions import LLMProcessingError
            raise LLMProcessingError(f"Error parsing response: {e}")
            
    def _validate_and_normalize(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and normalize parsed response.
        
        Args:
            result: The parsed JSON response
            
        Returns:
            Validated and normalized response
        """
        # Validate and normalize category
        if 'category' in result:
            # Convert to uppercase for consistency
            category = result['category'].upper()
            # Map to one of the expected categories
            category_mapping = {
                'WORK': 'Work',
                'PERSONAL': 'Personal',
                'PROMOTIONS': 'Promotions',
                'INFORMATIONAL': 'Informational'
            }
            result['category'] = category_mapping.get(category, 'Informational')
        
        # Ensure action_items are properly formatted
        if 'action_items' in result:
            formatted_items = []
            for item in result['action_items']:
                if isinstance(item, str):
                    # Convert string items to proper format
                    formatted_items.append({
                        'description': item,
                        'due_date': None
                    })
                elif isinstance(item, dict):
                    # Ensure proper structure
                    formatted_items.append({
                        'description': item.get('description', ''),
                        'due_date': item.get('due_date')
                    })
            result['action_items'] = formatted_items
        
        # Validate custom categories if present
        if 'custom_categories' in result and hasattr(g, 'user'):
            user_categories = g.user.get_setting('ai_features.custom_categories', [])
            valid_categories = {}
            for category in user_categories:
                name = category.get('name', '').strip()
                values = category.get('values', [])
                if name and name in result['custom_categories']:
                    value = result['custom_categories'][name]
                    # Only keep the value if it's in the allowed values
                    if value in values:
                        valid_categories[name] = value
            result['custom_categories'] = valid_categories
        
        # Validate required fields with defaults
        defaults = {
            'needs_action': False,
            'category': 'Informational',
            'action_items': [],
            'summary': 'No summary available',
            'priority': 50  # Default medium priority
        }
        
        for field, default in defaults.items():
            if field not in result or result[field] is None:
                result[field] = default
                
        # Ensure priority is within bounds
        if 'priority' in result:
            try:
                result['priority'] = max(0, min(100, int(result['priority'])))
            except (ValueError, TypeError):
                self.logger.warning(f"Invalid priority value: {result['priority']}, defaulting to 50")
                result['priority'] = 50
        
        return result
        
    def create_disabled_response(self, email_id: str) -> Dict[str, Any]:
        """Create a basic response when AI is disabled.
        
        Args:
            email_id: The ID of the email
            
        Returns:
            Basic disabled response
        """
        return {
            'needs_action': False,
            'category': 'Informational',
            'action_items': [],
            'summary': 'No summary available',
            'priority': 30,
            'model': None,
            'total_tokens': 0,
            'prompt_tokens': 0,
            'completion_tokens': 0,
            'cost': 0,
            'email_id': email_id,
            'ai_enabled': False
        } 