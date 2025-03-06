"""Redis client service.

This module provides initialization and management of Redis client instances,
ensuring proper connection pooling and resource cleanup.

Typical usage example:
    from app.services.redis_service import init_redis_client
    init_redis_client(app)
"""

import os
import logging
import asyncio
from flask import g

logger = logging.getLogger(__name__)

def init_redis_client(app):
    """Initialize Redis client with appropriate configuration.
    
    Args:
        app: Flask application instance
    
    Raises:
        ValueError: If Redis URL is missing in production
        Exception: For other initialization errors
    """
    redis_url = app.config.get('REDIS_URL')
    if not redis_url:
        if os.environ.get('RENDER'):
            raise ValueError("REDIS_URL environment variable is required in production")
        redis_url = 'redis://localhost:6379'
        logger.warning("No REDIS_URL configured, using default: %s", redis_url)

    try:
        if os.environ.get('RENDER'):
            # Upstash Redis in production
            from upstash_redis.asyncio import Redis as UpstashRedis
            # Extract token from URL if present, otherwise use separate env var
            upstash_token = app.config.get('REDIS_TOKEN')
            if not upstash_token:
                raise ValueError("REDIS_TOKEN environment variable is required for Upstash Redis")
            
            redis_client = UpstashRedis(url=redis_url, token=upstash_token)
            
            # Test the connection
            async def test_redis_connection():
                """Test Redis connection by setting and retrieving a test key.
                
                This function validates that the Redis connection is working properly
                by performing a simple set and get operation.
                
                Returns:
                    bool: True if the connection test passes
                    
                Raises:
                    ValueError: If the test fails or if the retrieved value is incorrect
                    Exception: For other connection errors
                """
                try:
                    await redis_client.set("_test_key", "test_value", ex=10)
                    test_result = await redis_client.get("_test_key")
                    if test_result != "test_value":
                        raise ValueError("Redis connection test failed")
                    return True
                except Exception as e:
                    logger.error(f"Redis test failed: {e}")
                    raise

            # Execute the test
            test_redis_connection()
            logger.info("Upstash Redis connection initialized successfully")
            app.config['REDIS_CLIENT'] = redis_client
        else:
            # Standard Redis for development
            from redis.asyncio import ConnectionPool, Redis
            pool = ConnectionPool.from_url(
                redis_url,
                max_connections=10,
                decode_responses=True
            )
            app.config['REDIS_POOL'] = pool
            logger.info("Local Redis connection pool initialized successfully")

        # Create Redis client getter
        def get_redis_client():
            """Get or create a Redis client for the current request context.
            
            This function returns a Redis client from the Flask application context
            or creates a new one if it doesn't exist. It handles different client 
            types based on the environment (Upstash Redis in production, standard 
            Redis in development).
            
            Returns:
                Redis: A configured Redis client instance
            """
            if 'redis_client' not in g:
                if os.environ.get('RENDER'):
                    # In production, use the Upstash client directly
                    g.redis_client = app.config['REDIS_CLIENT']
                else:
                    redis_url = app.config.get('REDIS_URL')
                    g.redis_client = Redis.from_url(
                        url=redis_url,
                        decode_responses=True,
                        socket_timeout=5.0,
                        socket_keepalive=True,
                        retry_on_timeout=True,
                    )
            return g.redis_client

        # Create Redis client cleanup
        async def close_redis_client(e=None):
            """Close the Redis client when the request ends.
            
            This function is registered as a teardown handler to ensure proper 
            cleanup of Redis resources when the application context ends.
            
            Args:
                e: Optional exception that caused the context to end
            """
            client = g.pop('redis_client', None)
            logger = logging.getLogger(__name__)
            
            if client is not None and not os.environ.get('RENDER'):
                try:
                    # Try directly closing the Redis client
                    await client.close()
                    logger.info("Closed Redis client directly.")
                except Exception as e:
                    logger.info(f"Error closing Redis client: {e}")
                finally:
                    client = None
        
        # Store the getter and closer functions in the app
        app.get_redis_client = get_redis_client
        app.close_redis_client = close_redis_client

    except Exception as e:
        logger.error("Failed to initialize Redis: %s", str(e))
        if os.environ.get('RENDER'):
            raise  # Re-raise in production
        # In development, we'll continue without Redis
        logger.warning("Continuing without Redis in development mode") 