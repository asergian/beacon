import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock

from app.email.processing.processor import (
    EmailProcessor, 
    EmailProcessingError,
    LLMProcessingError,
    NLPProcessingError
)
from app.email.parsing.parser import EmailMetadata
from app.email.models.processed_email import ProcessedEmail

@pytest.fixture
def mock_dependencies():
    return {
        'email_client': AsyncMock(),
        'text_analyzer': Mock(),
        'llm_analyzer': AsyncMock(),
        'priority_calculator': Mock(),
        'parser': Mock()
    }

@pytest.fixture
def email_processor(mock_dependencies):
    return EmailProcessor(
        email_client=mock_dependencies['email_client'],
        text_analyzer=mock_dependencies['text_analyzer'],
        llm_analyzer=mock_dependencies['llm_analyzer'],
        priority_calculator=mock_dependencies['priority_calculator'],
        parser=mock_dependencies['parser']
    )

@pytest.fixture
def sample_email_metadata():
    return EmailMetadata(
        id='test123',
        subject='Test Email',
        sender='sender@example.com',
        body='This is a test email body',
        date=datetime.now()
    )

@pytest.mark.asyncio
async def test_process_single_email_success(email_processor, sample_email_metadata):
    # Mock analyzer responses
    email_processor.text_analyzer.analyze.return_value = {
        'entities': {'person': ['John']},
        'is_urgent': True
    }
    
    email_processor.llm_analyzer.analyze.return_value = {
        'needs_action': True,
        'category': 'IMPORTANT',
        'action_items': ['Reply to sender'],
        'summary': 'Test email summary'
    }
    
    email_processor.priority_calculator.score.return_value = (8, 'HIGH')

    # Process email
    result = await email_processor._process_single_email(sample_email_metadata)

    # Assertions
    assert isinstance(result, ProcessedEmail)
    assert result.id == 'test123'
    assert result.subject == 'Test Email'
    assert result.needs_action == True
    assert result.category == 'IMPORTANT'
    assert result.priority == 8
    assert result.priority_level == 'HIGH'

@pytest.mark.asyncio
async def test_analyze_parsed_emails_success(email_processor, sample_email_metadata):
    # Mock successful processing of multiple emails
    email_processor.text_analyzer.analyze.return_value = {
        'entities': {},
        'is_urgent': False
    }
    
    email_processor.llm_analyzer.analyze.return_value = {
        'needs_action': False,
        'category': 'NORMAL',
        'action_items': [],
        'summary': 'Summary'
    }
    
    email_processor.priority_calculator.score.return_value = (3, 'LOW')

    results = await email_processor.analyze_parsed_emails([sample_email_metadata] * 3)
    
    assert len(results) == 3
    assert all(isinstance(r, ProcessedEmail) for r in results)

@pytest.mark.asyncio
async def test_process_single_email_nlp_error(email_processor, sample_email_metadata):
    # Mock NLP analyzer failure
    email_processor.text_analyzer.analyze.side_effect = Exception("NLP Error")

    with pytest.raises(EmailProcessingError):
        await email_processor._process_single_email(sample_email_metadata)

@pytest.mark.asyncio
async def test_process_single_email_llm_error(email_processor, sample_email_metadata):
    # Mock successful NLP but failed LLM
    email_processor.text_analyzer.analyze.return_value = {'entities': {}}
    email_processor.llm_analyzer.analyze.side_effect = Exception("LLM Error")

    with pytest.raises(EmailProcessingError):
        await email_processor._process_single_email(sample_email_metadata)

@pytest.mark.asyncio
async def test_context_manager(email_processor):
    async with email_processor as processor:
        assert processor == email_processor
    
    # Verify cleanup
    email_processor.email_client.close.assert_called_once()

@pytest.mark.asyncio
async def test_analyze_parsed_emails_partial_failure(email_processor, sample_email_metadata):
    # Mock one success, one failure
    email_processor.text_analyzer.analyze.side_effect = [
        {'entities': {}, 'is_urgent': False},
        Exception("NLP Error")
    ]
    
    email_processor.llm_analyzer.analyze.return_value = {
        'needs_action': False,
        'category': 'NORMAL',
        'action_items': [],
        'summary': 'Summary'
    }
    
    email_processor.priority_calculator.score.return_value = (3, 'LOW')

    results = await email_processor.analyze_parsed_emails([sample_email_metadata] * 2)
    
    # Should return only successful results
    assert len(results) == 1
    assert isinstance(results[0], ProcessedEmail) 