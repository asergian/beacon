import pytest
from unittest.mock import Mock, patch, AsyncMock

@pytest.fixture
def client(app):
    return app.test_client()

# test_routes.py
def test_show_emails(client, app, headers):
    with app.app_context():
        with patch('flask.current_app.config') as mock_config:
            mock_orchestrator = AsyncMock()
            mock_orchestrator.process_emails.return_value = []
            mock_config.__getitem__.return_value = mock_orchestrator
            
            response = client.get('/emails', headers=headers)
            assert response.status_code == 200

@pytest.mark.asyncio
async def test_show_emails_error(client, app, headers):
    with app.app_context():
        with patch('flask.current_app.config') as mock_config:
            mock_orchestrator = AsyncMock()
            mock_orchestrator.process_emails.side_effect = Exception("Test error")
            mock_config.__getitem__.return_value = mock_orchestrator
            
            response = await client.get('/emails', headers=headers)
            assert response.status_code == 500