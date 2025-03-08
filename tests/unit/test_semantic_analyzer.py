import pytest
from unittest.mock import AsyncMock, Mock, patch
import json
from flask import g, Flask

from app.email.analyzers.semantic.analyzer import SemanticAnalyzer
from app.email.models.exceptions import LLMProcessingError
from app.email.models.processed_email import ProcessedEmail

@pytest.fixture
def app():
    app = Flask(__name__)
    return app

@pytest.fixture
def app_context(app):
    with app.app_context():
        yield

@pytest.fixture
def analyzer():
    return SemanticAnalyzer(model="test-model")

@pytest.fixture
def sample_email():
    return ProcessedEmail(
        id="test123",
        subject="Test Subject",
        sender="test@example.com",
        body="Test body content",
        date="2024-01-01",
        needs_action=False,
        category="UNPROCESSED",
        action_items=[],
        summary="",
        priority=0,
        priority_level="LOW"
    )

@pytest.fixture
def sample_nlp_results():
    return {
        'entities': {'PERSON': 'John'},
        'key_phrases': ['test content'],
        'is_urgent': True
    }

@pytest.fixture
def mock_openai_response():
    response_content = {
        'needs_action': True,
        'category': 'Work',
        'action_items': [{'description': 'Reply', 'due_date': '2024-01-02'}],
        'summary': 'Test summary',
        'priority': 75
    }
    
    mock_response = Mock()
    mock_response.choices = [
        Mock(message=Mock(content=json.dumps(response_content)))
    ]
    return mock_response

@pytest.mark.asyncio
async def test_analyze_success(app_context, analyzer, sample_email, sample_nlp_results, mock_openai_response):
    mock_client = AsyncMock()
    mock_client.chat.completions.create.return_value = mock_openai_response
    
    with patch.object(g, 'get', return_value=mock_client):
        result = await analyzer.analyze(sample_email, sample_nlp_results)
    
    assert isinstance(result, dict)
    assert result['needs_action'] == True
    assert result['category'] == 'Work'
    assert len(result['action_items']) == 1
    assert result['priority'] == 75

@pytest.mark.asyncio
async def test_analyze_missing_client(app_context, analyzer, sample_email, sample_nlp_results):
    with patch.object(g, 'get', return_value=None):
        with pytest.raises(LLMProcessingError, match="OpenAI client not available"):
            await analyzer.analyze(sample_email, sample_nlp_results)

@pytest.mark.asyncio
async def test_analyze_api_error(app_context, analyzer, sample_email, sample_nlp_results):
    mock_client = AsyncMock()
    mock_client.chat.completions.create.side_effect = Exception("API Error")
    
    with patch.object(g, 'get', return_value=mock_client):
        with pytest.raises(LLMProcessingError):
            await analyzer.analyze(sample_email, sample_nlp_results)

def test_create_analysis_prompt(app_context, analyzer, sample_email, sample_nlp_results):
    prompt = analyzer._create_analysis_prompt(sample_email, sample_nlp_results)
    
    assert isinstance(prompt, str)
    assert sample_email.subject in prompt
    assert sample_email.sender in prompt
    assert sample_email.body in prompt

def test_parse_response_valid_json(analyzer):
    valid_json = '''
    {
        "needs_action": true,
        "category": "Work",
        "action_items": [],
        "summary": "Test",
        "priority": 50
    }
    '''
    result = analyzer._parse_response(valid_json)
    
    assert result['needs_action'] == True
    assert result['category'] == "Work"
    assert isinstance(result['action_items'], list)
    assert result['summary'] == "Test"
    assert result['priority'] == 50

def test_parse_response_invalid_json(analyzer):
    invalid_json = "Invalid JSON content"
    
    with pytest.raises(LLMProcessingError, match="Invalid JSON response"):
        analyzer._parse_response(invalid_json)

def test_parse_response_with_markdown_formatting(analyzer):
    markdown_json = '''```json
    {
        "needs_action": true,
        "category": "Work",
        "action_items": [],
        "summary": "Test",
        "priority": 50
    }
    ```'''
    
    result = analyzer._parse_response(markdown_json)
    assert result['needs_action'] == True
    assert result['category'] == "Work" 