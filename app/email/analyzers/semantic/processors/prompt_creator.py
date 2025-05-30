"""
Prompt creation functionality for the semantic analyzer.

This module handles the creation of prompts for LLM analysis of emails.
"""
import json
import logging
from typing import Dict, Any, List, Tuple
from flask import g, current_app

from ....parsing.parser import EmailMetadata
from ..utilities.text_processor import format_list, format_dict, sanitize_text, select_important_patterns
from ..utilities.token_handler import TokenHandler


class PromptCreator:
    """Creates prompts for LLM analysis of emails."""
    
    def __init__(self, token_handler: TokenHandler = None):
        """Initialize the prompt creator.
        
        Args:
            token_handler: TokenHandler instance for token counting and truncation
        """
        self.logger = logging.getLogger(__name__)
        
        # Initialize config with default values
        self.config = type('Config', (), {
            # Default values
            'CHARACTER_LIMIT': 3000,  # Default character limit for email body
            'summary_length': 'medium',  # Default to medium summary length
            'custom_categories': []  # Default empty list for custom categories
        })
        
        # Use the provided token handler or create a new one
        self.token_handler = token_handler or TokenHandler()
        
    def _load_settings(self):
        """
        Load user settings from the database within a Flask application context.
        This should only be called when we know we're inside a Flask application context.
        """
        # Import settings utilities here to avoid circular imports
        from ..utilities.settings_util import get_summary_length, get_custom_categories
        
        try:
            # Fetch settings within application context
            self.config.summary_length = get_summary_length() or self.config.summary_length
            self.config.custom_categories = get_custom_categories() or self.config.custom_categories
        except Exception as e:
            self.logger.warning(f"Error fetching settings, using defaults: {str(e)}")
        
    def create_prompt(self, email_data: EmailMetadata, nlp_results: Dict) -> str:
        """Create a prompt for the LLM analysis.
        
        Args:
            email_data: Email metadata for analysis
            nlp_results: Dictionary containing NLP analysis results
            
        Returns:
            Prompt text for LLM analysis
        """
        try:
            # Load settings now (within a request context) rather than during initialization
            self._load_settings()
            
            # Get sanitized content (subject and body)
            subject = sanitize_text(email_data.subject)
            # Body is already truncated by preprocess_email, just sanitize
            body = sanitize_text(email_data.body)
            sender = sanitize_text(email_data.sender)
            
            # Format NLP results for prompt context
            analysis_context = self._format_analysis_context(nlp_results)
            
            # Select the appropriate summary constraints based on content length
            selected_constraints = self._select_summary_constraints(body)
            
            # Create custom categories prompt
            custom_categories_prompt = self._format_custom_categories(self.config.custom_categories)
            
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
    - true if the email requires a response, action, or is worth the user's attention
    - false if it's purely informational with no action needed
    - Be more likely to mark as true if:
      * Email contains direct questions or requests
      * Email is from a recruiter, job opportunity, or LinkedIn message
      * Email is about a failed build, CI process, or deployment
      * Email is a follow-up on previous communication
      * Email requires approval, review, or sign-off

2. category (string, exactly one of):
    - "Work" - business/professional communications
    - "Personal" - friends, family, personal matters
    - "Promotions" - marketing, sales, newsletters
    - "Informational" - notifications, updates, reports
    - Always categorize recruiter emails, job opportunities, or LinkedIn messages as "Work"
    - Always categorize build/CI/deployment notifications as "Work"

3. action_items (array of objects):
    - Each object must have:
        * "description": clear, actionable task
        * "due_date": YYYY-MM-DD or null if no specific deadline
    - Leave empty array if no actions needed
    - For emails involving job opportunities or recruiters, include specific action items like "Respond to recruiter", "Complete application", etc.
    - For build failures, include action items like "Investigate build failure"

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
    - Urgency indicators: {analysis_context['urgency']}
    - Time sensitivity: {bool(analysis_context['has_deadlines'])}
    - Question type: {analysis_context['question_type']}
    - Sentiment: {analysis_context['sentiment_strength']}
    - Email type: {analysis_context['email_type_raw']}
    
    Higher Priority Contexts (score 60-100):
    - ANY email requiring a meaningful response or action should be at least 60+
    - Emails requiring immediate action with deadlines should be 75+
    - Messages from recruiters or job opportunities needing a response should be 70+
    - Build/deployment failures needing attention should be 80+
    - Work communications that need decisions or actions should be 65-85
    - VIP contacts or direct supervisor communications should be 70+
    
    Medium Priority Contexts (score 40-59):
    - General work communications without urgency
    - Personal messages needing minor response (not urgent)
    - Informational emails related to important projects
    
    Lower Priority Contexts (score 0-39):
    - Promotional and marketing emails
    - Newsletters
    - Routine notifications
    - Purely informational updates without action items

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
        
    def _select_summary_constraints(self, body: str) -> Dict:
        """Select the appropriate summary constraints based on content length.
        
        Uses the pre-fetched summary length setting to determine the appropriate
        summary constraints.
        
        Args:
            body: The email body content
            
        Returns:
            Dictionary of summary constraints
        """
        # Use the summary length that was already fetched during initialization
        summary_length = self.config.summary_length
        
        return self._get_summary_constraints(summary_length)
        
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
            
            # Process sentiment information
            sentiment_info = self._format_sentiment_info(sentiment_analysis)
            
            # Process question information
            question_info = self._format_question_info(questions)
            
            # Process deadline/time information
            deadline_info = self._format_deadline_info(time_sensitivity)
            
            # Select most important sentiment patterns
            important_patterns = select_important_patterns(
                sentiment_analysis.get('patterns', {}),
                max_items=3
            )
            
            # Format email type information
            email_type, email_type_raw = self._format_email_type_info(email_patterns)
            
            # Format question type for priority
            question_type = self._determine_question_type(questions)
            
            # Format sentiment strength for priority
            sentiment_strength = "Strong" if sentiment_analysis.get('is_strong_sentiment', False) else "Neutral"
            
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
            
    def _format_sentiment_info(self, sentiment_analysis: Dict) -> str:
        """
        Format sentiment information from NLP results.
        
        Args:
            sentiment_analysis: Sentiment analysis results dictionary
            
        Returns:
            Formatted sentiment information string
        """
        # Format sentiment information with validation
        sentiment_info = (
            "Positive" if sentiment_analysis.get('is_positive', False) else "Negative"
            if sentiment_analysis.get('is_strong_sentiment', False) else "Neutral"
        )
        
        # Add additional sentiment indicators if present
        if sentiment_analysis.get('has_gratitude', False):
            sentiment_info += " (expressing gratitude)"
        if sentiment_analysis.get('has_dissatisfaction', False):
            sentiment_info += " (expressing dissatisfaction)"
            
        return sentiment_info
    
    def _format_question_info(self, questions: Dict) -> List[str]:
        """
        Format question information from NLP results.
        
        Args:
            questions: Question analysis results dictionary
            
        Returns:
            List of formatted question information strings
        """
        question_info = []
        
        # Add direct questions if present (limit to top 2)
        if questions.get('direct_questions'):
            direct_q = [q[:100] for q in questions['direct_questions'][:2]]  # Truncate long questions
            question_info.append(f"Direct questions: {format_list(direct_q)}")
            
        # Add request questions if present (limit to top 2)
        if questions.get('request_questions'):
            request_q = [q[:100] for q in questions['request_questions'][:2]]  # Truncate long questions
            question_info.append(f"Requests: {format_list(request_q)}")
            
        return question_info
    
    def _format_deadline_info(self, time_sensitivity: Dict) -> List[str]:
        """
        Format deadline information from NLP results.
        
        Args:
            time_sensitivity: Time sensitivity analysis results dictionary
            
        Returns:
            List of formatted deadline information strings
        """
        deadline_info = []
        
        # Add deadline phrases if present (limit to top 2)
        if time_sensitivity.get('has_deadline', False):
            deadline_info.extend([p[:100] for p in time_sensitivity.get('deadline_phrases', [])[:2]])
            
        # Add time references if present (limit to top 2)
        if time_sensitivity.get('time_references'):
            deadline_info.extend([r[:50] for r in time_sensitivity.get('time_references', [])[:2]])
            
        return deadline_info
    
    def _format_email_type_info(self, email_patterns: Dict) -> Tuple[str, str]:
        """
        Format email type information from NLP results.
        
        Args:
            email_patterns: Email patterns analysis results dictionary
            
        Returns:
            Tuple of (formatted email type string, raw email type string)
        """
        # Determine email type string for display
        email_type = "Standard"
        if email_patterns.get('is_automated', False):
            email_type = "Automated"
        if email_patterns.get('is_bulk', False):
            email_type = "Bulk/Marketing" if email_type == "Standard" else email_type + ", Bulk/Marketing"
            
        # Format email type raw string for priority calculation
        email_type_raw = ""
        if email_patterns.get('is_automated', False):
            email_type_raw = "Automated"
        if email_patterns.get('is_bulk', False):
            email_type_raw = "Bulk" if not email_type_raw else email_type_raw + ", Bulk"
            
        return email_type, email_type_raw
    
    def _determine_question_type(self, questions: Dict) -> str:
        """
        Determine question type for priority calculation.
        
        Args:
            questions: Question analysis results dictionary
            
        Returns:
            Question type string
        """
        if questions.get('request_questions'):
            return "Requests present"
        elif questions.get('direct_questions'):
            return "Direct questions"
        else:
            return "No questions"
            
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