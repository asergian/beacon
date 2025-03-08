"""Memory profiling utilities for monitoring and logging application memory usage.

This module provides functionality for monitoring memory usage in Python applications,
including utilities for getting process memory stats, logging memory usage at specific
application stages, and middleware for profiling memory usage in web requests.
"""

import gc
import os
import logging
from datetime import datetime

import psutil


def get_process_memory():
    """Get detailed memory usage information for the current process.
    
    Returns:
        dict: A dictionary containing memory metrics in MB:
            - rss: Resident Set Size
            - vms: Virtual Memory Size
            - shared: Shared memory
            - data: Data memory
            - uss: Unique Set Size (memory unique to this process)
    """
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    return {
        'rss': memory_info.rss / 1024 / 1024,  # RSS in MB
        'vms': memory_info.vms / 1024 / 1024,  # VMS in MB
        'shared': getattr(memory_info, 'shared', 0) / 1024 / 1024,  # Shared memory in MB
        'data': getattr(memory_info, 'data', 0) / 1024 / 1024,  # Data memory in MB
        'uss': getattr(process.memory_full_info(), 'uss', 0) / 1024 / 1024  # Unique Set Size in MB
    }


def log_memory_usage(logger, stage: str):
    """Log current memory usage at a specific application stage.
    
    Args:
        logger: The logger instance to use for logging memory information
        stage: A string identifier indicating the application stage being measured
    """
    mem = get_process_memory()
    logger.debug(f"Memory Usage [{stage}]: RSS={mem['rss']:.1f}MB USS={mem['uss']:.1f}MB Data={mem['data']:.1f}MB Shared={mem['shared']:.1f}MB")


def log_memory_cleanup(logger, stage: str):
    """Run garbage collection and log memory cleanup results.
    
    Performs multiple garbage collection cycles and logs the difference in memory
    usage before and after cleanup.
    
    Args:
        logger: The logger instance to use for logging cleanup information
        stage: A string identifier indicating the application stage being measured
    """
    try:
        # Log memory before cleanup
        mem_before = get_process_memory()
        logger.debug(f"Memory Before Cleanup [{stage}]: RSS={mem_before['rss']:.1f}MB USS={mem_before['uss']:.1f}MB")
        
        # Run multiple collection cycles
        freed_objects = gc.collect()
        additional_freed = gc.collect()
        final_freed = gc.collect()
        
        # Log memory after cleanup
        mem_after = get_process_memory()
        diff = {k: mem_before[k] - mem_after[k] for k in mem_before}
        
        logger.debug(
            f"Memory Cleanup [{stage}]: "
            f"Freed {freed_objects+additional_freed+final_freed} objects, "
            f"RSS diff: {diff['rss']:.1f}MB, "
            f"USS diff: {diff['uss']:.1f}MB"
        )
    except Exception as e:
        logger.warning(f"Error during memory cleanup logging: {e}")


class MemoryProfilingMiddleware:
    """WSGI middleware for profiling memory usage across web requests.
    
    This middleware logs memory usage changes that occur during request processing,
    helping identify endpoints that have significant memory impacts.
    
    Attributes:
        app: The WSGI application being wrapped
        logger: Logger instance for recording memory profile information
        _last_mem: Internal storage of the last memory measurement
    """
    
    def __init__(self, app):
        """Initialize the memory profiling middleware.
        
        Args:
            app: The WSGI application to profile
        """
        self.app = app
        self.logger = logging.getLogger('memory_profiler')
        self._last_mem = None
        
    def _format_memory_diff(self, current_mem):
        """Format memory differences between measurements.
        
        Args:
            current_mem: Current memory measurements as returned by get_process_memory()
            
        Returns:
            str: Formatted string showing memory usage and differences
        """
        if not self._last_mem:
            self._last_mem = current_mem
            return "Initial"
            
        diff = {k: current_mem[k] - self._last_mem[k] for k in current_mem}
        self._last_mem = current_mem
        
        return (f"RSS: {current_mem['rss']:.1f}MB (Δ{diff['rss']:+.1f}MB) "
                f"USS: {current_mem['uss']:.1f}MB (Δ{diff['uss']:+.1f}MB) "
                f"Data: {current_mem['data']:.1f}MB (Δ{diff['data']:+.1f}MB)")
    
    def __call__(self, environ, start_response):
        """WSGI interface implementation.
        
        Args:
            environ: WSGI environment dictionary
            start_response: WSGI start_response callable
            
        Returns:
            The response from the wrapped application
        """
        path = environ.get('PATH_INFO')
        method = environ.get('REQUEST_METHOD')
        
        # Skip profiling for static files
        if path.startswith('/static/'):
            return self.app(environ, start_response)
        
        start_mem = get_process_memory()
        start_time = datetime.now()
        
        def memory_profiling_start_response(status, headers, exc_info=None):
            """Custom start_response that adds memory profiling.
            
            Args:
                status: HTTP status string
                headers: List of (header_name, header_value) tuples
                exc_info: Exception info for error responses
                
            Returns:
                The result of the original start_response function
            """
            end_mem = get_process_memory()
            duration = (datetime.now() - start_time).total_seconds()
            
            # Only log non-static paths and significant memory changes
            if not path.startswith('/static/') and (
                abs(end_mem['rss'] - start_mem['rss']) > 1 or  # 1MB threshold
                abs(end_mem['uss'] - start_mem['uss']) > 1
            ):
                self.logger.debug(
                    f"[Memory Profile] {method} {path}\n"
                    f"    Duration: {duration:.3f}s\n"
                    f"    Memory: {self._format_memory_diff(end_mem)}"
                )
            
            return start_response(status, headers, exc_info)
        
        return self.app(environ, memory_profiling_start_response)