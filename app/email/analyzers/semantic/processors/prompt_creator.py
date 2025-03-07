"""
Prompt creation functionality for the semantic analyzer.

This module handles the creation of prompts for LLM analysis of emails.
"""
import json
import logging
from typing import Dict, Any, List
from flask import g

from ....core.email_parsing import EmailMetadata
from ..utilities.text_processor import format_list, format_dict, sanitize_text, select_important_patterns


class PromptCreator:
    """Creates prompts for LLM analysis of emails."""
    
    def __init__(self):
        """Initialize the prompt creator."""
        self.logger = logging.getLogger(__name__)
        
    def create_prompt(self, email_data: EmailMetadata, nlp_results: Dict) -> str:
        """Create a prompt for the LLM analysis.
        
        Args:
            email_data: Parsed email data as EmailMetadata object
            nlp_results: Results from NLP analysis
            
        Returns:
            String prompt for the LLM
        """
        try:
            # Validate and sanitize NLP results
            if nlp_results is None:
                self.logger.warning("NLP results are None, using empty dict")
                nlp_results = {}
            
            # Get user settings from current app context
            user_settings = {}
            if hasattr(g, 'user') and hasattr(g.user, 'settings'):
                user_settings = g.user.settings

            # Get custom categories from user settings
            custom_categories = g.user.get_setting('ai_features.custom_categories', []) if hasattr(g, 'user') else []
            
            # Format custom categories for prompt if they exist
            custom_categories_prompt = self._format_custom_categories(custom_categories)

            # Ensure all expected NLP result sections exist with defaults
            nlp_results = self._ensure_complete_nlp_results(nlp_results)
            
            # Get summary length preference and set constraints
            summary_length = g.user.get_setting('ai_features.summary_length', 'medium')
            selected_constraints = self._get_summary_constraints(summary_length)

            # Get and validate email content
            subject = getattr(email_data, 'subject', 'No subject')
            sender = getattr(email_data, 'sender', 'Unknown sender')
            body = getattr(email_data, 'body', '')

            # Ensure content is properly sanitized
            subject = sanitize_text(subject)
            sender = sanitize_text(sender)
            body = sanitize_text(body) if body else ""

            # Process NLP results with error handling
            analysis_context = self._format_analysis_context(nlp_results)
            
            # Create the prompt with validated data and limited content
            prompt = f"""You are an email analysis assistant. Analyze the following email and provide a structured assessment to help prioritize inbox management.
EMAIL CONTENT
-------------
Subject: {subject}
From: {sender}
Content: {body}

CONTEXT
-------
NLP Analysis:
1. Content Classification:
   - Key Entities: {analysis_context['entities']}
   - Main Phrases: {analysis_context['phrases']}
   - Urgency: {analysis_context['urgency']}
   - Email Type: {analysis_context['email_type']}

2. Sentiment and Tone:
   - Overall: {analysis_context['sentiment']}
   - Key Indicators: {analysis_context['sentiment_indicators']}

3. Interaction Patterns:
   - Questions: {analysis_context['question_count']} detected
   {analysis_context['questions']}

4. Time Sensitivity:
   {analysis_context['deadlines']}

TASK
----
Analyze this email and provide a JSON response with the following fields:

1. needs_action (boolean):
    - true if the email requires a response or action
    - false if it's purely informational

2. category (string, exactly one of):
    - "Work" - business/professional communications
    - "Personal" - friends, family, personal matters
    - "Promotions" - marketing, sales, newsletters
    - "Informational" - notifications, updates, reports

3. action_items (array of objects):
    - Each object must have:
        * "description": clear, actionable task
        * "due_date": YYYY-MM-DD or null if no specific deadline
    - Leave empty array if no actions needed

4. summary (string):
    {selected_constraints['guidance']}
    STRICT CONSTRAINTS:
    - Maximum {selected_constraints['max_words']} words
    - Maximum {selected_constraints['max_sentences']} sentences
    - Focus on key decisions and actions needed
    - Be concise but informative

5. priority (integer 0-100):
    - 0-20: Can be ignored/archived
    - 21-40: Low priority
    - 41-60: Medium priority
    - 61-80: High priority
    - 81-100: Urgent/immediate attention
    Consider the following in priority scoring:
    - Urgency indicators: {nlp_results['urgency']}
    - Time sensitivity: {bool(analysis_context['has_deadlines'])}
    - Question type: {analysis_context['question_type']}
    - Sentiment: {analysis_context['sentiment_strength']}
    - Email type: {analysis_context['email_type_raw']}

{custom_categories_prompt}

OUTPUT FORMAT
------------
{self._get_schema_template(bool(custom_categories_prompt))}
"""
            return prompt

        except Exception as e:
            self.logger.error(f"Error creating prompt: {str(e)}")
            from ....models.exceptions import LLMProcessingError
            raise LLMProcessingError(f"Failed to create prompt: {str(e)}")
            
    def _format_custom_categories(self, custom_categories: List[Dict]) -> str:
        """Format custom categories for inclusion in the prompt.
        
        Args:
            custom_categories: List of category dictionaries
            
        Returns:
            Formatted string for prompt
        """
        if not custom_categories:
            return ""
            
        result = "\n6. custom_categories (object with string values):\n"
        result += "    For each category below, assign either:\n"
        result += "    - One of the specified values if the category applies to this email\n"
        result += "    - null if the category does not apply to this email\n\n"
        
        for category in custom_categories:
            name = category.get('name', '').strip()
            values = category.get('values', [])
            if name and values:
                valid_values = [v.strip() for v in values if v.strip()]
                if valid_values:
                    result += f"    - {name}: exactly one of {valid_values} or null\n"
                    
        return result
        
    def _ensure_complete_nlp_results(self, nlp_results: Dict) -> Dict:
        """Ensure all expected NLP result sections exist with defaults.
        
        Args:
            nlp_results: Raw NLP results
            
        Returns:
            Complete NLP results with defaults for missing fields
        """
        return {
            'entities': nlp_results.get('entities', {}),
            'key_phrases': nlp_results.get('key_phrases', []),
            'urgency': nlp_results.get('urgency', False),
            'sentiment_analysis': nlp_results.get('sentiment_analysis', {
                'scores': {'positive': 0.5, 'negative': 0.5},
                'is_positive': False,
                'is_strong_sentiment': False,
                'has_gratitude': False,
                'has_dissatisfaction': False,
                'patterns': {}
            }),
            'email_patterns': nlp_results.get('email_patterns', {
                'is_bulk': False,
                'is_automated': False,
                'bulk_indicators': [],
                'automated_indicators': []
            }),
            'questions': nlp_results.get('questions', {
                'has_questions': False,
                'direct_questions': [],
                'rhetorical_questions': [],
                'request_questions': [],
                'question_count': 0
            }),
            'time_sensitivity': nlp_results.get('time_sensitivity', {
                'has_deadline': False,
                'deadline_phrases': [],
                'time_references': []
            })
        }
        
    def _get_summary_constraints(self, summary_length: str) -> Dict:
        """Get summary constraints based on summary length preference.
        
        Args:
            summary_length: Desired summary length (short, medium, long)
            
        Returns:
            Dictionary of constraints
        """
        summary_constraints = {
            'short': {
                'guidance': """Generate a 1-2 sentence summary (max 25 words) that captures:
- The core message or main request
- The most critical action item (if any)
Example format: "Request for project timeline update. Needs response with Q3 milestones by Friday."
""",
                'max_words': 25,
                'max_sentences': 2
            },
            'medium': {
                'guidance': """Generate a 3-4 sentence summary (40-60 words) that includes:
- The core message or request
- Key context or background
- Important deadlines or next steps
- Any critical implications
Example format: "Budget approval request for Q3 marketing campaign. Previous quarter showed 20% ROI. Requesting $50K for digital ads and events. Approval needed by July 1st to meet campaign timeline."
""",
                'max_words': 60,
                'max_sentences': 4
            },
            'long': {
                'guidance': """Generate a comprehensive 5-7 sentence summary (80-120 words) covering:
- Complete context and background
- All key points and requests
- Detailed action items and deadlines
- Stakeholders involved and their roles
- Implications and potential impact
- Related projects or dependencies
Example format: "Quarterly strategy review for APAC expansion. Team reports 30% growth in existing markets, with China and Japan exceeding targets. Three new market opportunities identified: Vietnam, Thailand, and Indonesia. Local partnerships needed for regulatory compliance, estimated setup time 6-8 months. Budget impact of $2M over 18 months. Legal team review required for partnership agreements. VP approval needed by August for 2024 planning."
""",
                'max_words': 120,
                'max_sentences': 7
            }
        }
        
        # Get constraints for the selected length, with fallback to medium
        selected_constraints = summary_constraints.get(summary_length)
        if not selected_constraints:
            self.logger.warning(f"Invalid summary length '{summary_length}', falling back to medium")
            selected_constraints = summary_constraints['medium']
            
        return selected_constraints
        
    def _format_analysis_context(self, nlp_results: Dict) -> Dict:
        """Format NLP results into a context dictionary for prompt creation.
        
        Args:
            nlp_results: Processed NLP results
            
        Returns:
            Formatted context dictionary
        """
        try:
            sentiment_analysis = nlp_results['sentiment_analysis']
            email_patterns = nlp_results['email_patterns']
            questions = nlp_results['questions']
            time_sensitivity = nlp_results['time_sensitivity']
            
            # Format sentiment information with validation
            sentiment_info = (
                "Positive" if sentiment_analysis.get('is_positive', False) else "Negative"
                if sentiment_analysis.get('is_strong_sentiment', False) else "Neutral"
            )
            if sentiment_analysis.get('has_gratitude', False):
                sentiment_info += " (expressing gratitude)"
            if sentiment_analysis.get('has_dissatisfaction', False):
                sentiment_info += " (expressing dissatisfaction)"
            
            # Format question information with validation (limit to top 2 of each type)
            question_info = []
            if questions.get('direct_questions'):
                direct_q = [q[:100] for q in questions['direct_questions'][:2]]  # Truncate long questions
                question_info.append(f"Direct questions: {format_list(direct_q)}")
            if questions.get('request_questions'):
                request_q = [q[:100] for q in questions['request_questions'][:2]]  # Truncate long questions
                question_info.append(f"Requests: {format_list(request_q)}")
            
            # Format time sensitivity information with validation (limit phrases)
            deadline_info = []
            if time_sensitivity.get('has_deadline', False):
                deadline_info.extend([p[:100] for p in time_sensitivity.get('deadline_phrases', [])[:2]])
            if time_sensitivity.get('time_references'):
                deadline_info.extend([r[:50] for r in time_sensitivity.get('time_references', [])[:2]])
            
            # Select most important sentiment patterns
            important_patterns = select_important_patterns(
                sentiment_analysis.get('patterns', {}),
                max_items=3
            )
            
            # Determine email type string
            email_type = "Standard"
            if email_patterns.get('is_automated', False):
                email_type = "Automated"
            if email_patterns.get('is_bulk', False):
                email_type = "Bulk/Marketing" if email_type == "Standard" else email_type + ", Bulk/Marketing"
                
            # Determine question type for priority
            question_type = "No questions"
            if questions.get('request_questions'):
                question_type = "Requests present"
            elif questions.get('direct_questions'):
                question_type = "Direct questions"
                
            # Format sentiment strength for priority
            sentiment_strength = "Strong" if sentiment_analysis.get('is_strong_sentiment', False) else "Neutral"
            
            # Format email type raw for priority
            email_type_raw = ""
            if email_patterns.get('is_automated', False):
                email_type_raw = "Automated"
            if email_patterns.get('is_bulk', False):
                email_type_raw = "Bulk" if not email_type_raw else email_type_raw + ", Bulk"
            
            return {
                'entities': format_dict(nlp_results['entities']),
                'phrases': format_list(nlp_results['key_phrases']),
                'urgency': "Detected" if nlp_results['urgency'] else "Not detected",
                'email_type': email_type,
                'sentiment': sentiment_info,
                'sentiment_indicators': format_dict(important_patterns),
                'question_count': questions.get('question_count', 0),
                'questions': chr(10).join(question_info) if question_info else "   - No questions detected",
                'deadlines': "   - Deadlines/Time References: " + "; ".join(deadline_info) if deadline_info else "   - No specific deadlines detected",
                'has_deadlines': bool(deadline_info),
                'question_type': question_type,
                'sentiment_strength': sentiment_strength,
                'email_type_raw': email_type_raw
            }
            
        except Exception as e:
            self.logger.error(f"Error processing NLP results: {e}")
            # Use default values if processing fails
            return {
                'entities': "{}",
                'phrases': "[]",
                'urgency': "Not detected",
                'email_type': "Standard",
                'sentiment': "Neutral",
                'sentiment_indicators': "{}",
                'question_count': 0,
                'questions': "   - No questions detected",
                'deadlines': "   - No specific deadlines detected",
                'has_deadlines': False,
                'question_type': "No questions",
                'sentiment_strength': "Neutral",
                'email_type_raw': ""
            }
            
    def _get_schema_template(self, custom_categories_prompt: bool) -> str:
        """Get the JSON schema template.
        
        Args:
            custom_categories_prompt: Whether custom categories are included
            
        Returns:
            JSON schema template string
        """
        base_schema = {
            "needs_action": "boolean",
            "category": "string",
            "action_items": "array",
            "summary": "string",
            "priority": "integer"
        }
        
        if custom_categories_prompt:
            base_schema["custom_categories"] = "object"
            
        schema_str = json.dumps(base_schema, indent=4)
        return f"Return only valid JSON matching this schema:\n{schema_str}" 