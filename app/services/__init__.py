"""Services package for the application.

This package contains service modules that handle initialization and management
of various application components like database, OpenAI client, Redis, etc.

Each service is responsible for initializing a specific component, managing its
lifecycle, and providing access methods to the rest of the application.
"""

# Import all service initialization functions for convenience
from .openai_service import init_openai_client
from .redis_service import init_redis_client
from .db_service import init_db

__all__ = ['init_openai_client', 'init_redis_client', 'init_db'] 