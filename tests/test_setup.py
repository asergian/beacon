import pytest
from app import create_app
from app.config import Config
import logging

class TestConfig(Config):
    TESTING = True
    IMAP_SERVER = 'test.server'
    EMAIL = 'test@example.com'
    IMAP_PASSWORD = 'test_password'
    OPENAI_API_KEY = 'test_key'
    LOGGING_LEVEL = logging.DEBUG  # Ensure logging is testable

@pytest.fixture
def app():
    app = create_app(TestConfig)
    return app

@pytest.fixture
def client(app):
    return app.test_client()

def test_create_app(app):
    """Test application creation and basic configuration."""
    assert app.config['TESTING']
    assert 'EMAIL_ORCHESTRATOR' in app.config
    assert app.config['IMAP_SERVER'] == 'test.server'

def test_home_route(client):
    """Test the home route returns 200 OK."""
    response = client.get('/')
    assert response.status_code == 200

def test_config_loading():
    """Test that configuration is loaded correctly."""
    app = create_app(TestConfig)
    assert app.config['OPENAI_API_KEY'] == 'test_key'
    assert app.config['EMAIL'] == 'test@example.com'

def test_email_orchestrator_initialization(app):
    """Verify email orchestrator is correctly initialized."""
    email_orchestrator = app.config['EMAIL_ORCHESTRATOR']
    assert email_orchestrator is not None
    
    # Verify IMAP client configuration directly
    assert email_orchestrator.imap_client._config['server'] == 'test.server'
    assert email_orchestrator.imap_client._config['email'] == 'test@example.com'
    
    # Verify VIP list
    assert email_orchestrator.vip_list == []
    
    # Additional checks for other components
    assert email_orchestrator.email_parser is not None
    assert email_orchestrator.nlp is not None
    assert email_orchestrator.logger is not None

def test_logging_configuration(app):
    """Ensure logging is configured correctly."""
    assert logging.getLogger().level == app.config['LOGGING_LEVEL']

def test_route_registration(app):
    """Check that routes are registered."""
    # This assumes you have specific routes to check
    # Modify based on your actual routes
    with app.test_request_context():
        assert '/' in [rule.rule for rule in app.url_map.iter_rules()]

def test_config_environment_variables(monkeypatch):
    """Test handling of environment-based configuration."""
    # Simulate environment variable configuration
    monkeypatch.setenv('FLASK_ENV', 'testing')
    app = create_app(TestConfig)
    assert app.config['TESTING'] is True

def test_app_not_in_debug_mode_for_production():
    """Ensure debug mode is off in production."""
    class ProductionConfig(Config):
        TESTING = False

    app = create_app(ProductionConfig)
    assert app.debug is False

# Add more specific tests based on your application's functionality
# For example, if you have specific email processing routes or methods
def test_email_processing_route(client):
    """Example of a route-specific test."""
    # Implement based on your specific email processing endpoint
    pass