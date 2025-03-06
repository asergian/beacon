"""Utilities for handling async operations in Flask context.

This module provides tools to simplify working with asynchronous code in a 
Flask application, which primarily operates in a synchronous context. It 
includes utilities for managing event loops, preserving context between 
synchronous and asynchronous code, and handling common async operation scenarios.
"""

import asyncio
import contextvars
import functools
from typing import Any, Callable, TypeVar, Optional
from flask import current_app

T = TypeVar('T')

class AsyncContextManager:
    """Manages async context and event loops for Flask applications.
    
    This class provides a set of utilities to manage asynchronous operations
    within Flask's synchronous environment. It handles event loop lifecycle
    management, context preservation, and graceful error handling for common
    async operation scenarios.
    
    Attributes:
        _loop: The asyncio event loop instance being managed by this class
    """
    
    def __init__(self):
        """Initialize the AsyncContextManager with no active event loop."""
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        
    def get_loop(self) -> asyncio.AbstractEventLoop:
        """Get or create an event loop for the current context.
        
        This method ensures that a valid event loop is available. If the current
        loop is closed or not set, it will create a new one.
        
        Returns:
            An active asyncio event loop that can be used for async operations
        
        Raises:
            RuntimeError: If an event loop cannot be created
        """
        if self._loop is None or self._loop.is_closed():
            try:
                self._loop = asyncio.get_event_loop()
            except RuntimeError:
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
        return self._loop
        
    def run_async(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """Decorator to run async functions in Flask routes.
        
        This decorator allows using async functions as Flask route handlers by
        automatically running them in an event loop and handling context
        preservation between sync and async code.
        
        Args:
            func: The async function to be wrapped for use in Flask
            
        Returns:
            A synchronous wrapper function that can be used in Flask routes
            
        Example:
            @app.route('/data')
            @async_manager.run_async
            async def get_data():
                data = await fetch_data_async()
                return jsonify(data)
        """
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            loop = self.get_loop()
            
            # Copy context vars from parent to child
            ctx = contextvars.copy_context()
            
            async def _wrapped():
                # Restore context
                for var in ctx:
                    var.set(ctx[var])
                return await func(*args, **kwargs)
            
            try:
                return loop.run_until_complete(_wrapped())
            except RuntimeError as e:
                if "Event loop is closed" in str(e):
                    # Create new loop if current one is closed
                    self._loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(self._loop)
                    return self._loop.run_until_complete(_wrapped())
                raise
                
    def ensure_loop(self) -> asyncio.AbstractEventLoop:
        """Ensure we have a valid event loop, creating one if necessary.
        
        This method is similar to get_loop() but has more robust error handling
        for situations where the event loop might be closed or unavailable.
        
        Returns:
            An active asyncio event loop that can be used for async operations
            
        Raises:
            RuntimeError: If an event loop cannot be created or is invalid
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                raise RuntimeError("Event loop is closed")
            return loop
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop
            
    async def run_in_loop(self, coro: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Run a coroutine in the current event loop, handling loop closure.
        
        This method safely executes a coroutine, automatically handling cases
        where the event loop might be closed or invalid.
        
        Args:
            coro: The coroutine function to execute
            *args: Positional arguments to pass to the coroutine
            **kwargs: Keyword arguments to pass to the coroutine
            
        Returns:
            The result returned by the coroutine
            
        Raises:
            RuntimeError: If the coroutine cannot be executed after handling
                         event loop issues
        """
        try:
            return await coro(*args, **kwargs)
        except RuntimeError as e:
            if "Event loop is closed" in str(e):
                loop = self.ensure_loop()
                return await coro(*args, **kwargs)
            raise

# Global instance
async_manager = AsyncContextManager() 