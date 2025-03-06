"""Flask application entry point.

This module serves as the main entry point for the Flask application.
It creates and runs the Flask application instance using the factory pattern.

Typical usage:
    $ python app.py

Raises:
    ImportError: If the Flask application factory cannot be imported.
    Exception: Any unexpected errors during application startup.
"""
import logging
from hypercorn.config import Config
from hypercorn.run import run
import os
import pathlib
from app.config import configure_logging

# Initialize logging first
configure_logging()
logger = logging.getLogger(__name__)

def setup_https_config() -> Config:
    """Set up Hypercorn configuration with HTTPS support.
    
    This function configures Hypercorn for HTTPS using self-signed certificates.
    If certificates don't exist in the 'certs' directory, they will be generated.
    The function also sets appropriate worker settings, SSL parameters, and 
    SSE-specific configurations for the server.
    
    Returns:
        Config: A fully configured Hypercorn Config object with HTTPS settings.
        
    Raises:
        ImportError: If the certificate generation script cannot be imported.
        OSError: If there are permission issues accessing or creating certificates.
    """
    config = Config()
    
    # Certificate setup
    cert_dir = os.path.join(pathlib.Path(__file__).parent, "certs")
    if not os.path.exists(cert_dir) or \
       not os.path.exists(os.path.join(cert_dir, "cert.pem")) or \
       not os.path.exists(os.path.join(cert_dir, "key.pem")):
        logger.info("Generating SSL certificates...")
        from scripts.generate_cert import generate_self_signed_cert
        generate_self_signed_cert(cert_dir)
        logger.info("SSL certificates generated successfully")
    
    # Basic server config
    config.bind = ["127.0.0.1:5000"]
    config.certfile = os.path.join(cert_dir, "cert.pem")
    config.keyfile = os.path.join(cert_dir, "key.pem")
    config.verify_mode = None  # Don't verify client certs
    config.ciphers = "ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256"  # Modern cipher suite
    
    # Worker configuration
    config.worker_class = "asyncio"
    #config.workers = max(1, min(4, os.cpu_count() - 1))
    config.workers = 1
    config.worker_connections = 1000
    
    # SSE-specific configuration
    config.keep_alive_timeout = 120  # Increase keep-alive timeout for SSE
    config.h11_max_incomplete_size = 0  # Disable max incomplete size limit
    config.websocket_ping_interval = 20  # Keep connections alive
    config.graceful_timeout = 120  # Allow more time for graceful shutdowns
    
    # Application configuration
    config.application_path = "app:create_app()"
    config.reload = False
    
    # Logging configuration
    config.accesslog = None
    config.errorlog = None
    
    # Only log in the main process
    if not os.environ.get('HYPERCORN_WORKER_ID'):
        logger.info(f"Starting Hypercorn with {config.workers} workers (HTTPS enabled)")
    
    return config

if __name__ == "__main__":
    """Application entry point.
    
    Initializes the application configuration and runs the Hypercorn server
    with HTTPS support. Any exceptions during startup are logged and re-raised.
    """
    try:
        config = setup_https_config()
        run(config)
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise