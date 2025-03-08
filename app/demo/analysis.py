"""Demo email analysis module.

This module provides pre-generated analysis capabilities for demo emails.
It handles caching and retrieval of analysis results for different models
and context lengths to demonstrate AI-powered email analysis features
without requiring actual API calls during demo usage.

Classes:
    DemoAnalysis: Class to manage pre-generated analysis for demo emails.

Functions:
    get_analysis_key: Generate a key for looking up analysis by model and context.
    load_analysis_cache: Load cached analysis results from a JSON file.
    save_analysis_cache: Save analysis cache to a JSON file.
    generate_all_demo_analysis: Generate analysis for all demo emails.
"""

import os
from openai import OpenAI
from typing import Dict, Any, List
import json
import logging
from flask import current_app

logger = logging.getLogger(__name__)

# Global instance for demo analysis
demo_analysis = None

def get_openai_client():
    """Get the OpenAI client from the Flask application context.
    
    Returns:
        OpenAI: The OpenAI client instance.
        
    Raises:
        RuntimeError: If called outside Flask application context or client not initialized.
    """
    if not current_app:
        raise RuntimeError("This function must be called within a Flask application context")
    if not hasattr(current_app, 'get_openai_client'):
        raise RuntimeError("OpenAI client not initialized in Flask application")
    return current_app.get_openai_client()

def get_analysis_key(model: str, context_length: str) -> str:
    """Generate a key for looking up pre-generated analysis.
    
    Args:
        model: The model name (e.g., "gpt-4o-mini").
        context_length: The context length as a string (e.g., "500").
        
    Returns:
        str: A composite key in the format "model_contextlength".
    """
    return f"{model}_{context_length}"

class DemoAnalysis:
    """Manages pre-generated analysis results for demo emails.
    
    This class handles caching, retrieval, and application of pre-generated
    analysis results for demo emails. It supports multiple models and context
    lengths for comprehensive demonstration of AI capabilities.
    
    Attributes:
        analysis_cache: Dictionary storing analysis results by email ID, model, and context length.
    """
    
    def __init__(self):
        """Initialize the DemoAnalysis with an empty cache."""
        self.analysis_cache: Dict[str, Dict[str, Any]] = {}
        
    def get_analysis(self, email_id: str, model: str, context_length: str) -> Dict[str, Any]:
        """Get pre-generated analysis for an email based on model and context length.
        
        Args:
            email_id: The unique identifier for the email.
            model: The model name used for analysis.
            context_length: The context length used for analysis.
            
        Returns:
            Dict[str, Any]: The analysis results or an empty dict if not found.
        """
        key = get_analysis_key(model, context_length)
        email_analysis = self.analysis_cache.get(email_id, {})
        return email_analysis.get(key, {})

    def _determine_needs_action(self, action_items: List[Dict[str, Any]]) -> bool:
        """Determine if an email needs action based on its action items.
        
        Args:
            action_items: List of action items detected in the email.
            
        Returns:
            bool: True if there are action items, False otherwise.
        """
        return bool(action_items and len(action_items) > 0)

    def apply_analysis(self, email: Dict[str, Any], model: str, context_length: str) -> Dict[str, Any]:
        """Apply pre-generated analysis to an email.
        
        Retrieves cached analysis for the email and applies it to the email object.
        
        Args:
            email: The email object to enhance with analysis.
            model: The model to use for analysis lookup.
            context_length: The context length to use for analysis lookup.
            
        Returns:
            Dict[str, Any]: The enhanced email object with analysis applied.
        """
        email_id = email['id']
        analysis = self.get_analysis(email_id, model, context_length)
        
        if analysis:
            # Apply all analysis fields
            email['summary'] = analysis.get('summary', '')
            email['key_phrases'] = analysis.get('key_phrases', [])
            email['sentiment_indicators'] = analysis.get('sentiment', {})
            email['priority_level'] = analysis.get('priority_level', 'MEDIUM')
            email['priority_score'] = analysis.get('priority_score', 50)
            email['action_items'] = analysis.get('action_items', [])
            email['category'] = analysis.get('category', 'Uncategorized')
            
            # Determine needs_action based on action_items
            email['needs_action'] = self._determine_needs_action(email['action_items'])
            
            # Add metadata about the analysis
            email['analysis_metadata'] = {
                'model': analysis.get('model', model),
                'context_length': analysis.get('context_length', context_length),
                'total_tokens': analysis.get('total_tokens', 0),
                'input_length': analysis.get('input_length', 0)
            }
            
        return email

    def generate_analysis(self, email_body: str, model: str = "gpt-4o-mini", context_length: str = "1000") -> Dict[str, Any]:
        """Generate analysis for an email using OpenAI API.
        
        Creates a comprehensive analysis of an email including summary, key phrases,
        sentiment, priority, action items, and category.
        
        Args:
            email_body: The HTML body of the email to analyze.
            model: The OpenAI model to use for analysis.
            context_length: The maximum context length to use.
            
        Returns:
            Dict[str, Any]: The generated analysis results.
            
        Raises:
            Exception: If the OpenAI API call fails.
        """
        try:
            client = get_openai_client()

            # Truncate email body based on context length
            # Using approximate chars-to-tokens ratio of 4:1
            max_body_chars = int(context_length) * 3  # Leave room for system message and output
            if len(email_body) > max_body_chars:
                print(f"Truncating email body from {len(email_body)} to {max_body_chars} characters")
                email_body = email_body[:max_body_chars] + "..."
            
            # Prepare the prompt
            system_prompt = """You are an AI email analyzer. Your task is to analyze emails and provide output in the following JSON format:
{
    "summary": "Brief summary of the email",
    "key_phrases": ["phrase1", "phrase2", "phrase3"],
    "sentiment": {
        "positive": ["word1", "word2"],
        "negative": ["word3", "word4"],
        "neutral": ["word5", "word6"]
    },
    "priority_level": "LOW|MEDIUM|HIGH",
    "priority_score": 0-100,
    "action_items": [
        {
            "description": "Action to take",
            "due_date": "YYYY-MM-DD"
        }
    ],
    "category": "Work|Personal|Promotions|Informational"
}

Guidelines for Action Items:
1. ONLY include action items if the email explicitly requires action from the recipient
2. Common cases that should NOT have action items:
   - Promotional emails (sales, marketing)
   - Pure informational updates (newsletters, announcements)
   - General FYI emails
   - Recap/summary emails without specific tasks
3. Common cases that SHOULD have action items:
   - Meeting invites/RSVPs
   - Requests for review/approval
   - Task assignments
   - Deadlines/submissions
   - Security alerts requiring action
4. Action items must be:
   - Specific and actionable
   - Time-bound with realistic deadlines
   - Directly related to email content
   - Required, not optional suggestions

Analysis Guidelines by Context Length:
1. Shorter context (300):
   - Concise summary
   - 3-4 key phrases
   - Basic sentiment
2. Medium context (800):
   - Standard analysis
   - 4-5 key phrases
   - More detailed sentiment
3. Longer context (2000):
   - Comprehensive analysis
   - 5-6 key phrases
   - Detailed sentiment
   - Relationship analysis
   
Note: Context length should NOT affect whether action items are included - this should only depend on the email's content and requirements."""
            
            # Call the OpenAI API
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": email_body
                    }
                ],
                response_format={"type": "json_object"},
                max_tokens=int(context_length),
                temperature=0.3
            )
            
            # Process the response
            response_json = json.loads(response.choices[0].message.content)
            
            # Add usage stats from the API response
            response_json['model'] = model
            response_json['context_length'] = context_length
            response_json['total_tokens'] = response.usage.total_tokens
            response_json['prompt_tokens'] = response.usage.prompt_tokens
            response_json['completion_tokens'] = response.usage.completion_tokens
            response_json['input_length'] = len(email_body)
            
            return response_json
            
        except Exception as e:
            logger.error(f"Error generating analysis: {e}")
            return {
                "summary": "Failed to generate analysis due to an error.",
                "key_phrases": [],
                "sentiment": {"positive": [], "negative": [], "neutral": []},
                "priority_level": "MEDIUM",
                "priority_score": 50,
                "action_items": [],
                "category": "Uncategorized",
                "error": str(e)
            }


