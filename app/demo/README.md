# Demo Module

The Demo module provides demonstration and sample functionality for the Beacon application.

## Overview

This module contains demonstration features, sample data generators, and testing routes to showcase the application's capabilities. It provides example implementations and simplified workflows that help users understand how to use the application's features.

## Directory Structure

```
demo/
├── __init__.py        # Package exports
├── analysis.py        # Demo email analysis features
├── auth.py            # Authentication demos
├── data.py            # Sample data generation
├── routes.py          # Demo routes and endpoints
└── README.md          # This documentation
```

## Components

### Demo Analysis
Provides sample email analysis functionality with pre-configured settings and example responses. Demonstrates how the email analysis pipeline works with simplified inputs and outputs.

### Demo Authentication
Implements simplified authentication flows for demonstration purposes, allowing easy testing without complex setup. Includes sample login flows and authorization examples.

### Demo Data
Generates realistic sample data for testing and demonstration, including email content, user accounts, and analysis results. Useful for development, testing, and showcases.

### Demo Routes
Exposes endpoints specifically for demonstration purposes, allowing users to interact with and test the application's features through a simplified interface.

## Usage Examples

```python
# Generating sample data
from app.demo.data import generate_sample_emails

sample_emails = generate_sample_emails(count=5)

# Running demo analysis
from app.demo.analysis import analyze_demo_email

result = analyze_demo_email(email_content="Sample email content")
print(f"Analysis Result: {result}")

# Using demo authentication
from app.demo.auth import get_demo_user

demo_user = get_demo_user()
# Log in as the demo user
login_user(demo_user)
```

## Internal Design

The demo module follows these design principles:
- Simplified implementations of core functionality
- Clear examples of proper usage patterns
- Consistent interface with actual application features
- Limited dependencies on external services
- Focus on educational and illustrative value

## Dependencies

Internal:
- `app.email`: For email processing functionality
- `app.auth`: For authentication functionality
- `app.models`: For data models

External:
- `flask`: For route definitions
- `faker`: For generating realistic test data
- `random`: For randomizing demo data

## Additional Resources

- [Flask Documentation](https://flask.palletsprojects.com/)
- [Faker Documentation](https://faker.readthedocs.io/)
- [API Reference](../../docs/sphinx/build/html/api.html)
- [Email Processing Documentation](../../docs/email_processing.md) 