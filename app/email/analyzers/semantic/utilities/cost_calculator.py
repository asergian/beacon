"""
Cost calculation utilities for LLM processing.

This module provides utilities for calculating costs associated with LLM API calls.
"""
from typing import Dict, Tuple, Union


def get_cost_per_1k(model: str) -> Dict[str, float]:
    """
    Get the cost per 1000 tokens for a given model.
    
    Args:
        model: The model identifier (e.g., 'gpt-4o-mini')
        
    Returns:
        Dictionary with 'input' and 'output' costs per 1000 tokens
    """
    # Model pricing table ($/1000 tokens)
    pricing = {
        "gpt-4o-mini": {
            "input": 0.00015,
            "output": 0.0006
        },
        "gpt-4o": {
            "input": 0.005,
            "output": 0.015
        }
        # Add more models as needed
    }
    
    # Default to gpt-4o-mini rates if model not found
    return pricing.get(model, {
        "input": 0.00015,
        "output": 0.0006
    })


def calculate_cost(
    model: str, 
    prompt_tokens: int, 
    completion_tokens: int
) -> Tuple[float, float, float]:
    """
    Calculate the cost of an LLM API call.
    
    Args:
        model: The model identifier
        prompt_tokens: Number of tokens in the prompt (input)
        completion_tokens: Number of tokens in the completion (output)
        
    Returns:
        Tuple of (input_cost, output_cost, total_cost)
    """
    cost_per_1k = get_cost_per_1k(model)
    
    input_cost = (prompt_tokens / 1000) * cost_per_1k["input"]
    output_cost = (completion_tokens / 1000) * cost_per_1k["output"]
    total_cost = input_cost + output_cost
    
    return input_cost, output_cost, total_cost


def calculate_total_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """
    Calculate the total cost of an LLM API call.
    
    Args:
        model: The model identifier
        prompt_tokens: Number of tokens in the prompt (input)
        completion_tokens: Number of tokens in the completion (output)
        
    Returns:
        Total cost in dollars
    """
    _, _, total_cost = calculate_cost(model, prompt_tokens, completion_tokens)
    return total_cost


def format_cost_stats(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int = None
) -> Dict[str, Union[str, int, float]]:
    """
    Format cost statistics into a dictionary for response.
    
    Args:
        model: The model identifier
        prompt_tokens: Number of tokens in the prompt
        completion_tokens: Number of tokens in the completion
        total_tokens: Total token count (if None, calculated from prompt + completion)
        
    Returns:
        Dictionary with model, token counts, and cost information
    """
    if total_tokens is None:
        total_tokens = prompt_tokens + completion_tokens
        
    _, _, total_cost = calculate_cost(model, prompt_tokens, completion_tokens)
    
    return {
        'model': model,
        'total_tokens': total_tokens,
        'prompt_tokens': prompt_tokens,
        'completion_tokens': completion_tokens,
        'cost': total_cost
    } 