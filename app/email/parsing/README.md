# Email Parsing Module

The Email Parsing module extracts structured data from raw email content, converting complex email formats into usable metadata.

## Overview

This module handles the parsing and extraction of information from raw email data. It converts complex, multi-part email formats into structured metadata objects that can be easily processed by other components. The parser handles various email components including headers, body text (in different formats), attachments, and threading information.

## Directory Structure

```
parsing/
├── __init__.py           # Package exports
├── parser.py             # Main parser implementation
├── utils/                # Parsing utilities
│   ├── __init__.py       # Utility exports
│   ├── body_extractor.py # Email body extraction
│   ├── date_utils.py     # Date parsing utilities
│   ├── header_utils.py   # Header parsing functions
│   └── html_utils.py     # HTML processing utilities
└── README.md             # This documentation
```

## Components

### Email Parser
The main parser class that extracts structured metadata from raw email content. Handles conversion from raw email data to a standardized EmailMetadata object with normalized fields.

### Parsing Utilities
Specialized utilities for handling specific aspects of email parsing, including body text extraction, date normalization, header processing, and HTML content handling.

## Usage Examples

```python
# Parsing a raw email
from app.email.parsing.parser import EmailParser

parser = EmailParser()
raw_email = {
    "id": "email_123",
    "raw_message": b"MIME-Version: 1.0\r\nFrom: sender@example.com\r\n..."
}
email_metadata = parser.extract_metadata(raw_email)

print(f"From: {email_metadata.sender}")
print(f"Subject: {email_metadata.subject}")
print(f"Date: {email_metadata.date}")
print(f"Body: {email_metadata.body[:100]}...")

# Using specific utilities
from app.email.parsing.utils.html_utils import extract_text_from_html

html_content = "<html><body><p>Hello world!</p></body></html>"
plain_text = extract_text_from_html(html_content)
print(plain_text)  # "Hello world!"
```

## Internal Design

The parsing module follows these design principles:
- Robust handling of various email formats
- Proper decoding of character sets and encodings
- Graceful fallback for malformed emails
- Consistent extraction of essential metadata
- Efficient processing of large emails

## Dependencies

Internal:
- `app.utils.logging_setup`: For logging parsing events

External:
- `email`: Python's standard email parsing library
- `dateutil.parser`: For flexible date parsing
- `beautifulsoup4`: For HTML parsing and cleaning
- `chardet`: For character encoding detection

## Additional Resources

- [Email MIME Structure Reference](https://tools.ietf.org/html/rfc2045)
- [Python email Package Documentation](https://docs.python.org/3/library/email.html)
- [BeautifulSoup Documentation](https://www.crummy.com/software/BeautifulSoup/bs4/doc/)
- [API Reference](../../../docs/sphinx/build/html/api.html) 