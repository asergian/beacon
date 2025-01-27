import pytest
from app import create_app
from app.config import Config
import logging
from unittest.mock import patch, AsyncMock

class TestConfig(Config):
    TESTING = True
    IMAP_SERVER = 'test.server'
    EMAIL = 'test@example.com'
    IMAP_PASSWORD = 'test_password'
    OPENAI_API_KEY = 'test_key'
    LOGGING_LEVEL = 'DEBUG'

@pytest.fixture
def app(monkeypatch):
    # Mock environment variables if needed
    monkeypatch.setenv('OPENAI_API_KEY', 'test_key')
    monkeypatch.setenv('EMAIL', 'test@example.com')
    monkeypatch.setenv('IMAP_SERVER', 'test.server')
    monkeypatch.setenv('IMAP_PASSWORD', 'test_password')
    monkeypatch.setenv('LOGGING_LEVEL', 'DEBUG')
    app = create_app(TestConfig)
    return app

@pytest.fixture
def client(app):
    return app.test_client()

@patch('app.email.core.email_connection.EmailConnection.connect', new_callable=AsyncMock)
def test_create_app(mock_connect, app):
    """Test application creation and basic configuration."""
    mock_connect.return_value = None
    assert app.config['TESTING']
    assert app.config['IMAP_SERVER'] == 'test.server'

def test_home_route(client):
    """Test the home route returns 200 OK."""
    response = client.get('/')
    assert response.status_code == 200

@patch('app.email.core.email_connection.EmailConnection.connect', new_callable=AsyncMock)
def test_config_loading(mock_connect, app):
    """Test that configuration is loaded correctly."""
    mock_connect.return_value = None
    assert app.config['OPENAI_API_KEY'] == 'test_key'
    assert app.config['EMAIL'] == 'test@example.com'

def test_email_orchestrator_initialization(app):
    """Verify email orchestrator is correctly initialized."""
    # This test might need to be moved to integration tests if EMAIL_ORCHESTRATOR
    # is not part of the basic app setup
    pytest.skip("Email orchestrator initialization should be tested in integration tests")

def test_logging_configuration(app):
    """Ensure logging is configured correctly."""
    expected_level = app.config['LOGGING_LEVEL']
    assert logging.getLogger().level == logging.getLevelName(expected_level)

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