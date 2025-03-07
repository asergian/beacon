"""
LLM client utilities for semantic analysis.

This module provides functions for interacting with the OpenAI client
for semantic analysis of emails.
"""
import logging
from typing import Dict, Any, List
from flask import current_app

from ....models.exceptions import LLMProcessingError


logger = logging.getLogger(__name__)


async def get_openai_client():
    """
    Get the OpenAI client from the current application.
    
    Returns:
        The OpenAI client instance
        
    Raises:
        LLMProcessingError: If client initialization fails
    """
    try:
        if not hasattr(current_app, 'get_openai_client'):
            raise ValueError("OpenAI client getter not initialized")
        
        client = current_app.get_openai_client()
        if client is None:
            raise ValueError("OpenAI client is None")
            
        return client
        
    except Exception as e:
        logger.error(f"Failed to get OpenAI client: {e}")
        raise LLMProcessingError(f"OpenAI client initialization failed: {e}")


async def send_completion_request(
    client, 
    model: str, 
    prompt: str, 
    max_tokens: int, 
    temperature: float = 0.1
):
    """
    Send a completion request to the OpenAI API.
    
    Args:
        client: The OpenAI client instance
        model: The model to use for the completion
        prompt: The prompt text
        max_tokens: Maximum number of tokens to generate
        temperature: Temperature for the completion (randomness)
        
    Returns:
        The response from the OpenAI API
        
    Raises:
        LLMProcessingError: If the API call fails
    """
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are an AI assistant analyzing emails."},
                {"role": "user", "content": prompt}
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"}  # Force JSON response
        )
        return response
        
    except Exception as e:
        logger.error(f"OpenAI API call failed: {e}")
        raise LLMProcessingError(f"OpenAI API call failed: {e}")


def extract_response_content(response):
    """
    Extract the content from a completion response.
    
    Args:
        response: The response from the OpenAI API
        
    Returns:
        The content of the response
    """
    return response.choices[0].message.content 