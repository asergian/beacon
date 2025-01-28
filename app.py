"""Flask application entry point.

This module serves as the main entry point for the Flask application.
It creates and runs the Flask application instance using the factory pattern.

Typical usage:
    $ python app.py

Raises:
    ImportError: If the Flask application factory cannot be imported.
    Exception: Any unexpected errors during application startup.
"""
from app import create_app
import asyncio
from hypercorn.config import Config
from hypercorn.asyncio import serve
import logging
from asgiref.wsgi import WsgiToAsgi
import os
import pathlib

# Set up basic logging before app creation
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def setup_https_config() -> Config:
    """Set up Hypercorn configuration with HTTPS support."""
    config = Config()
    
    # Get the absolute path to the certificates
    cert_dir = os.path.join(pathlib.Path(__file__).parent, "certs")
    
    # Check if certificates exist, if not, generate them
    if not os.path.exists(cert_dir) or \
       not os.path.exists(os.path.join(cert_dir, "cert.pem")) or \
       not os.path.exists(os.path.join(cert_dir, "key.pem")):
        logger.info("Generating SSL certificates...")
        from scripts.generate_cert import generate_self_signed_cert
        generate_self_signed_cert(cert_dir)
        logger.info("SSL certificates generated successfully")
    
    # Configure HTTPS
    #config.bind = ["localhost:5000"]
    config.bind = ["127.0.0.1:5000"]
    config.certfile = os.path.join(cert_dir, "cert.pem")
    config.keyfile = os.path.join(cert_dir, "key.pem")
    
    return config

try:
    logger.info("Starting application creation...")
    flask_app = create_app()
    # Convert WSGI app to ASGI
    app = WsgiToAsgi(flask_app)
    logger.info("Application created successfully")
except ImportError as e:
    logger.error(f"Failed to import application factory: {e}")
    raise
except Exception as e:
    logger.error(f"Failed to create application instance: {e}")
    raise

if __name__ == "__main__":
    try:
        logger.info('App starting with Hypercorn (HTTPS enabled)...')
        config = setup_https_config()
        asyncio.run(serve(app, config))
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise