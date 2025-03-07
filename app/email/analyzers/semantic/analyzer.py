import json
import logging
from typing import Dict, Any, List, Tuple
from flask import g, current_app
import tiktoken
import re
import time
import asyncio

from ...core.email_parsing import EmailMetadata
from ...models.exceptions import LLMProcessingError
from ..base import BaseAnalyzer

class SemanticAnalyzer(BaseAnalyzer):
    """Analyzes emails using LLM for semantic understanding."""
    
    def __init__(self):
        """Initialize the semantic analyzer."""
        self.logger = logging.getLogger(__name__)
        self.model = "gpt-4o-mini"  # Default model - will be overridden by user settings
        self.max_content_tokens = 1000  # Default to medium length - will be overridden by user settings
        try:
            self.encoding = tiktoken.get_encoding("cl100k_base")  # Explicitly use cl100k_base encoding
        except Exception as e:
            self.logger.error(f"Failed to get tiktoken encoding: {e}")
            self.encoding = None
    
    def count_tokens(self, text: str) -> int:
        """Count the number of tokens in a text string."""
        return len(self.encoding.encode(text))
    
    def _truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """Truncate text to a maximum number of tokens while preserving sentence boundaries.
        
        Args:
            text: The text to truncate
            max_tokens: Maximum number of tokens to keep
            
        Returns:
            Truncated text ending at a sentence boundary, with a [truncated] marker if needed
        """
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
    
    def _select_important_entities(self, entities: List[Dict]) -> List[Dict]:
        """Select the most important named entities."""
        # Sort entities by frequency and importance
        sorted_entities = sorted(
            entities,
            key=lambda x: (x.get('count', 1), len(x.get('text', '')), x.get('label', '') in ['PERSON', 'ORG']),
            reverse=True
        )
        # Return top 5 most important entities
        return sorted_entities[:5]
    
    def _select_important_keywords(self, keywords: List[str], max_keywords: int = 5) -> List[str]:
        """Select the most important keywords."""
        # Sort keywords by length (longer usually more specific) and take top N
        return sorted(keywords, key=len, reverse=True)[:max_keywords]
    
    def _strip_html(self, html_content: str) -> str:
        """Extract readable text from HTML content.
        
        This method:
        1. Removes script and style elements
        2. Converts <br> and </p> to newlines
        3. Strips all other HTML tags
        4. Normalizes whitespace
        5. Preserves important line breaks
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

    async def analyze(self, email_data: EmailMetadata, nlp_results: Dict) -> Dict[str, Any]:
        """
        Analyze email content using LLM.
        
        Args:
            email_data: Parsed email data as EmailMetadata object
            nlp_results: Results from NLP analysis
            
        Returns:
            Dictionary containing LLM analysis results and usage statistics
        """
        try:
            # Get user settings from current app context
            user_settings = {}
            if hasattr(g, 'user') and hasattr(g.user, 'settings'):
                user_settings = g.user.settings
                ai_settings = g.user.get_settings_group('ai_features')
                # Log AI config once during initialization
                self.logger.debug(
                    "AI Configuration:\n"
                    f"    Enabled: {ai_settings.get('enabled', True)}\n"
                    f"    Model: {ai_settings.get('model_type', 'gpt-4o-mini')}\n"
                    f"    Context Length: {ai_settings.get('context_length', 1000)}\n"
                    f"    Summary Length: {ai_settings.get('summary_length', 'medium')}"
                )

            # Check if AI features are enabled (default to True if setting not found)
            ai_enabled = g.user.get_setting('ai_features.enabled', True) if hasattr(g, 'user') else True

            if not ai_enabled:
                self.logger.info("AI features disabled, returning basic metadata")
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
                    'email_id': getattr(email_data, 'id', None),
                    'ai_enabled': False
                }

            # Get model type from user settings
            raw_model_type = g.user.get_setting('ai_features.model_type')
            self.model = raw_model_type or 'gpt-4o-mini'
            
            # Get context length from user settings and convert to int
            raw_context_length = g.user.get_setting('ai_features.context_length')
            context_length = int(raw_context_length) if raw_context_length else 1000
            self.max_content_tokens = context_length

            # Get summary length preference and set constraints
            summary_length = g.user.get_setting('ai_features.summary_length', 'medium')
            
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
            
            # Set max response tokens based on summary length
            max_response_tokens = {
                'short': 150,   # Brief summary and key points
                'medium': 300,  # Detailed summary and analysis
                'long': 500     # Comprehensive analysis
            }.get(summary_length, 300)  # Default to medium if unknown value
            
            self.logger.debug(
                f"Analysis config - Model: {self.model}, Context: {context_length}, "
                f"Summary: {summary_length}, Max Response: {max_response_tokens}"
            )

            # Ensure email_data is properly structured
            if not isinstance(email_data, EmailMetadata):
                self.logger.error(f"email_data is not an EmailMetadata object (got {type(email_data)})")
                if isinstance(email_data, dict):
                    email_data = EmailMetadata(**email_data)
                else:
                    raise ValueError("Invalid email_data format: must be EmailMetadata or dict")

            # Validate required fields
            required_fields = ['subject', 'sender', 'body']
            for field in required_fields:
                if not hasattr(email_data, field) or getattr(email_data, field) is None:
                    self.logger.error(f"Missing required field '{field}' in email_data")
                    raise ValueError(f"Missing required field: {field}")
            
            # Clean HTML first, before any analysis
            clean_body = self._strip_html(email_data.body)
            truncated_body = self._truncate_to_tokens(clean_body, self.max_content_tokens)
            
            # Create prompt using the cleaned and truncated body
            prompt = self._create_prompt(
                EmailMetadata(
                    id=email_data.id,
                    subject=email_data.subject,
                    sender=email_data.sender,
                    body=truncated_body,
                    date=email_data.date
                ),
                nlp_results
            )
            prompt_tokens = self.count_tokens(prompt)
            
            # Condense email analysis logging to one line
            self.logger.info(f"Processing email {email_data.id} - Model: {self.model}, Prompt Tokens: {prompt_tokens}, Max Response: {max_response_tokens}")
            
            # Get OpenAI client using the app's getter function
            try:
                if not hasattr(current_app, 'get_openai_client'):
                    raise ValueError("OpenAI client getter not initialized")
                client = current_app.get_openai_client()
                if client is None:
                    raise ValueError("OpenAI client is None")
            except Exception as e:
                self.logger.error(f"Failed to get OpenAI client: {e}")
                raise LLMProcessingError(f"OpenAI client initialization failed: {e}")
            
            # Make the API call with the selected model
            try:
                response = await client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are an AI assistant analyzing emails."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,  # Lower temperature for more consistent outputs
                    max_tokens=max_response_tokens,
                    response_format={ "type": "json_object" }  # Force JSON response
                )
            except Exception as e:
                self.logger.error(f"OpenAI API call failed: {e}")
                raise LLMProcessingError(f"OpenAI API call failed: {e}")
            
            # Calculate usage and costs
            prompt_tokens = response.usage.prompt_tokens
            completion_tokens = response.usage.completion_tokens
            total_tokens = response.usage.total_tokens
            
            cost_per_1k = {
                "gpt-4o-mini": {
                    "input": 0.00015,
                    "output": 0.0006
                },
                "gpt-4o": {
                    "input": 0.005,
                    "output": 0.015
                }
            }.get(self.model, {
                "input": 0.00015,  # Default to gpt-4o-mini rates
                "output": 0.0006
            })
            
            input_cost = (prompt_tokens / 1000) * cost_per_1k["input"]
            output_cost = (completion_tokens / 1000) * cost_per_1k["output"]
            total_cost = input_cost + output_cost
            
            # Condense completion logging to one line
            self.logger.info(f"Completed email {email_data.id} - Tokens: {prompt_tokens}/{completion_tokens}/{total_tokens} (in/out/total), Cost: ${total_cost:.4f}")
            
            # Parse the response
            analysis = self._parse_response(response.choices[0].message.content)
            
            # Add usage statistics
            analysis.update({
                'model': self.model,
                'total_tokens': total_tokens,
                'prompt_tokens': prompt_tokens,
                'completion_tokens': completion_tokens,
                'cost': total_cost,
                'email_id': getattr(email_data, 'id', None),  # Include email ID if available
                'ai_enabled': True
            })
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"LLM analysis failed: {str(e)}")
            raise LLMProcessingError(f"LLM analysis failed: {str(e)}")
    
    def _format_list(self, items: list) -> str:
        """Safely format a list of items."""
        if not items:
            return "[]"
        # Limit to first 3 items and truncate each item to 50 chars
        formatted_items = [str(item)[:50] for item in items[:3]]
        return str(formatted_items)

    def _format_dict(self, d: dict) -> str:
        """Safely format a dictionary."""
        if not d:
            return "{}"
        # Limit to first 3 items and truncate values to 50 chars
        formatted_dict = {str(k): str(v)[:50] for k, v in list(d.items())[:3]}
        return str(formatted_dict)

    def _select_important_patterns(self, patterns: dict, max_items: int = 3) -> dict:
        """Select the most important sentiment patterns."""
        if not patterns:
            return {}
        # Sort by value (frequency) and take top N
        sorted_patterns = sorted(patterns.items(), key=lambda x: x[1], reverse=True)
        return dict(sorted_patterns[:max_items])

    def _create_prompt(self, email_data: EmailMetadata, nlp_results: Dict) -> str:
        """Create a prompt for the LLM analysis."""
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
            custom_categories_prompt = ""
            if custom_categories:
                custom_categories_prompt = "\n6. custom_categories (object with string values):\n"
                custom_categories_prompt += "    For each category below, assign either:\n"
                custom_categories_prompt += "    - One of the specified values if the category applies to this email\n"
                custom_categories_prompt += "    - null if the category does not apply to this email\n\n"
                for category in custom_categories:
                    name = category.get('name', '').strip()
                    values = category.get('values', [])
                    if name and values:
                        valid_values = [v.strip() for v in values if v.strip()]
                        if valid_values:
                            custom_categories_prompt += f"    - {name}: exactly one of {valid_values} or null\n"

            # Ensure all expected NLP result sections exist with defaults
            nlp_results = {
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

            # Get summary length preference and set constraints
            summary_length = g.user.get_setting('ai_features.summary_length', 'medium')
            
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

            # Get and validate email content
            subject = getattr(email_data, 'subject', 'No subject')
            sender = getattr(email_data, 'sender', 'Unknown sender')
            body = getattr(email_data, 'body', '')

            # Ensure content is properly sanitized
            subject = self._sanitize_text(subject)
            sender = self._sanitize_text(sender)
            body = self._sanitize_text(body) if body else ""

            # Process NLP results with error handling
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
                    question_info.append(f"Direct questions: {self._format_list(direct_q)}")
                if questions.get('request_questions'):
                    request_q = [q[:100] for q in questions['request_questions'][:2]]  # Truncate long questions
                    question_info.append(f"Requests: {self._format_list(request_q)}")
                
                # Format time sensitivity information with validation (limit phrases)
                deadline_info = []
                if time_sensitivity.get('has_deadline', False):
                    deadline_info.extend([p[:100] for p in time_sensitivity.get('deadline_phrases', [])[:2]])
                if time_sensitivity.get('time_references'):
                    deadline_info.extend([r[:50] for r in time_sensitivity.get('time_references', [])[:2]])
                
                # Select most important sentiment patterns
                important_patterns = self._select_important_patterns(
                    sentiment_analysis.get('patterns', {}),
                    max_items=3
                )
                
            except Exception as e:
                self.logger.error(f"Error processing NLP results: {e}")
                # Use default values if processing fails
                sentiment_info = "Neutral"
                question_info = []
                deadline_info = []
                important_patterns = {}
            
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
   - Key Entities: {self._format_dict(nlp_results['entities'])}
   - Main Phrases: {self._format_list(nlp_results['key_phrases'])}
   - Urgency: {"Detected" if nlp_results['urgency'] else "Not detected"}
   - Email Type: {"Automated" if email_patterns.get('is_automated', False) else ""}{"Bulk/Marketing" if email_patterns.get('is_bulk', False) else ""}{"Standard" if not email_patterns.get('is_automated', False) and not email_patterns.get('is_bulk', False) else ""}

2. Sentiment and Tone:
   - Overall: {sentiment_info}
   - Key Indicators: {self._format_dict(important_patterns)}

3. Interaction Patterns:
   - Questions: {questions.get('question_count', 0)} detected
   {chr(10).join(question_info) if question_info else "   - No questions detected"}

4. Time Sensitivity:
   {"   - Deadlines/Time References: " + "; ".join(deadline_info) if deadline_info else "   - No specific deadlines detected"}

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
    - Time sensitivity: {bool(deadline_info)}
    - Question type: {"Requests present" if questions.get('request_questions') else "Direct questions" if questions.get('direct_questions') else "No questions"}
    - Sentiment: {"Strong" if sentiment_analysis.get('is_strong_sentiment', False) else "Neutral"}
    - Email type: {"Automated" if email_patterns.get('is_automated', False) else ""}{"Bulk" if email_patterns.get('is_bulk', False) else ""}

{custom_categories_prompt}

OUTPUT FORMAT
------------
{self._get_schema_template(bool(custom_categories_prompt))}
"""
            return prompt

        except Exception as e:
            self.logger.error(f"Error creating prompt: {str(e)}")
            raise LLMProcessingError(f"Failed to create prompt: {str(e)}")

    def _sanitize_text(self, text: str) -> str:
        """Sanitize text to prevent prompt injection and ensure valid formatting."""
        if not text:
            return ""
        # Remove any potential markdown or prompt injection characters
        text = re.sub(r'[`*_~<>{}[\]()#+-]', ' ', str(text))
        # Normalize whitespace
        text = ' '.join(text.split())
        return text

    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """Parse the LLM response into a structured format."""
        try:
            # First try to extract JSON if response is wrapped in markdown code blocks
            if '```json' in response_text:
                json_content = response_text.split('```json')[1].split('```')[0].strip()
            elif '```' in response_text:
                json_content = response_text.split('```')[1].split('```')[0].strip()
            else:
                json_content = response_text.strip()
                
            result = json.loads(json_content)
            
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
                result['priority'] = max(0, min(100, int(result['priority'])))
            
            return result
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse LLM response as JSON: {e}")
            raise LLMProcessingError(f"Invalid JSON response: {e}")
        except Exception as e:
            self.logger.error(f"Error parsing LLM response: {e}")
            raise LLMProcessingError(f"Error parsing response: {e}")

    def _get_schema_template(self, custom_categories_prompt: bool) -> str:
        """Get the JSON schema template."""
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

    async def analyze_batch(self, emails: List[Tuple[EmailMetadata, Dict]], max_batch_size: int = 20) -> List[Dict[str, Any]]:
        """Analyze a batch of emails using a single LLM request.
        
        Args:
            emails: List of tuples containing (EmailMetadata, nlp_results)
            max_batch_size: Maximum number of emails to process in a single batch
            
        Returns:
            List of analysis results corresponding to input emails
        """
        try:
            # Get user settings
            user_settings = {}
            if hasattr(g, 'user') and hasattr(g.user, 'settings'):
                user_settings = g.user.settings
                ai_settings = g.user.get_settings_group('ai_features')

            # Check if AI features are enabled
            ai_enabled = g.user.get_setting('ai_features.enabled', True) if hasattr(g, 'user') else True
            if not ai_enabled:
                return [self._create_disabled_response(email.id) for email, _ in emails]

            # Get model and context settings
            self.model = g.user.get_setting('ai_features.model_type', 'gpt-4o-mini')
            raw_context_length = g.user.get_setting('ai_features.context_length')
            self.max_content_tokens = int(raw_context_length) if raw_context_length else 1000

            # Process emails in batches of max_batch_size
            results = []
            for i in range(0, len(emails), max_batch_size):
                batch = emails[i:i + max_batch_size]
                batch_results = await self._process_batch(batch)
                results.extend(batch_results)

            return results

        except Exception as e:
            self.logger.error(f"Batch analysis failed: {str(e)}")
            raise LLMProcessingError(f"Batch analysis failed: {str(e)}")

    async def _process_batch(self, batch: List[Tuple[EmailMetadata, Dict]]) -> List[Dict[str, Any]]:
        """Process a single batch of emails."""
        try:
            # Create prompts for all emails in batch
            prompts = []
            for email_data, nlp_results in batch:
                # Clean HTML and truncate content
                clean_body = self._strip_html(email_data.body)
                truncated_body = self._truncate_to_tokens(clean_body, self.max_content_tokens)
                
                # Create clean version of email metadata
                clean_email = EmailMetadata(
                    id=email_data.id,
                    subject=email_data.subject,
                    sender=email_data.sender,
                    body=truncated_body,
                    date=email_data.date
                )
                
                prompt = self._create_prompt(clean_email, nlp_results)
                prompts.append(prompt)

            # Create messages for the batch
            messages = []
            for prompt in prompts:
                messages.append([
                    {"role": "system", "content": "You are an AI assistant analyzing emails."},
                    {"role": "user", "content": prompt}
                ])

            # Get OpenAI client
            try:
                if not hasattr(current_app, 'get_openai_client'):
                    raise ValueError("OpenAI client getter not initialized")
                client = current_app.get_openai_client()
                if client is None:
                    raise ValueError("OpenAI client is None")
            except Exception as e:
                self.logger.error(f"Failed to get OpenAI client: {e}")
                raise LLMProcessingError(f"OpenAI client initialization failed: {e}")

            # Make batch API call
            try:
                start_time = time.time()
                self.logger.info(f"Processing batch of {len(batch)} emails with model {self.model}")
                
                # Process messages in parallel with asyncio.gather
                async def process_message(msg):
                    return await client.chat.completions.create(
                        model=self.model,
                        messages=msg,
                        temperature=0.1,
                        max_tokens=300,
                        response_format={ "type": "json_object" }
                    )
                
                responses = await asyncio.gather(*[process_message(msg) for msg in messages])
                
                processing_time = time.time() - start_time
                self.logger.debug(f"Batch processing completed in {processing_time:.2f} seconds")

            except Exception as e:
                self.logger.error(f"OpenAI batch API call failed: {e}")
                raise LLMProcessingError(f"OpenAI batch API call failed: {e}")

            # Process responses
            results = []
            total_tokens = 0
            total_cost = 0

            for i, response in enumerate(responses):
                email_data, _ = batch[i]
                
                # Parse the response
                analysis = self._parse_response(response.choices[0].message.content)
                
                # Calculate usage for this completion
                prompt_tokens = response.usage.prompt_tokens
                completion_tokens = response.usage.completion_tokens
                total_tokens += prompt_tokens + completion_tokens
                
                # Calculate cost
                cost_per_1k = {
                    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
                    "gpt-4o": {"input": 0.005, "output": 0.015}
                }.get(self.model, {"input": 0.00015, "output": 0.0006})
                
                input_cost = (prompt_tokens / 1000) * cost_per_1k["input"]
                output_cost = (completion_tokens / 1000) * cost_per_1k["output"]
                email_cost = input_cost + output_cost
                total_cost += email_cost

                # Add usage statistics
                analysis.update({
                    'model': self.model,
                    'total_tokens': prompt_tokens + completion_tokens,
                    'prompt_tokens': prompt_tokens,
                    'completion_tokens': completion_tokens,
                    'cost': email_cost,
                    'email_id': email_data.id,
                    'ai_enabled': True
                })
                
                results.append(analysis)

            self.logger.info(f"Batch processing stats: emails processed: {len(batch)}, total_tokens: {total_tokens}, avg_tokens: {total_tokens/len(batch):.1f}, total_cost: ${total_cost:.4f}")
            self.logger.debug(
                f"Batch processing stats:\n"
                f"    Emails processed: {len(batch)}\n"
                f"    Total tokens: {total_tokens}\n"
                f"    Total cost: ${total_cost:.4f}\n"
                f"    Average tokens per email: {total_tokens/len(batch):.1f}"
            )

            return results

        except Exception as e:
            self.logger.error(f"Batch processing failed: {str(e)}")
            raise LLMProcessingError(f"Batch processing failed: {str(e)}")

    def _create_disabled_response(self, email_id: str) -> Dict[str, Any]:
        """Create a basic response when AI is disabled."""
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