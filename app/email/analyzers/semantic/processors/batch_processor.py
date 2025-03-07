"""
Batch processing functionality for the semantic analyzer.

This module handles batch processing of emails for analysis.
"""
import asyncio
import logging
import time
from typing import Dict, Any, List, Tuple
from flask import g

from ....core.email_parsing import EmailMetadata
from ....models.exceptions import LLMProcessingError
from ..utilities import (
    # LLM client operations
    get_openai_client,
    send_completion_request,
    
    # Email validation
    preprocess_email,
    
    # Settings management
    is_ai_enabled,
    get_model_type,
    get_context_length,
    
    # Cost calculation
    format_cost_stats
)
from ..processors.prompt_creator import PromptCreator
from ..processors.response_parser import ResponseParser


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
            prompts, clean_emails = await self._prepare_batch_prompts(batch)
            
            # Create messages for the batch
            messages = self._create_batch_messages(prompts)
            
            # Process batch with LLM
            responses = await self._process_batch_with_llm(messages)
            
            # Process responses
            return self._process_batch_responses(responses, batch, clean_emails)

        except Exception as e:
            self.logger.error(f"Batch processing failed: {str(e)}")
            raise LLMProcessingError(f"Batch processing failed: {str(e)}")
    
    async def _prepare_batch_prompts(
        self, 
        batch: List[Tuple[EmailMetadata, Dict]]
    ) -> Tuple[List[str], List[EmailMetadata]]:
        """
        Prepare prompts for a batch of emails.
        
        Args:
            batch: List of tuples containing (EmailMetadata, nlp_results)
            
        Returns:
            Tuple of (list of prompts, list of preprocessed emails)
        """
        prompts = []
        clean_emails = []
        
        for email_data, nlp_results in batch:
            # Preprocess the email
            clean_email = preprocess_email(email_data, self.token_handler, self.max_content_tokens)
            clean_emails.append(clean_email)
            
            # Create prompt
            prompt = self.prompt_creator.create_prompt(clean_email, nlp_results)
            prompts.append(prompt)
            
        return prompts, clean_emails
    
    def _create_batch_messages(self, prompts: List[str]) -> List[List[Dict[str, str]]]:
        """
        Create message structures for batch processing.
        
        Args:
            prompts: List of prompts to convert to messages
            
        Returns:
            List of messages for the OpenAI API
        """
        messages = []
        for prompt in prompts:
            messages.append([
                {"role": "system", "content": "You are an AI assistant analyzing emails."},
                {"role": "user", "content": prompt}
            ])
        return messages
    
    async def _process_batch_with_llm(
        self, 
        messages: List[List[Dict[str, str]]]
    ) -> List[Any]:
        """
        Process a batch of messages with the LLM.
        
        Args:
            messages: List of message structures for the OpenAI API
            
        Returns:
            List of LLM responses
            
        Raises:
            LLMProcessingError: If the API call fails
        """
        # Get OpenAI client
        client = await get_openai_client()
        
        start_time = time.time()
        self.logger.info(f"Processing batch of {len(messages)} emails with model {self.model}")
        
        # Process messages in parallel with asyncio.gather
        async def process_message(msg):
            return await send_completion_request(
                client, 
                self.model, 
                msg[1]["content"],  # Extract prompt from message structure
                300  # Use fixed 300 tokens for batch processing
            )
        
        try:
            responses = await asyncio.gather(*[process_message(msg) for msg in messages])
            processing_time = time.time() - start_time
            self.logger.debug(f"Batch processing completed in {processing_time:.2f} seconds")
            return responses
            
        except Exception as e:
            self.logger.error(f"OpenAI batch API call failed: {e}")
            raise LLMProcessingError(f"OpenAI batch API call failed: {e}")
    
    def _process_batch_responses(
        self, 
        responses: List[Any], 
        batch: List[Tuple[EmailMetadata, Dict]],
        clean_emails: List[EmailMetadata]
    ) -> List[Dict[str, Any]]:
        """
        Process batch responses and format results.
        
        Args:
            responses: List of LLM responses
            batch: Original batch of email data
            clean_emails: List of preprocessed emails
            
        Returns:
            List of analysis results
        """
        results = []
        total_tokens = 0
        total_cost = 0

        for i, response in enumerate(responses):
            email_data = clean_emails[i]
            
            # Parse the response
            analysis = self.response_parser.parse_response(response.choices[0].message.content)
            
            # Calculate and add usage statistics
            prompt_tokens = response.usage.prompt_tokens
            completion_tokens = response.usage.completion_tokens
            
            # Track total usage
            email_tokens = prompt_tokens + completion_tokens
            total_tokens += email_tokens
            
            # Add usage stats to the results
            stats = format_cost_stats(self.model, prompt_tokens, completion_tokens)
            analysis.update(stats)
            
            # Track cost
            total_cost += analysis['cost']
            
            # Add email ID and enabled flag
            analysis.update({
                'email_id': email_data.id,
                'ai_enabled': True
            })
            
            results.append(analysis)

        # Log batch processing statistics
        self._log_batch_stats(len(batch), total_tokens, total_cost)
        
        return results
    
    def _log_batch_stats(self, batch_size: int, total_tokens: int, total_cost: float) -> None:
        """
        Log batch processing statistics.
        
        Args:
            batch_size: Number of emails in the batch
            total_tokens: Total tokens used
            total_cost: Total cost incurred
        """
        self.logger.info(
            f"Batch processing stats: emails processed: {batch_size}, "
            f"total_tokens: {total_tokens}, "
            f"avg_tokens: {total_tokens/batch_size:.1f}, "
            f"total_cost: ${total_cost:.4f}"
        )
        
        self.logger.debug(
            f"Batch processing stats:\n"
            f"    Emails processed: {batch_size}\n"
            f"    Total tokens: {total_tokens}\n"
            f"    Total cost: ${total_cost:.4f}\n"
            f"    Average tokens per email: {total_tokens/batch_size:.1f}"
        )
            
    async def analyze_batch(
        self, 
        emails: List[Tuple[EmailMetadata, Dict]], 
        max_batch_size: int = 20
    ) -> List[Dict[str, Any]]:
        """Analyze a batch of emails using a single LLM request.
        
        Args:
            emails: List of tuples containing (EmailMetadata, nlp_results)
            max_batch_size: Maximum number of emails to process in a single batch
            
        Returns:
            List of analysis results corresponding to input emails
        """
        try:
            # Check if AI features are enabled
            if not is_ai_enabled():
                return [self.response_parser.create_disabled_response(email.id) for email, _ in emails]

            # Configure from user settings if not already set by the parent analyzer
            if self.model == "gpt-4o-mini":  # Check if still using default value
                self.model = get_model_type()
                
            if self.max_content_tokens == 1000:  # Check if still using default value
                self.max_content_tokens = get_context_length()

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