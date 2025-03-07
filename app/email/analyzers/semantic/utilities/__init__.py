"""
Utility functions and classes for semantic analysis.

This package provides various utility functions and classes for text processing,
token handling, settings management, LLM client operations, and cost calculation.
"""

from .text_processor import (
    strip_html,
    sanitize_text,
    format_list,
    format_dict,
    select_important_entities,
    select_important_keywords,
    select_important_patterns
)

from .token_handler import TokenHandler

from .settings_util import (
    get_user_setting,
    get_ai_settings,
    is_ai_enabled,
    get_model_type,
    get_context_length,
    get_summary_length,
    get_response_tokens,
    get_custom_categories,
    log_ai_config
)

from .cost_calculator import (
    get_cost_per_1k,
    calculate_cost,
    calculate_total_cost,
    format_cost_stats
)

from .llm_client import (
    get_openai_client,
    send_completion_request,
    extract_response_content
)

from .email_validator import (
    validate_email_data,
    preprocess_email
)

__all__ = [
    # Text processor
    'strip_html',
    'sanitize_text', 
    'format_list',
    'format_dict',
    'select_important_entities',
    'select_important_keywords',
    'select_important_patterns',
    
    # Token handler
    'TokenHandler',
    
    # Settings utilities
    'get_user_setting',
    'get_ai_settings',
    'is_ai_enabled',
    'get_model_type',
    'get_context_length',
    'get_summary_length',
    'get_response_tokens',
    'get_custom_categories',
    'log_ai_config',
    
    # Cost calculator
    'get_cost_per_1k',
    'calculate_cost',
    'calculate_total_cost',
    'format_cost_stats',
    
    # LLM client
    'get_openai_client',
    'send_completion_request',
    'extract_response_content',
    
    # Email validator
    'validate_email_data',
    'preprocess_email'
] 