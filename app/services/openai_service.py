"""OpenAI client service.

This module provides initialization and management of OpenAI client instances,
ensuring proper resource cleanup and connection handling.

Typical usage example:
    from app.services.openai_service import init_openai_client
    init_openai_client(app)
"""

import os
import logging
import asyncio
import multiprocessing
from flask import g, current_app
from openai import AsyncOpenAI

def init_openai_client(app):
    """Initialize OpenAI client with API key configuration.
    
    Args:
        app: Flask application instance
    
    Raises:
        ValueError: If OpenAI API key is missing or invalid
        Exception: For other initialization errors
    """

    # Initialize logger at module level
    logger = logging.getLogger(__name__)

    try:
        # Check for API key
        openai_api_key = app.config.get('OPENAI_API_KEY')
        if not openai_api_key:
            raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY in the configuration.")
            
        logger.info("Initializing OpenAI client")
        
        # Create a function to get or create the OpenAI client
        def get_openai_client():
            """Get or create an OpenAI client for the current request context.
            
            This function returns an AsyncOpenAI client from the Flask application
            context or creates a new one if it doesn't exist. The client is configured
            with the application's API key and a reasonable timeout setting.
            
            Returns:
                AsyncOpenAI: A configured OpenAI client instance
            """
            if 'async_openai_client' not in g:
                g.async_openai_client = AsyncOpenAI(
                    api_key=app.config['OPENAI_API_KEY'],
                    timeout=60.0  # Set a reasonable timeout
                )
            return g.async_openai_client
        
        # Modified teardown function to run the async cleanup
        def teardown_openai_client(e=None):
            """
            Flask teardown function that handles the async cleanup of OpenAI client.
            
            This function is registered with Flask's teardown_appcontext to ensure
            proper cleanup of OpenAI client resources when the application context ends.
            
            Args:
                e: Optional exception that caused the context to end
            """
            try:
                # In a Flask context, we need to perform a non-async cleanup
                # since we can't rely on the event loop being available or active
                client = g.pop('async_openai_client', None)
                if client is not None:
                    try:
                        # For HTTPX clients and other clients with async methods,
                        # we can access the underlying client but we can't await its methods
                        # So we manually close the synchronous resources and log the rest
                        if hasattr(client._client, '_pool'):
                            client._client._pool.close()
                        logger.debug("OpenAI client resources released")
                    except Exception as ex:
                        logger.warning(f"Error during OpenAI client cleanup: {ex}")
                    finally:
                        try:
                            asyncio.create_task(client.aclose())
                        except Exception as e:
                            logger.debug(f"Error closing OpenAI client: {e}")
                        client = None
            except Exception as ex:
                logger.warning(f"Error during OpenAI client cleanup: {ex}")
        
        # Store the getter and closer functions in the app
        app.get_openai_client = get_openai_client
        app.close_openai_client = teardown_openai_client

        # Log initialization status based on process type
        if multiprocessing.parent_process():
            logger.debug(f"OpenAI client initialized successfully for worker process (PID: {os.getpid()})")
        
    except ValueError as e:
        logger = getattr(current_app, 'logger', logging.getLogger(__name__))
        logger.error(f"Failed to initialize OpenAI client: {str(e)}")
        raise
    except Exception as e:
        logger = getattr(current_app, 'logger', logging.getLogger(__name__))
        logger.error(f"Unexpected error initializing OpenAI client: {str(e)}")
        raise 