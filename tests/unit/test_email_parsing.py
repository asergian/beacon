"""Unit tests for the email parsing functionality.

This module contains comprehensive tests for the EmailParser class, covering various
email formats, encodings, and edge cases. Tests include validation of basic emails,
multipart messages, attachments, and different date formats.

Typical usage example:
    pytest tests/test_email_parsing.py
"""

import pytest
from datetime import datetime
from app.email.core.email_parsing import EmailParser, EmailParsingError, EmailMetadata

@pytest.fixture
def parser():
    """Creates an EmailParser instance for testing.

    Returns:
        EmailParser: A fresh instance of the EmailParser class.
    """
    return EmailParser()

@pytest.fixture
def basic_email():
    """Provides a basic email in bytes format for testing.

    Returns:
        bytes: A simple email with From, Subject, Date headers and plain text body.
    """
    return b"""From: sender@example.com
Subject: Test Subject
Date: Thu, 24 Jan 2025 10:00:00 +0000

Test body content
"""

@pytest.fixture
def multipart_email():
    """Provides a multipart email with both plain text and HTML parts.

    Returns:
        bytes: A multipart email containing both text/plain and text/html content.
    """
    return b"""From: sender@example.com
Subject: Multipart Email
MIME-Version: 1.0
Content-Type: multipart/alternative; boundary="boundary123"

--boundary123
Content-Type: text/plain; charset=UTF-8

Plain text body
--boundary123
Content-Type: text/html; charset=UTF-8

<html><body>HTML body</body></html>
--boundary123--
"""

@pytest.fixture
def email_with_attachment():
    return b"""From: sender@example.com
Subject: Email with attachment
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="boundary123"

--boundary123
Content-Type: text/plain; charset=UTF-8

Main body text
--boundary123
Content-Type: application/pdf
Content-Disposition: attachment; filename="test.pdf"

PDF content here
--boundary123--"""

@pytest.fixture
def malformed_multipart():
    return b"""From: sender@example.com
Subject: Malformed Multipart
Content-Type: multipart/mixed; boundary="boundary123"

--boundary123
Content-Type: text/plain
Incomplete boundary structure
"""

@pytest.fixture
def non_utf8_email():
    return b"""From: sender@example.com
Subject: Test Non-UTF8
Content-Type: text/plain; charset=iso-8859-1

Special chars: \xF6\xE4\xFC
"""

@pytest.fixture
def date_test_template():
    def _make_email(date_header):
        return b"""From: sender@example.com
Subject: Date Test
""" + date_header + b"""

Test content
"""
    return _make_email

@pytest.fixture
def expected_metadata():
    return {
        'basic': {
            'sender': 'sender@example.com',
            'subject': 'Test Subject',
            'body': 'Test body content',
        },
        'multipart': {
            'sender': 'sender@example.com',
            'subject': 'Multipart Email',
            'body': 'Plain text body',
        }
    }

class TestEmailParser:
    """Test suite for EmailParser class.
    
    This test suite verifies the functionality of the EmailParser class,
    particularly its ability to extract metadata from various email formats.
    """

    def test_extract_metadata_basic_email(self, parser, basic_email, expected_metadata):
        """Tests parsing of a basic email with all required fields.

        Args:
            parser: EmailParser fixture instance.
            basic_email: Fixture providing basic email content.
            expected_metadata: Fixture providing expected parsing results.

        Raises:
            AssertionError: If the parsed metadata doesn't match expected values.
        """
        metadata = parser.extract_metadata(basic_email)
        expected = expected_metadata['basic']
        
        assert isinstance(metadata, EmailMetadata)
        assert metadata.sender == expected['sender']
        assert metadata.subject == expected['subject']
        assert metadata.body.strip() == expected['body']
        assert isinstance(metadata.date, datetime)
        self._validate_metadata_fields(metadata)

    def _validate_metadata_fields(self, metadata):
        """Validates common metadata fields.

        Performs standard validation checks on the required fields of the
        parsed email metadata.

        Args:
            metadata: EmailMetadata instance to validate.

        Raises:
            AssertionError: If any validation check fails.
        """
        assert len(metadata.sender) > 0
        assert '@' in metadata.sender
        assert len(metadata.subject) > 0
        assert len(metadata.body.strip()) > 0

    def test_extract_metadata_multipart(self, parser, multipart_email, expected_metadata):
        """Tests parsing of multipart emails.

        Verifies that the parser correctly extracts plain text content from
        multipart emails and properly handles HTML content.

        Args:
            parser: EmailParser fixture instance.
            multipart_email: Fixture providing multipart email content.
            expected_metadata: Fixture providing expected parsing results.

        Raises:
            AssertionError: If the parsed metadata doesn't match expected values
                or if HTML content is present in the body.
        """
        metadata = parser.extract_metadata(multipart_email)
        expected = expected_metadata['multipart']
        
        assert isinstance(metadata, EmailMetadata)
        assert metadata.sender == expected['sender']
        assert expected['body'] in metadata.body
        assert '<html>' not in metadata.body
        assert '<body>' not in metadata.body
        assert metadata.body.strip() == expected['body']
        self._validate_metadata_fields(metadata)

    @pytest.mark.parametrize('invalid_input', [
        b'',  # Empty bytes
        None,  # None input
        b'Invalid content',  # Missing headers
        b'From: invalid@@email\nSubject: Test',  # Invalid email
        b'Subject: Test\nBody: content',  # Missing From
        b'From: test@example.com',  # Missing Subject
        {},  # Empty dict
        {'wrong_key': b'content'},  # Dict with wrong key
        {'raw_message': ''},  # Dict with empty message
    ])
    def test_invalid_inputs(self, parser, invalid_input):
        """Test various invalid inputs return None instead of raising exceptions."""
        metadata = parser.extract_metadata(invalid_input)
        assert metadata is None

    def test_non_utf8_content_handling(self, parser, non_utf8_email):
        """Tests handling of non-UTF8 encoded content.

        Verifies that the parser correctly handles and converts content
        encoded in other character sets (e.g., ISO-8859-1).

        Args:
            parser: EmailParser fixture instance.
            non_utf8_email: Fixture providing email with non-UTF8 content.

        Raises:
            AssertionError: If character encoding conversion fails.
        """
        metadata = parser.extract_metadata(non_utf8_email)
        assert isinstance(metadata, EmailMetadata)
        assert 'Special chars: öäü' in metadata.body
        assert metadata.sender == 'sender@example.com'
        self._validate_metadata_fields(metadata)

    def test_date_parsing_formats(self, parser, date_test_template):
        """Tests parsing of various date formats.

        Verifies that the parser can handle different date formats and
        timezone specifications correctly.

        Args:
            parser: EmailParser fixture instance.
            date_test_template: Fixture providing date template function.

        Raises:
            AssertionError: If date parsing fails for any supported format.
        """
        test_cases = [
            (b"Date: Wed, 15 Nov 2023 14:30:00 +0000", (2023, 11, 15, 14, 30)),
            (b"Date: 2023-11-15T14:30:00Z", (2023, 11, 15, 14, 30)),
            (b"Date: Thu, 24 Jan 2025 10:00:00 -0500", (2025, 1, 24, 10, 0)),
            (b"Date: Invalid Date", None),
        ]
        
        for date_input, expected in test_cases:
            email_content = date_test_template(date_input)
            metadata = parser.extract_metadata(email_content)
            assert isinstance(metadata, EmailMetadata)
            self._validate_metadata_fields(metadata)
            
            if expected is None:
                assert isinstance(metadata.date, datetime)
            else:
                year, month, day, hour, minute = expected
                assert metadata.date.year == year
                assert metadata.date.month == month
                assert metadata.date.day == day
                assert metadata.date.hour == hour
                assert metadata.date.minute == minute

    def test_dict_input_handling(self, parser, basic_email):
        """Test handling of dictionary input format."""
        # Test with bytes
        dict_input = {'raw_message': basic_email}
        metadata = parser.extract_metadata(dict_input)
        assert isinstance(metadata, EmailMetadata)
        assert metadata.sender == 'sender@example.com'
        
        # Test with string
        dict_input = {'raw_message': basic_email.decode('utf-8')}
        metadata = parser.extract_metadata(dict_input)
        assert isinstance(metadata, EmailMetadata)
        assert metadata.sender == 'sender@example.com'

    def test_email_with_attachments(self, parser, email_with_attachment):
        """Test email with attachments is handled correctly."""
        metadata = parser.extract_metadata(email_with_attachment)
        assert isinstance(metadata, EmailMetadata)
        assert 'Main body text' in metadata.body
        assert 'PDF content' not in metadata.body
        self._validate_metadata_fields(metadata)

    def test_malformed_multipart(self, parser, malformed_multipart):
        """Test handling of malformed multipart emails."""
        metadata = parser.extract_metadata(malformed_multipart)
        assert isinstance(metadata, EmailMetadata)
        assert len(metadata.body.strip()) > 0
        self._validate_metadata_fields(metadata)