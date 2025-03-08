# Email Parsing Module

A comprehensive email parsing and processing module that extracts structured metadata from raw email messages. This module handles various email formats, encodings, and special cases to provide consistent, normalized data.

## Features

- Extract metadata from raw email messages and API responses
- Support for both Gmail API format and standard MIME format
- Robust header decoding with multiple fallback mechanisms
- HTML and plain text content processing
- Comprehensive error handling and logging
- Memory-optimized processing for large messages

## Structure

The module is organized into the following components:

```
app/email/parsing/
├── __init__.py        # Package exports and documentation
├── parser.py          # Main parser implementation
├── README.md          # This documentation file
└── utils/             # Specialized utility functions
    ├── __init__.py    # Utility exports
    ├── body_extractor.py # Email body extraction utilities
    ├── date_utils.py  # Date parsing and normalization
    ├── header_utils.py # Header decoding and extraction
    └── html_utils.py  # HTML processing utilities
```

## Usage

### Basic Usage

```python
from app.email.parsing import EmailParser

# Create a parser instance
parser = EmailParser()

# Extract metadata from raw email data
metadata = parser.extract_metadata(raw_email)

# Access structured metadata
print(f"Subject: {metadata.subject}")
print(f"From: {metadata.sender}")
print(f"Date: {metadata.date}")
print(f"Body: {metadata.body[:100]}...")  # First 100 chars of body
```

### Working with Pre-processed Email Data

```python
# For emails that have been pre-processed (e.g., from Gmail API)
preprocessed_email = {
    'id': 'msg123',
    'from': 'sender@example.com',
    'subject': 'Hello World',
    'body_html': '<p>This is the message</p>',
    'body_text': 'This is the message',
    'parsed_date': '2023-05-15T14:30:00'
}

metadata = parser.extract_metadata(preprocessed_email)
```

### Using Individual Utilities

```python
from app.email.parsing.utils import decode_header, normalize_date, strip_html

# Decode an encoded email header
subject = decode_header("=?utf-8?B?SGVsbG8gV29ybGQ=?=")  # "Hello World"

# Normalize a date string to datetime
date = normalize_date("2023-05-15T14:30:00")

# Strip HTML tags from content
plain_text = strip_html("<p>Hello <b>World</b></p>")  # "Hello World"
```

## Key Components

### EmailParser

The main class for parsing emails and extracting metadata.

**Methods:**
- `extract_metadata(raw_email)`: Parse and extract structured metadata

### EmailMetadata

A dataclass that holds structured email information.

**Attributes:**
- `id`: Unique email ID
- `subject`: Email subject
- `sender`: Email sender
- `body`: Email body (HTML or text)
- `date`: Email date as datetime object

### Utility Modules

#### Date Utils
- `normalize_date()`: Convert various date formats to datetime
- `parse_email_date()`: Parse RFC 2822 date format from email

#### Header Utils
- `decode_header()`: Decode MIME-encoded email headers
- `safe_extract_header()`: Extract and decode headers with fallback

#### HTML Utils
- `strip_html()`: Convert HTML to plain text
- `text_to_html()`: Convert plain text to HTML with link detection
- `convert_urls_to_links()`: Convert URLs in text to clickable links

#### Body Extractor
- `extract_body_content()`: Extract body content from email message
- `get_best_body_content()`: Select best body format from preprocessed email
- `has_attachments()`: Check if an email has attachments

## Error Handling

The module provides robust error handling with the `EmailParsingError` exception class and detailed logging. All critical functions include try/except blocks to prevent failures from propagating.

## Performance Considerations

- The module is optimized to work with preprocessed email data when available
- Memory management is implemented to prevent issues with large attachments
- Header decoding uses progressive fallback mechanisms for robustness

## Dependencies

- Python's standard `email` package
- Standard library modules: `re`, `base64`, `quopri`, `html`
- Core Python datetime and typing modules

## Integration Points

This module is designed to work with:
- Gmail API email formats
- Standard MIME email messages
- Preprocessed email data from email clients

## Maintainers

For questions or issues, contact the email processing team. 