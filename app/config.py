# app/config.py
import os
from dotenv import load_dotenv
import logging
import logging.config

# Load environment variables immediately
load_dotenv()

class SafeStreamHandler(logging.StreamHandler):
    """A StreamHandler that safely handles string encoding."""
    def emit(self, record):
        try:
            msg = self.format(record)
            stream = self.stream
            # Write with encoding if stream has encoding defined
            if hasattr(stream, 'encoding') and stream.encoding:
                stream.write(msg.encode(stream.encoding).decode(stream.encoding))
            else:
                stream.write(msg)
            stream.write(self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)

class Config:
    """Base configuration class."""
    
    def __init__(self):
        """Initialize configuration with environment variables."""
        # IMAP Configuration
        self.IMAP_SERVER = os.environ.get('IMAP_SERVER') or 'imap.gmail.com'
        self.EMAIL = os.environ.get('EMAIL') or 'your-email@example.com'
        self.IMAP_PASSWORD = os.environ.get('IMAP_PASSWORD') or 'your-email-password'
        
        # Load environment variables into config
        self.REDIS_TOKEN = os.environ.get('REDIS_TOKEN')
        self.REDIS_URL = os.environ.get('REDIS_URL')

        # OpenAI Configuration
        self.OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY') or 'your-default-openai-key'
        
        # TinyMCE Configuration
        self.TINYMCE_API_KEY = os.environ.get('TINYMCE_API_KEY') or 'your-default-tiny-mce-key'

        self.FLASK_SECRET_KEY = os.environ.get('FLASK_SECRET_KEY') or 'your-default-flask-secret-key'
        
        # Logging Configuration
        self.LOGGING_LEVEL = os.environ.get('LOGGING_LEVEL', 'ERROR').upper()
        
        # Redis Configuration (if used)
        self.REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379')
        
        # Database Configuration
        database_url = os.environ.get('DATABASE_URL', 'postgresql://localhost/beacon')
        # Handle Render's postgres:// URLs
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        self.SQLALCHEMY_DATABASE_URI = database_url
        self.SQLALCHEMY_TRACK_MODIFICATIONS = os.environ.get('SQLALCHEMY_TRACK_MODIFICATIONS', False)
        
        # Debug flag
        self.DEBUG = os.environ.get('FLASK_DEBUG', '0') == '1'
        
    def __getitem__(self, key):
        """Allow dictionary-style access to config values."""
        return getattr(self, key)
        
    def get(self, key, default=None):
        """Implement get method for compatibility with dict interface."""
        return getattr(self, key, default)

def configure_logging():
    """Configure application-wide logging."""
    # Get the logging level from environment
    log_level = os.environ.get('LOGGING_LEVEL', 'ERROR').upper()
    
    logging.config.dictConfig({
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'standard': {
                'format': '%(asctime)s | %(name)-32s | %(levelname)-8s | %(message)s',
                'datefmt': '%H:%M:%S'
            },
            'operation': {
                'format': '%(asctime)s | %(name)-32s | %(levelname)-8s\n%(message)s',
                'datefmt': '%H:%M:%S'
            }
        },
        'handlers': {
            'console': {
                'level': log_level,  # Use environment-specified level
                'formatter': 'standard',
                'class': 'app.config.SafeStreamHandler',
                'stream': 'ext://sys.stdout',
            },
            'operation': {
                'level': log_level,  # Use environment-specified level
                'formatter': 'operation',
                'class': 'app.config.SafeStreamHandler',
                'stream': 'ext://sys.stdout',
            }
        },
        'loggers': {
            '': {  # Root logger
                'handlers': ['console'],
                'level': log_level,  # Use environment-specified level
                'propagate': False
            },
            'app.email.pipeline': {
                'handlers': ['operation'],
                'level': log_level,  # Use environment-specified level
                'propagate': False
            },
            'app.email.storage.cache': {
                'handlers': ['console'],
                'level': log_level,  # Use environment-specified level
                'propagate': False
            },
            'app.email.core': {
                'handlers': ['console'],
                'level': log_level,  # Use environment-specified level
                'propagate': False
            },
            'app.email.analyzers': {
                'handlers': ['console'],
                'level': log_level,  # Use environment-specified level
                'propagate': False
            },
            'app.models': {
                'handlers': ['console'],
                'level': log_level,  # Use environment-specified level
                'propagate': False
            }
        }
    })

def format_log_message(msg: str, wrap_length: int = 100) -> str:
    """Format a log message with proper wrapping"""
    if len(msg) <= wrap_length:
        return msg
        
    words = msg.split()
    lines = []
    current_line = []
    current_length = 0
    
    for word in words:
        if current_length + len(word) + 1 <= wrap_length:
            current_line.append(word)
            current_length += len(word) + 1
        else:
            if current_line:
                lines.append(' '.join(current_line))
            current_line = [word]
            current_length = len(word)
            
    if current_line:
        lines.append(' '.join(current_line))
        
    return '\n    '.join(lines)  # Indent continuation lines