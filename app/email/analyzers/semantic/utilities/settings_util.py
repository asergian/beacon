"""
User settings utilities for semantic analysis.

This module provides utility functions for retrieving and managing user settings
related to semantic analysis.
"""
import logging
from typing import Dict, Any, Optional, Union, TypeVar
from flask import g

# Type variable for generic return types
T = TypeVar('T')

logger = logging.getLogger(__name__)

def get_user_setting(setting_path: str, default: T = None) -> T:
    """
    Get a user setting by path with a default fallback.
    
    Args:
        setting_path: Dot-separated path to the setting (e.g., 'ai_features.enabled')
        default: Default value to return if setting is not found
        
    Returns:
        The setting value or the default
    """
    try:
        if not hasattr(g, 'user'):
            return default
            
        return g.user.get_setting(setting_path, default)
    except Exception as e:
        logger.warning(f"Error getting user setting {setting_path}: {e}")
        return default

def get_ai_settings() -> Dict[str, Any]:
    """
    Get all AI-related settings as a dictionary.
    
    Returns:
        Dictionary containing all AI settings with defaults
    """
    # Default settings
    default_settings = {
        'enabled': True,
        'model_type': 'gpt-4o-mini',
        'context_length': 1000,
        'summary_length': 'medium',
        'custom_categories': []
    }
    
    # Get user settings if available
    if hasattr(g, 'user') and hasattr(g.user, 'settings'):
        try:
            ai_settings = g.user.get_settings_group('ai_features')
            # Merge with defaults for any missing settings
            for key, value in default_settings.items():
                if key not in ai_settings:
                    ai_settings[key] = value
            return ai_settings
        except Exception as e:
            logger.warning(f"Error getting AI settings: {e}")
    
    return default_settings

def is_ai_enabled() -> bool:
    """
    Check if AI features are enabled for the current user.
    
    Returns:
        True if AI features are enabled, False otherwise
    """
    return get_user_setting('ai_features.enabled', True)

def get_model_type() -> str:
    """
    Get the model type from user settings.
    
    Returns:
        Model type string
    """
    return get_user_setting('ai_features.model_type', 'gpt-4o-mini')

def get_context_length() -> int:
    """
    Get the context length from user settings.
    
    Returns:
        Context length as an integer
    """
    raw_length = get_user_setting('ai_features.context_length')
    return int(raw_length) if raw_length else 1000

def get_summary_length() -> str:
    """
    Get the summary length preference from user settings.
    
    Returns:
        Summary length string ('short', 'medium', or 'long')
    """
    return get_user_setting('ai_features.summary_length', 'medium')

def get_response_tokens() -> int:
    """
    Get the maximum response tokens based on summary length.
    
    Returns:
        Maximum response tokens
    """
    summary_length = get_summary_length()
    return {
        'short': 150,   # Brief summary and key points
        'medium': 300,  # Detailed summary and analysis
        'long': 500     # Comprehensive analysis
    }.get(summary_length, 300)  # Default to medium if unknown value

def get_custom_categories() -> list:
    """
    Get custom categories from user settings.
    
    Returns:
        List of custom category dictionaries
    """
    return get_user_setting('ai_features.custom_categories', [])

def log_ai_config(logger: logging.Logger) -> None:
    """
    Log AI configuration details.
    
    Args:
        logger: Logger instance to use for logging
    """
    ai_settings = get_ai_settings()
    logger.debug(
        "AI Configuration:\n"
        f"    Enabled: {ai_settings.get('enabled', True)}\n"
        f"    Model: {ai_settings.get('model_type', 'gpt-4o-mini')}\n"
        f"    Context Length: {ai_settings.get('context_length', 1000)}\n"
        f"    Summary Length: {ai_settings.get('summary_length', 'medium')}"
    ) 