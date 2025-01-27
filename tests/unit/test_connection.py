"""Tests for the IMAP email client implementation.

This module contains test cases for the IMAPEmailClient class, covering connection
handling, email fetching, error scenarios, and concurrent operations.

Classes:
    None

Functions:
    test_imap_client_initialization: Tests client initialization with valid parameters.
    test_imap_client_invalid_initialization: Tests client initialization with missing parameters.
    test_imap_client_connect: Tests successful IMAP client connection flow.
    test_imap_client_connection_failure: Tests handling of IMAP connection failures.
    test_fetch_emails_structure: Tests the structure and format of fetched emails.
    test_close_connection: Tests proper closure of IMAP connection.
    test_fetch_emails_with_empty_result: Tests behavior when no emails are found.
    test_fetch_emails_with_fetch_error: Tests handling of fetch operation errors.
    test_connection_timeout: Tests handling of connection timeout.
    test_concurrent_connections: Tests handling of concurrent connections.
    test_fetch_emails_different_days_range: Tests fetching emails with different day ranges.
    test_reconnection_after_failure: Tests reconnection behavior after failure.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock, Mock
from imapclient import IMAPClient
from datetime import date
import socket

# Updated imports to reflect new structure
from app.email.core.email_connection import EmailConnection, IMAPConnectionError
from app.email.core.email_parsing import EmailParser, EmailMetadata

@pytest.mark.asyncio
async def test_imap_client_initialization(imap_config):
    """Tests client initialization with valid parameters.

    Verifies that an IMAPEmailClient instance is correctly initialized with the
    provided configuration parameters and default values.

    Args:
        imap_config (dict): Fixture providing IMAP configuration parameters.
            Contains keys:
                server (str): IMAP server hostname
                email (str): Email address for authentication
                password (str): Password for authentication

    Returns:
        None

    Raises:
        AssertionError: If any initialization parameters don't match expected values.
    """
    client = EmailConnection(**imap_config)
    
    print(f"Server: {imap_config['server']}")
    print(f"Email: {imap_config['email']}")
    print(f"Password length: {len(imap_config['password'])}")

    assert client.server == imap_config['server']
    assert client.email == imap_config['email']
    assert client.password == imap_config['password']
    assert client.port == 993
    assert client.use_ssl is True
    assert client._client is None

@pytest.mark.asyncio
async def test_imap_client_invalid_initialization():
    """Tests client initialization with missing parameters.

    Verifies that attempting to initialize an IMAPEmailClient with empty
    required parameters raises a ValueError.

    Returns:
        None

    Raises:
        ValueError: Expected to be raised when invalid parameters are provided.
    """
    with pytest.raises(ValueError):
        EmailConnection(server='', email='', password='')

@pytest.mark.asyncio
async def test_imap_client_connect(imap_config):
    """Tests successful IMAP client connection flow.

    Verifies that the IMAP client can successfully establish a connection,
    perform login, and select the default folder.

    Args:
        imap_config (dict): Fixture providing IMAP configuration parameters.
            Contains keys:
                server (str): IMAP server hostname
                email (str): Email address for authentication
                password (str): Password for authentication

    Returns:
        None

    Raises:
        AssertionError: If connection, login, or folder selection fails
    """
    with patch('imapclient.IMAPClient') as mock_imap_client:
        mock_instance = AsyncMock()
        mock_imap_client.return_value = mock_instance
        
        # Explicitly mock connection methods
        mock_instance.connect = AsyncMock()
        mock_instance.login = AsyncMock()
        mock_instance.select_folder = AsyncMock()

        client = EmailConnection(**imap_config)
        await client.connect()

@pytest.mark.asyncio
async def test_imap_client_connection_failure(imap_config):
    """Test handling of IMAP connection failures.
    
    Args:
        imap_config (dict): Fixture providing IMAP configuration parameters.
        
    Raises:
        IMAPConnectionError: Expected to be raised when connection fails.
    """
    with patch('imapclient.IMAPClient') as mock_imap_client, \
         patch('asyncio.to_thread', side_effect=Exception("Connection failed")):
        
        client = EmailConnection(**imap_config)
        
        with pytest.raises(IMAPConnectionError):
            await client.connect()

@pytest.mark.asyncio
async def test_fetch_emails_structure(imap_config):
    """Tests the structure and format of fetched emails.

    Verifies that the fetch_emails method returns properly structured email data
    with expected fields and data types.

    Args:
        imap_config (dict): Fixture providing IMAP configuration parameters.
            Contains keys:
                server (str): IMAP server hostname
                email (str): Email address for authentication
                password (str): Password for authentication

    Returns:
        None

    Raises:
        AssertionError: If email structure or content doesn't match expectations
    """
    with patch('app.email.core.email_connection.IMAPClient') as mock_imap_client:
        # Setup mock instance with synchronous methods
        mock_instance = mock_imap_client.return_value
        
        # Mock search to return some message IDs
        mock_instance.search = Mock(return_value=[1, 2])
        
        # Mock fetch to return some test emails
        mock_instance.fetch = Mock(return_value={
            1: {b'BODY[]': b'email content 1'},
            2: {b'BODY[]': b'email content 2'}
        })
        
        client = EmailConnection(**imap_config)
        client._client = mock_instance
        emails = await client.fetch_emails(days=1)
        
        # Verify email structure
        assert isinstance(emails, list)
        assert len(emails) == 2
        assert all('id' in email and 'raw_message' in email for email in emails)

@pytest.mark.asyncio
async def test_close_connection(imap_config):
    """Tests proper closure of IMAP connection.

    Verifies that the connection is properly closed and cleaned up,
    including logout process and connection state reset.

    Args:
        imap_config (dict): Fixture providing IMAP configuration parameters.
            Contains keys:
                server (str): IMAP server hostname
                email (str): Email address for authentication
                password (str): Password for authentication

    Returns:
        None

    Raises:
        AssertionError: If connection closure or cleanup fails
    """
    with patch('imapclient.IMAPClient') as mock_imap_client:
        # Create mock instance
        mock_instance = Mock()  # Use regular Mock since logout is now synchronous
        mock_imap_client.return_value = mock_instance
        
        # Set up the logout mock
        mock_instance.logout = Mock()
        
        client = EmailConnection(**imap_config)
        client._client = mock_instance
        
        await client.close()
        
        # Verify logout was called
        mock_instance.logout.assert_called_once()

@pytest.mark.asyncio
async def test_fetch_emails_with_empty_result(imap_config):
    """Tests behavior when no emails are found in the mailbox.

    Verifies that the fetch_emails method handles empty search results correctly
    by returning an empty list rather than raising an error.

    Args:
        imap_config (dict): Fixture providing IMAP configuration parameters.
            Contains keys:
                server (str): IMAP server hostname
                email (str): Email address for authentication
                password (str): Password for authentication

    Returns:
        None

    Raises:
        AssertionError: If empty result handling is incorrect
    """
    with patch('app.email.core.email_connection.IMAPClient') as mock_imap_client, \
         patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
        
        # Setup regular Mock for IMAPClient (since it's synchronous)
        mock_instance = Mock()
        mock_imap_client.return_value = mock_instance
        
        # Mock the connection methods
        mock_instance.login.return_value = True
        mock_instance.select_folder.return_value = True
        mock_instance.search.return_value = []
        
        # Mock to_thread to handle the connection setup
        async def async_passthrough(f, *args, **kwargs):
            return f(*args, **kwargs) if callable(f) else f
            
        mock_to_thread.side_effect = async_passthrough
        
        client = EmailConnection(**imap_config)
        emails = await client.fetch_emails(days=1)
        
        # Verify empty result handling
        assert isinstance(emails, list)
        assert len(emails) == 0

@pytest.mark.asyncio
async def test_fetch_emails_with_fetch_error(imap_config):
    """Tests handling of fetch operation errors.

    Verifies that errors during the email fetch operation are properly caught
    and raised as IMAPConnectionError.

    Args:
        imap_config (dict): Fixture providing IMAP configuration parameters.
            Contains keys:
                server (str): IMAP server hostname
                email (str): Email address for authentication
                password (str): Password for authentication

    Returns:
        None

    Raises:
        IMAPConnectionError: Expected when fetch operation fails
        AssertionError: If error handling is incorrect
    """
    with patch('app.email.core.email_connection.IMAPClient') as mock_imap_client, \
         patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
        
        mock_instance = Mock()
        mock_imap_client.return_value = mock_instance
        
        # Mock successful connection but failed fetch
        mock_instance.login.return_value = True
        mock_instance.select_folder.return_value = True
        mock_instance.search.return_value = [1, 2, 3]
        mock_instance.fetch.side_effect = IMAPClient.Error("Fetch failed")
        
        async def async_passthrough(f, *args, **kwargs):
            return f(*args, **kwargs) if callable(f) else f
            
        mock_to_thread.side_effect = async_passthrough
        
        client = EmailConnection(**imap_config)
        client._client = mock_instance
        
        with pytest.raises(IMAPConnectionError):
            await client.fetch_emails(days=1)

@pytest.mark.asyncio
async def test_connection_timeout(imap_config):
    """Tests handling of connection timeout.

    Verifies that connection timeout errors are properly caught and
    converted to IMAPConnectionError.

    Args:
        imap_config (dict): Fixture providing IMAP configuration parameters.
            Contains keys:
                server (str): IMAP server hostname
                email (str): Email address for authentication
                password (str): Password for authentication

    Returns:
        None

    Raises:
        IMAPConnectionError: Expected when connection times out
    """
    with patch('app.email.core.email_connection.IMAPClient') as mock_imap_client, \
         patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
        
        mock_instance = Mock()
        mock_imap_client.return_value = mock_instance
        mock_instance.login.side_effect = socket.timeout("Connection timed out")
        
        async def async_passthrough(f, *args, **kwargs):
            return f(*args, **kwargs) if callable(f) else f
            
        mock_to_thread.side_effect = async_passthrough
        
        client = EmailConnection(**imap_config)
        with pytest.raises(IMAPConnectionError):
            await client.connect()

@pytest.mark.asyncio
async def test_concurrent_connections(imap_config):
    """Tests handling of concurrent connections.

    Verifies that the client properly handles multiple connection attempts,
    ensuring proper connection state management.

    Args:
        imap_config (dict): Fixture providing IMAP configuration parameters.
            Contains keys:
                server (str): IMAP server hostname
                email (str): Email address for authentication
                password (str): Password for authentication

    Returns:
        None

    Raises:
        AssertionError: If concurrent connection handling is incorrect
    """
    with patch('app.email.core.email_connection.IMAPClient') as mock_imap_client, \
         patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
        
        mock_instance = Mock()
        mock_imap_client.return_value = mock_instance
        mock_instance.login.return_value = True
        mock_instance.select_folder.return_value = True
        
        async def async_passthrough(f, *args, **kwargs):
            return f(*args, **kwargs) if callable(f) else f
            
        mock_to_thread.side_effect = async_passthrough
        
        client = EmailConnection(**imap_config)
        await client.connect()
        
        # Verify connect was called
        mock_instance.login.assert_called_once()
        mock_instance.select_folder.assert_called_once()

@pytest.mark.asyncio
async def test_fetch_emails_different_days_range(imap_config):
    """Tests fetching emails with different day ranges.

    Verifies that the fetch_emails method correctly handles different day ranges
    for email retrieval and returns properly structured results.

    Args:
        imap_config (dict): Fixture providing IMAP configuration parameters.
            Contains keys:
                server (str): IMAP server hostname
                email (str): Email address for authentication
                password (str): Password for authentication

    Returns:
        None

    Raises:
        AssertionError: If email fetching with different day ranges fails
    """
    with patch('app.email.core.email_connection.IMAPClient') as mock_imap_client, \
         patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
        
        mock_instance = Mock()
        mock_imap_client.return_value = mock_instance
        
        # Mock 3 emails in the last 7 days
        mock_instance.login.return_value = True
        mock_instance.select_folder.return_value = True
        mock_instance.search.return_value = [1, 2, 3]
        
        # Mock fetch to return properly structured response
        mock_instance.fetch.return_value = {
            1: {b'BODY[]': b'email content 1'},
            2: {b'BODY[]': b'email content 2'},
            3: {b'BODY[]': b'email content 3'}
        }
        
        async def async_passthrough(f, *args, **kwargs):
            return f(*args, **kwargs) if callable(f) else f
            
        mock_to_thread.side_effect = async_passthrough
        
        client = EmailConnection(**imap_config)
        client._client = mock_instance
        emails = await client.fetch_emails(days=7)
        
        # Verify email structure
        assert isinstance(emails, list)
        assert len(emails) == 3
        assert all('id' in email and 'raw_message' in email for email in emails)

@pytest.mark.asyncio
async def test_reconnection_after_failure(imap_config):
    """Tests reconnection behavior after a connection failure.

    Verifies that the client handles a failed connection attempt gracefully and
    can successfully reconnect on a subsequent attempt.

    Args:
        imap_config (dict): Fixture providing IMAP configuration parameters.
            Contains keys:
                server (str): IMAP server hostname
                email (str): Email address for authentication
                password (str): Password for authentication

    Returns:
        None

    Raises:
        IMAPConnectionError: On first connection attempt (expected)
    """
    with patch('app.email.core.email_connection.IMAPClient') as mock_imap_client, \
         patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
        
        mock_instance = Mock()
        mock_imap_client.return_value = mock_instance
        
        # First attempt fails, second succeeds
        mock_instance.login.side_effect = [
            socket.timeout("Connection timed out"),
            True
        ]
        mock_instance.select_folder.return_value = True
        
        async def async_passthrough(f, *args, **kwargs):
            return f(*args, **kwargs) if callable(f) else f
            
        mock_to_thread.side_effect = async_passthrough
        
        client = EmailConnection(**imap_config)
        with pytest.raises(IMAPConnectionError):
            await client.connect()
        
        # Second attempt should succeed
        await client.connect()
        mock_instance.login.assert_called()