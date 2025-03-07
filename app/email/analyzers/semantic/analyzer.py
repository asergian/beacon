"""
Semantic Analyzer for email content.

This module provides semantic analysis of emails using LLM, providing insights
about content, priority, action items, and more.
"""
import logging
from typing import Dict, Any, List, Tuple

from flask import g, current_app

from ...core.email_parsing import EmailMetadata
from ...models.exceptions import LLMProcessingError
from ..base import BaseAnalyzer
from .utilities.token_handler import TokenHandler
from .utilities.text_processor import strip_html
from .processors.prompt_creator import PromptCreator
from .processors.response_parser import ResponseParser
from .processors.batch_processor import BatchProcessor


class SemanticAnalyzer(BaseAnalyzer):
    """Analyzes emails using LLM for semantic understanding."""
    
    def __init__(self):
        """Initialize the semantic analyzer."""
        self.logger = logging.getLogger(__name__)
        self.model = "gpt-4o-mini"  # Default model - will be overridden by user settings
        self.max_content_tokens = 1000  # Default to medium length - will be overridden by user settings
        self.token_handler = TokenHandler()
        self.prompt_creator = PromptCreator()
        self.response_parser = ResponseParser()
        self.batch_processor = BatchProcessor(self.token_handler)
        
    async def analyze(self, email_data: EmailMetadata, nlp_results: Dict) -> Dict[str, Any]:
        """
        Analyze email content using LLM.
        
        Args:
            email_data: Parsed email data as EmailMetadata object
            nlp_results: Results from NLP analysis
            
        Returns:
            Dictionary containing LLM analysis results and usage statistics
            
        Raises:
            LLMProcessingError: If the analysis fails
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
                return self.response_parser.create_disabled_response(getattr(email_data, 'id', None))

            # Get model type from user settings
            raw_model_type = g.user.get_setting('ai_features.model_type')
            self.model = raw_model_type or 'gpt-4o-mini'
            
            # Get context length from user settings and convert to int
            raw_context_length = g.user.get_setting('ai_features.context_length')
            context_length = int(raw_context_length) if raw_context_length else 1000
            self.max_content_tokens = context_length

            # Get summary length preference
            summary_length = g.user.get_setting('ai_features.summary_length', 'medium')
            
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
            clean_body = strip_html(email_data.body)
            truncated_body = self.token_handler.truncate_to_tokens(clean_body, self.max_content_tokens)
            
            # Create prompt using the cleaned and truncated body
            clean_email = EmailMetadata(
                id=email_data.id,
                subject=email_data.subject,
                sender=email_data.sender,
                body=truncated_body,
                date=email_data.date
            )
            
            prompt = self.prompt_creator.create_prompt(clean_email, nlp_results)
            prompt_tokens = self.token_handler.count_tokens(prompt)
            
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
            analysis = self.response_parser.parse_response(response.choices[0].message.content)
            
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

    async def analyze_batch(self, emails: List[Tuple[EmailMetadata, Dict]], max_batch_size: int = 20) -> List[Dict[str, Any]]:
        """Analyze a batch of emails using a single LLM request.
        
        Args:
            emails: List of tuples containing (EmailMetadata, nlp_results)
            max_batch_size: Maximum number of emails to process in a single batch
            
        Returns:
            List of analysis results corresponding to input emails
        """
        return await self.batch_processor.analyze_batch(emails, max_batch_size) 