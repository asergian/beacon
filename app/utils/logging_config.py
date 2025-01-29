import logging

def setup_logging():
    logging.basicConfig(level=logging.INFO)  # Set the desired logging level
    logger = logging.getLogger(__name__)
    return logger