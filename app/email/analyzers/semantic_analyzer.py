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
        self.model = "gpt-4o-mini"  # Default model - cost-effective option
        self.max_tokens = 1000  # Maximum tokens per request
        self.max_content_tokens = 500  # Maximum tokens for email content
        try:
            self.encoding = tiktoken.encoding_for_model(self.model)
        except Exception as e:
            self.logger.warning(f"Failed to get encoding for {self.model}, using cl100k_base: {e}")
            self.encoding = tiktoken.get_encoding("cl100k_base")
    
    def count_tokens(self, text: str) -> int:
        """Count the number of tokens in a text string."""
        return len(self.encoding.encode(text))
    
    def _truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """Truncate text to a maximum number of tokens while preserving sentence boundaries."""
        tokens = self.encoding.encode(text)
        if len(tokens) <= max_tokens:
            return text
            
        # Decode only the tokens we want to keep
        truncated = self.encoding.decode(tokens[:max_tokens])
        
        # Try to find the last sentence boundary
        last_period = truncated.rfind('.')
        if last_period > 0:
            truncated = truncated[:last_period + 1]
        
        return truncated + " [truncated]"
    
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
            # Ensure email_data is properly structured
            if not isinstance(email_data, EmailMetadata):
                self.logger.error(f"email_data is not an EmailMetadata object (got {type(email_data)})")
                # Convert to EmailMetadata if it's a dict
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
            
            # Prepare the prompt
            prompt = self._create_prompt(email_data, nlp_results)
            prompt_tokens = self.count_tokens(prompt)
            
            self.logger.info(f"Using model {self.model} with max {self.max_tokens} tokens per request")
            self.logger.info(f"Prompt length: {prompt_tokens} tokens")
            
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
            
            # Make the API call
            try:
                response = await client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are an AI assistant analyzing emails."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=self.max_tokens
                )
            except Exception as e:
                self.logger.error(f"OpenAI API call failed: {e}")
                raise LLMProcessingError(f"OpenAI API call failed: {e}")
            
            # Log token usage
            prompt_tokens = response.usage.prompt_tokens
            completion_tokens = response.usage.completion_tokens
            total_tokens = response.usage.total_tokens
            self.logger.info(f"Token usage - Prompt: {prompt_tokens}, Completion: {completion_tokens}, Total: {total_tokens}")
            
            # Parse the response
            analysis = self._parse_response(response.choices[0].message.content)
            
            # Calculate costs (approximate, update rates as needed)
            cost_per_1k = {
                "gpt-4o-mini": {
                    "input": 0.00015,  # Updated for gpt-4o-mini
                    "output": 0.0006
                }
            }[self.model]
            
            input_cost = (prompt_tokens / 1000) * cost_per_1k["input"]
            output_cost = (completion_tokens / 1000) * cost_per_1k["output"]
            total_cost = input_cost + output_cost
            
            self.logger.info(f"Cost - Input: ${input_cost:.4f}, Output: ${output_cost:.4f}, Total: ${total_cost:.4f}")
            
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

            # Get email metadata safely
            subject = getattr(email_data, 'subject', 'No subject')
            sender = getattr(email_data, 'sender', 'Unknown sender')
            body = getattr(email_data, 'body', '')

            # Ensure body is a string
            if not isinstance(body, str):
                body = str(body)

            # Truncate email body to max tokens while preserving meaning
            truncated_body = self._truncate_to_tokens(body, self.max_content_tokens)
            
            # Safely get NLP results with empty defaults
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
Body: {truncated_body}

CONTEXT
-------
NLP Analysis Results:
- Key Entities: {important_entities}
- Important Keywords: {important_keywords}
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
    - 2-3 sentences maximum
    - Focus on key points and decisions needed

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