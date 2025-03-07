"""
Batch processing functionality for the semantic analyzer.

This module handles batch processing of emails for analysis.
"""
import asyncio
import logging
import time
from typing import Dict, Any, List, Tuple
from flask import g, current_app

from ....core.email_parsing import EmailMetadata
from ....models.exceptions import LLMProcessingError
from ..processors.prompt_creator import PromptCreator
from ..processors.response_parser import ResponseParser
from ..utilities.text_processor import strip_html


class BatchProcessor:
    """Processes batches of emails for semantic analysis."""
    
    def __init__(self, token_handler):
        """Initialize the batch processor.
        
        Args:
            token_handler: The token handler for text truncation
        """
        self.logger = logging.getLogger(__name__)
        self.token_handler = token_handler
        self.model = "gpt-4o-mini"  # Default model - will be overridden by user settings
        self.max_content_tokens = 1000  # Default - will be overridden by user settings
        self.prompt_creator = PromptCreator()
        self.response_parser = ResponseParser()
        
    async def process_batch(self, batch: List[Tuple[EmailMetadata, Dict]]) -> List[Dict[str, Any]]:
        """Process a single batch of emails.
        
        Args:
            batch: List of tuples containing (EmailMetadata, nlp_results)
            
        Returns:
            List of analysis results
            
        Raises:
            LLMProcessingError: If batch processing fails
        """
        try:
            # Create prompts for all emails in batch
            prompts = []
            for email_data, nlp_results in batch:
                # Clean HTML and truncate content
                clean_body = strip_html(email_data.body)
                truncated_body = self.token_handler.truncate_to_tokens(clean_body, self.max_content_tokens)
                
                # Create clean version of email metadata
                clean_email = EmailMetadata(
                    id=email_data.id,
                    subject=email_data.subject,
                    sender=email_data.sender,
                    body=truncated_body,
                    date=email_data.date
                )
                
                prompt = self.prompt_creator.create_prompt(clean_email, nlp_results)
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
                analysis = self.response_parser.parse_response(response.choices[0].message.content)
                
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
                return [self.response_parser.create_disabled_response(email.id) for email, _ in emails]

            # Get model and context settings
            self.model = g.user.get_setting('ai_features.model_type', 'gpt-4o-mini')
            raw_context_length = g.user.get_setting('ai_features.context_length')
            self.max_content_tokens = int(raw_context_length) if raw_context_length else 1000

            # Process emails in batches of max_batch_size
            results = []
            for i in range(0, len(emails), max_batch_size):
                batch = emails[i:i + max_batch_size]
                batch_results = await self.process_batch(batch)
                results.extend(batch_results)

            return results

        except Exception as e:
            self.logger.error(f"Batch analysis failed: {str(e)}")
            raise LLMProcessingError(f"Batch analysis failed: {str(e)}") 