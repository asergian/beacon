"""Pre-generated analysis results for demo emails using different models and context lengths."""

import os
from openai import OpenAI
from typing import Dict, Any, List
import json
import logging
from flask import current_app

logger = logging.getLogger(__name__)

# The OpenAI client will be obtained from the Flask app context instead of being initialized here
def get_openai_client():
    """Get the OpenAI client from the Flask application context."""
    if not current_app:
        raise RuntimeError("This function must be called within a Flask application context")
    if not hasattr(current_app, 'get_openai_client'):
        raise RuntimeError("OpenAI client not initialized in Flask application")
    return current_app.get_openai_client()

def get_analysis_key(model: str, context_length: str) -> str:
    """Generate a key for looking up pre-generated analysis."""
    return f"{model}_{context_length}"

class DemoAnalysis:
    """Manages pre-generated analysis results for demo emails."""
    
    def __init__(self):
        self.analysis_cache: Dict[str, Dict[str, Any]] = {}
        
    def get_analysis(self, email_id: str, model: str, context_length: str) -> Dict[str, Any]:
        """Get pre-generated analysis for an email based on model and context length."""
        key = get_analysis_key(model, context_length)
        email_analysis = self.analysis_cache.get(email_id, {})
        return email_analysis.get(key, {})

    def _determine_needs_action(self, action_items: List[Dict[str, Any]]) -> bool:
        """Determine if an email needs action based on its action items."""
        return bool(action_items and len(action_items) > 0)

    def apply_analysis(self, email: Dict[str, Any], model: str, context_length: str) -> Dict[str, Any]:
        """Apply pre-generated analysis to an email based on model and context length."""
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
        """Generate analysis for an email using OpenAI API."""
        try:
            # Map our model names to OpenAI model names
            model_map = {
                "gpt-4o": "gpt-4o",
                "gpt-4o-mini": "gpt-4o-mini"
            }
            
            openai_model = model_map.get(model, "gpt-4o-mini")
            context_length_int = int(context_length)
            
            # Truncate email body based on context length
            # Using approximate chars-to-tokens ratio of 4:1
            max_body_chars = context_length_int * 3  # Leave room for system message and output
            if len(email_body) > max_body_chars:
                print(f"Truncating email body from {len(email_body)} to {max_body_chars} characters")
                email_body = email_body[:max_body_chars] + "..."
            
            print(f"Calling OpenAI API with model: {openai_model}")
            print(f"Input length: {len(email_body)} chars, Max output tokens: {context_length_int}")
            
            # Prepare system message to enforce JSON output
            system_message = """You are an AI email analyzer. Your task is to analyze emails and provide output in the following JSON format:
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

            # Call OpenAI API
            response = get_openai_client().chat.completions.create(
                model=openai_model,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": f"Analyze this email:\n\n{email_body}"}
                ],
                max_tokens=context_length_int,
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            print(f"Received response from OpenAI API")
            
            # Parse the response
            analysis = json.loads(response.choices[0].message.content)
            
            # Add usage statistics
            analysis.update({
                'model': model,
                'context_length': context_length,
                'total_tokens': response.usage.total_tokens,
                'prompt_tokens': response.usage.prompt_tokens,
                'completion_tokens': response.usage.completion_tokens,
                'input_length': len(email_body)
            })
            
            print(f"Successfully generated analysis with {response.usage.total_tokens} total tokens")
            return analysis
            
        except Exception as e:
            print(f"Error generating analysis: {str(e)}")
            logger.error(f"Failed to generate analysis: {e}")
            return {}

# Create singleton instance
demo_analysis = DemoAnalysis()

def generate_all_demo_analysis(demo_emails):
    """Generate and cache analysis for all demo emails using different models and context lengths."""
    for email in demo_emails:
        email_id = email['id']
        email_body = email['body']
        print(f"\nProcessing email ID: {email_id}")
        
        # Generate analysis for different combinations
        for model in ['gpt-4o', 'gpt-4o-mini']:
            # Use 300 for concise summaries, 800 for standard analysis, 2000 for detailed analysis
            for context_length in ['300', '800', '2000']:
                print(f"\nGenerating analysis for model={model}, context_length={context_length}")
                key = get_analysis_key(model, context_length)
                analysis = demo_analysis.generate_analysis(
                    email_body,
                    model=model,
                    context_length=context_length
                )
                if email_id not in demo_analysis.analysis_cache:
                    demo_analysis.analysis_cache[email_id] = {}
                demo_analysis.analysis_cache[email_id][key] = analysis
                print(f"Completed analysis for {model} with context length {context_length}")

# Function to save analysis cache to file
def save_analysis_cache(filepath: str = 'app/email/demo_analysis_cache.json'):
    """Save the analysis cache to a JSON file."""
    try:
        with open(filepath, 'w') as f:
            json.dump(demo_analysis.analysis_cache, f, indent=2)
        logger.info(f"Saved analysis cache to {filepath}")
    except Exception as e:
        logger.error(f"Failed to save analysis cache: {e}")

# Function to load analysis cache from file
def load_analysis_cache(filepath: str = 'app/email/demo_analysis_cache.json'):
    """Load the analysis cache from a JSON file."""
    try:
        with open(filepath, 'r') as f:
            demo_analysis.analysis_cache = json.load(f)
        logger.info(f"Loaded analysis cache from {filepath}")
    except Exception as e:
        logger.error(f"Failed to load analysis cache: {e}") 