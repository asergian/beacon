import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.email_processor import EmailOrchestrator, ProcessedEmail, ProcessingError
from app.email_connection import IMAPEmailClient
from datetime import datetime
from flask import g
from app import create_app, init_openai_client
from openai import AsyncOpenAI
import asyncio

@pytest.fixture
def sample_email():
    return {
        "id": 1,
        "raw_message": b"""
        From: sender@example.com
        Subject: Test Email
        Date: Fri, 24 Jan 2025 10:00:00 +0000
        \nTest email body.
        """
    }

@pytest.mark.asyncio
class TestEmailProcessor:

    @pytest.mark.asyncio
    async def test_process_emails(self, imap_config, sample_email):
        with patch('app.email_processor.IMAPEmailClient') as mock_imap:
            orchestrator = EmailOrchestrator(imap_config)
            
            # Mock fetch_emails as an async function using AsyncMock
            mock_imap_instance = mock_imap.return_value
            mock_imap_instance.fetch_emails = AsyncMock(return_value=[sample_email])

            # Add debug logging for the mock
            print(f"Mock IMAP fetch_emails returned: {await mock_imap_instance.fetch_emails()}")

            # Process the emails asynchronously
            emails = await orchestrator.process_emails()

            # Add debug logging for processed emails
            print(f"Processed emails: {emails}")

            # Assert that the returned value is a list of ProcessedEmail objects
            assert isinstance(emails, list)
            assert len(emails) == 1
            assert emails[0].subject == "Test Email"

    @patch('app.email_processor.spacy.load', side_effect=Exception("Load Error"))
    def test_nlp_model_load_failure(self, mock_spacy, imap_config):
        with pytest.raises(ProcessingError, match="NLP model initialization failed"):
            EmailOrchestrator(imap_config)

    # @pytest.mark.asyncio
    # async def test_process_no_emails(self, imap_config):
    #     with patch('app.email_connection.IMAPEmailClient') as mock_imap:
    #         orchestrator = EmailOrchestrator(imap_config)
    #         mock_imap.return_value.fetch_emails = AsyncMock(return_value=[])

    #         emails = await orchestrator.process_emails()
    #         assert emails == []

    @pytest.mark.asyncio
    async def test_process_single_email_success(self, imap_config, sample_email):
        orchestrator = EmailOrchestrator(imap_config)
        orchestrator.email_parser.extract_metadata = MagicMock(
            return_value=MagicMock(
                subject="Test Email",
                sender="sender@example.com",
                body="Test email body",
                date=datetime.now()
            )
        )
        orchestrator._analyze_content = MagicMock(return_value={'urgency_indicators': False})
        orchestrator._llm_analysis = MagicMock(return_value={'action_required': False, 'category': "Informational"})
        orchestrator._calculate_priority = MagicMock(return_value=50)

        result = await orchestrator._process_single_email(sample_email)
        assert isinstance(result, ProcessedEmail)
        assert result.subject == "Test Email"

    @pytest.mark.asyncio
    async def test_llm_analysis_success(self, imap_config):
        # Create the Flask app instance
        app = create_app()

        # Push an application context to ensure flask.g.async_openai_client is accessible
        with app.app_context():
            init_openai_client(app)  # This directly ensures g.async_openai_client is available
        
            # Initialize the orchestrator with the provided IMAP config
            orchestrator = EmailOrchestrator(imap_config)
            
            # Mock the _construct_analysis_prompt method to return a predefined prompt
            orchestrator._construct_analysis_prompt = MagicMock(return_value="Test Prompt")
            
            # Mock the OpenAI response (mocking the actual chat completion response)
            response_mock = MagicMock(choices=[MagicMock(message=MagicMock(content='{"action_required": true, "category": "Work", "action_items": [], "summary": "Summary"}'))])
            
            # Patch flask.g.async_openai_client to mock the OpenAI client object
            with patch.object(g, 'async_openai_client', new_callable=MagicMock) as mock_client:
                # Mock the method `chat.completions.create` to return an awaitable response
                mock_client.chat.completions.create = MagicMock(return_value=await asyncio.to_thread(lambda: response_mock))

                # Call the _llm_analysis method which internally uses the mocked OpenAI client
                result = await orchestrator._llm_analysis(MagicMock(), {})
                
                # Assertions to ensure the result matches the mocked response
                assert result['action_required'] is True  # Ensure the action_required field is correctly parsed
                assert result['category'] == "Work"  # Ensure the category field is correctly parsed

    @pytest.mark.asyncio
    async def test_llm_analysis_fallback(self, imap_config):
        app = create_app()

        # Push an application context to ensure flask.g.async_openai_client is accessible
        with app.app_context():
            init_openai_client(app)  # This directly ensures g.async_openai_client is available
            
            # Setup EmailOrchestrator
            orchestrator = EmailOrchestrator(imap_config)
            orchestrator._fallback_analysis = MagicMock(return_value={'action_required': False, 'category': 'Informational'})

            # Patch the OpenAI client method to simulate failure
            with patch.object(g, 'async_openai_client', side_effect=Exception("LLM Failure")):
                # Call the _llm_analysis method and check the fallback behavior
                result = await orchestrator._llm_analysis(MagicMock(), {})
                assert result['action_required'] is False
                assert result['category'] == "Informational"

    def test_priority_no_vip_no_urgency(self, imap_config):
        orchestrator = EmailOrchestrator(imap_config)
        metadata = MagicMock(sender='normal@example.com')
        nlp_data = {'urgency_indicators': False}
        llm_results = {'action_required': False}

        score = orchestrator._calculate_priority(metadata, nlp_data, llm_results)
        assert score == 50  # Base score only

    @pytest.mark.asyncio
    async def test_process_emails_with_errors(self, imap_config, sample_email):
        orchestrator = EmailOrchestrator(imap_config)
        orchestrator._process_single_email = MagicMock(side_effect=[None, ProcessingError("Failed")])

        with patch('app.email_connection.IMAPEmailClient') as mock_imap:
            mock_imap.return_value.fetch_emails = AsyncMock(return_value=[sample_email, sample_email])
            emails = await orchestrator.process_emails()
            assert len(emails) == 0
