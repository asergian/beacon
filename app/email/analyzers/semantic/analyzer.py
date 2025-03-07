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
from .utilities import (
    # Token and text handling
    TokenHandler,
    
    # LLM client operations
    get_openai_client,
    send_completion_request,
    extract_response_content,
    
    # Settings management
    get_model_type,
    get_context_length,
    get_response_tokens,
    is_ai_enabled,
    log_ai_config,
    
    # Cost calculation
    format_cost_stats,
    
    # Email validation and preprocessing
    validate_email_data,
    preprocess_email
)
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
            # Configure analysis settings from user preferences
            await self._configure_analysis_settings()
            
            # Check if AI features are enabled
            if not is_ai_enabled():
                self.logger.info("AI features disabled, returning basic metadata")
                return self.response_parser.create_disabled_response(getattr(email_data, 'id', None))

            # Validate and preprocess email data
            validated_email = validate_email_data(email_data)
            clean_email = preprocess_email(validated_email, self.token_handler, self.max_content_tokens)
            
            # Generate prompt and analyze
            return await self._analyze_with_llm(clean_email, nlp_results)
            
        except Exception as e:
            self.logger.error(f"LLM analysis failed: {str(e)}")
            raise LLMProcessingError(f"LLM analysis failed: {str(e)}")

    async def _configure_analysis_settings(self) -> None:
        """
        Configure analysis settings from user preferences.
        
        This method sets up model type, context length, and other settings
        from the user's configuration.
        """
        # Log AI configuration
        log_ai_config(self.logger)
        
        # Get model type from user settings
        self.model = get_model_type()
        
        # Get context length from user settings
        self.max_content_tokens = get_context_length()
        
        # Get response token limit based on summary length preference
        self.response_tokens = get_response_tokens()
        
        self.logger.debug(
            f"Analysis config - Model: {self.model}, Context: {self.max_content_tokens}, "
            f"Max Response: {self.response_tokens}"
        )

    async def _analyze_with_llm(
        self, 
        email_data: EmailMetadata, 
        nlp_results: Dict
    ) -> Dict[str, Any]:
        """
        Perform LLM analysis on a preprocessed email.
        
        Args:
            email_data: Preprocessed email data
            nlp_results: NLP analysis results
            
        Returns:
            Analysis results dictionary
            
        Raises:
            LLMProcessingError: If LLM processing fails
        """
        # Create prompt for LLM
        prompt = self.prompt_creator.create_prompt(email_data, nlp_results)
        prompt_tokens = self.token_handler.count_tokens(prompt)
        
        # Log the analysis request
        self.logger.info(
            f"Processing email {email_data.id} - Model: {self.model}, " 
            f"Prompt Tokens: {prompt_tokens}, Max Response: {self.response_tokens}"
        )
        
        # Get OpenAI client and send request
        client = await get_openai_client()
        response = await send_completion_request(
            client, 
            self.model, 
            prompt, 
            self.response_tokens
        )
        
        # Extract and process response
        return await self._process_llm_response(response, email_data, prompt_tokens)
    
    async def _process_llm_response(
        self, 
        response, 
        email_data: EmailMetadata, 
        prompt_tokens: int
    ) -> Dict[str, Any]:
        """
        Process the LLM response and format results.
        
        Args:
            response: The LLM response object
            email_data: Original email data
            prompt_tokens: Number of tokens in the prompt
            
        Returns:
            Processed analysis results
        """
        # Calculate token usage
        prompt_tokens = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens
        total_tokens = response.usage.total_tokens
        
        # Log completion details
        self.logger.info(
            f"Completed email {email_data.id} - "
            f"Tokens: {prompt_tokens}/{completion_tokens}/{total_tokens} (in/out/total)"
        )
        
        # Parse the response content
        response_content = extract_response_content(response)
        analysis = self.response_parser.parse_response(response_content)
        
        # Add usage statistics
        stats = format_cost_stats(self.model, prompt_tokens, completion_tokens, total_tokens)
        analysis.update(stats)
        
        # Add email identifier and enabled flag
        analysis.update({
            'email_id': getattr(email_data, 'id', None),
            'ai_enabled': True
        })
        
        return analysis
    
    async def analyze_batch(self, emails: List[Tuple[EmailMetadata, Dict]], max_batch_size: int = 20) -> List[Dict[str, Any]]:
        """Analyze a batch of emails using a single LLM request.
        
        Args:
            emails: List of tuples containing (EmailMetadata, nlp_results)
            max_batch_size: Maximum number of emails to process in a single batch
            
        Returns:
            List of analysis results corresponding to input emails
        """
        # Configure analysis settings (will be used by the batch processor)
        await self._configure_analysis_settings()
        
        # Pass configured values to batch processor
        self.batch_processor.model = self.model
        self.batch_processor.max_content_tokens = self.max_content_tokens
        
        return await self.batch_processor.analyze_batch(emails, max_batch_size) 