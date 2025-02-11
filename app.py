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

# Initialize logging
configure_logging()
logger = logging.getLogger(__name__)

def setup_https_config() -> Config:
    """Set up Hypercorn configuration with HTTPS support."""
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
    
    # Worker configuration
    config.worker_class = "asyncio"
    config.workers = max(1, min(4, os.cpu_count() - 1))
    config.worker_connections = 1000
    
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
    try:
        config = setup_https_config()
        run(config)
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise