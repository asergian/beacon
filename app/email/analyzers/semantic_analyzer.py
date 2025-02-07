import json
import logging
from typing import Dict, Any, List
from flask import g, current_app
import tiktoken

#from ..models.processed_email import ProcessedEmail
from ..core.email_parsing import EmailMetadata
from ..models.exceptions import LLMProcessingError

class SemanticAnalyzer:
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
        import re
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
        import re
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
                self.logger.debug(
                    "AI Configuration:\n"
                    f"    Enabled: {ai_settings.get('enabled', True)}\n"
                    f"    Model: {ai_settings.get('model_type', 'gpt-4o-mini')}\n"
                    f"    Context Length: {ai_settings.get('context_length', 1000)}\n"
                    f"    Summary Length: {ai_settings.get('summary_length', 'medium')}"
                )

            # Check if AI summarization is enabled
            ai_enabled = user_settings.get('ai_features.enabled', True)

            if not ai_enabled:
                self.logger.info("AI features disabled, returning basic analysis")
                return {
                    'needs_action': False,
                    'category': 'Informational',
                    'action_items': [],
                    'summary': None,
                    'priority': 50,
                    'model': self.model,
                    'total_tokens': 0,
                    'prompt_tokens': 0,
                    'completion_tokens': 0,
                    'cost': 0
                }

            # Get model type from user settings
            raw_model_type = g.user.get_setting('ai_features.model_type')
            self.model = raw_model_type or 'gpt-4o-mini'
            
            # Get context length from user settings and convert to int
            raw_context_length = g.user.get_setting('ai_features.context_length')
            context_length = int(raw_context_length) if raw_context_length else 1000
            self.max_content_tokens = context_length

            # Get summary length from user settings
            raw_summary_length = g.user.get_setting('ai_features.summary_length')
            summary_length = raw_summary_length or 'medium'

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
            
            self.logger.info(
                "Starting Email Analysis\n"
                f"    Email ID: {email_data.id}\n"
                f"    Model: {self.model}\n"
                f"    Prompt Tokens: {prompt_tokens}\n"
                f"    Max Response: {max_response_tokens} tokens"
            )
            
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
            
            self.logger.info(
                "Analysis Complete\n"
                f"    Email ID: {email_data.id}\n"
                f"    Token Usage:\n"
                f"        Input: {prompt_tokens}\n"
                f"        Output: {completion_tokens}\n"
                f"        Total: {total_tokens}\n"
                f"    Cost: ${total_cost:.4f}"
            )
            
            # Parse the response
            analysis = self._parse_response(response.choices[0].message.content)
            
            # Add usage statistics
            analysis.update({
                'model': self.model,
                'total_tokens': total_tokens,
                'prompt_tokens': prompt_tokens,
                'completion_tokens': completion_tokens,
                'cost': total_cost,
                'email_id': getattr(email_data, 'id', None)  # Include email ID if available
            })
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"LLM analysis failed: {str(e)}")
            raise LLMProcessingError(f"LLM analysis failed: {str(e)}")
    
    def _create_prompt(self, email_data: EmailMetadata, nlp_results: Dict) -> str:
        """Create a prompt for the LLM analysis."""
        try:
            # Get user settings from current app context
            user_settings = {}
            if hasattr(g, 'user') and hasattr(g.user, 'settings'):
                user_settings = g.user.settings

            # Get summary length preference and set constraints
            summary_length = user_settings.get('ai_features.summary_length', 'medium')
            summary_guidance = {
                'short': """Generate a 1-2 sentence summary (max 25 words) that captures:
- The core message or main request
- The most critical action item (if any)
Example format: "Request for project timeline update. Needs response with Q3 milestones by Friday."
""",
                'medium': """Generate a 3-4 sentence summary (40-60 words) that includes:
- The core message or request
- Key context or background
- Important deadlines or next steps
- Any critical implications
Example format: "Budget approval request for Q3 marketing campaign. Previous quarter showed 20% ROI. Requesting $50K for digital ads and events. Approval needed by July 1st to meet campaign timeline."
""",
                'long': """Generate a comprehensive 5-7 sentence summary (80-120 words) covering:
- Complete context and background
- All key points and requests
- Detailed action items and deadlines
- Stakeholders involved and their roles
- Implications and potential impact
- Related projects or dependencies
Example format: "Quarterly strategy review for APAC expansion. Team reports 30% growth in existing markets, with China and Japan exceeding targets. Three new market opportunities identified: Vietnam, Thailand, and Indonesia. Local partnerships needed for regulatory compliance, estimated setup time 6-8 months. Budget impact of $2M over 18 months. Legal team review required for partnership agreements. VP approval needed by August for 2024 planning."
"""
            }.get(summary_length, '2-3 sentences, covering key points and decisions needed')

            # Validate and convert nlp_results if needed
            if nlp_results is None:
                nlp_results = {}
            elif isinstance(nlp_results, str):
                try:
                    nlp_results = json.loads(nlp_results)
                except json.JSONDecodeError:
                    self.logger.warning("Could not parse nlp_results string as JSON, using empty dict")
                    nlp_results = {}
            elif not isinstance(nlp_results, dict):
                self.logger.warning(f"nlp_results is not a dict or string (got {type(nlp_results)}), using empty dict")
                nlp_results = {}

            # Get email content
            subject = getattr(email_data, 'subject', 'No subject')
            sender = getattr(email_data, 'sender', 'Unknown sender')
            body = getattr(email_data, 'body', '')

            # Ensure body is a string
            if not isinstance(body, str):
                body = str(body)
            
            # Process NLP results
            entities = nlp_results.get('entities', [])
            keywords = nlp_results.get('keywords', [])
            sentiment = nlp_results.get('sentiment', 'neutral')
            
            # Ensure entities and keywords are lists
            if not isinstance(entities, list):
                entities = []
            if not isinstance(keywords, list):
                keywords = []
            
            # Select important entities and keywords
            important_entities = self._select_important_entities(entities)
            important_keywords = self._select_important_keywords(keywords)
            
            return f"""You are an email analysis assistant. Analyze the following email and provide a structured assessment to help prioritize inbox management.
EMAIL CONTENT
-------------
Subject: {subject}
From: {sender}
Content: {body}

CONTEXT
-------
NLP Context:
- Entities: {important_entities}
- Keywords: {important_keywords}
- Sentiment: {sentiment}

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
    - {summary_guidance}
    - Focus on key decisions and actions needed
    - Be concise but informative

5. priority (integer 0-100):
    - 0-20: Can be ignored/archived
    - 21-40: Low priority
    - 41-60: Medium priority
    - 61-80: High priority
    - 81-100: Urgent/immediate attention

OUTPUT FORMAT
------------
Return only valid JSON matching this schema:
{{
    "needs_action": boolean,
    "category": string,
    "action_items": array,
    "summary": string,
    "priority": integer
}}"""
        except Exception as e:
            self.logger.error(f"Error creating prompt: {str(e)}")
            raise LLMProcessingError(f"Failed to create prompt: {str(e)}")
    
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