def generate_all_demo_analysis(demo_emails: Dict[str, Any]):
    """Generate analysis for all demo emails.
    
    Processes each demo email with multiple models and context lengths
    to provide a comprehensive demo experience.
    
    Args:
        demo_emails: Dictionary of demo emails with their content.
    """
    from .data import get_demo_email_bodies
    
    # Get email bodies
    email_bodies = get_demo_email_bodies()
    
    # Define models and context lengths to use
    models = ["gpt-4o", "gpt-4o-mini"]
    context_lengths = ["500", "1000", "2000"]
    
    # Process each email
    for email_id, email_body in email_bodies.items():
        print(f"Processing email: {email_id}")
        for model in models:
            for context_length in context_lengths:
                key = get_analysis_key(model, context_length)
                print(f"Generating analysis with {model} and context length {context_length}...")
                
                # Skip if analysis already exists
                if email_id in demo_analysis.analysis_cache and key in demo_analysis.analysis_cache[email_id]:
                    print(f"Analysis already exists for {model} with context length {context_length}")
                    continue
                
                # Generate new analysis
                analysis = demo_analysis.generate_analysis(
                    email_body,
                    model=model,
                    context_length=context_length
                )
                if email_id not in demo_analysis.analysis_cache:
                    demo_analysis.analysis_cache[email_id] = {}
                demo_analysis.analysis_cache[email_id][key] = analysis
                print(f"Completed analysis for {model} with context length {context_length}")


def save_analysis_cache(filepath: str = 'app/demo/analysis_cache.json'):
    """Save the analysis cache to a JSON file.
    
    Args:
        filepath: Path to save the JSON cache file.
    """
    try:
        with open(filepath, 'w') as f:
            json.dump(demo_analysis.analysis_cache, f, indent=2)
        logger.info(f"Saved analysis cache to {filepath}")
    except Exception as e:
        logger.error(f"Failed to save analysis cache: {e}")


def load_analysis_cache(filepath: str = 'app/demo/analysis_cache.json'):
    """Load the analysis cache from a JSON file.
    
    Args:
        filepath: Path to the JSON cache file.
    """
    global demo_analysis
    if demo_analysis is None:
        demo_analysis = DemoAnalysis()
        
    try:
        with open(filepath, 'r') as f:
            demo_analysis.analysis_cache = json.load(f)
        logger.info(f"Loaded analysis cache from {filepath}")
    except Exception as e:
        logger.error(f"Failed to load analysis cache: {e}")


# Initialize the global demo analysis instance
demo_analysis = DemoAnalysis() 