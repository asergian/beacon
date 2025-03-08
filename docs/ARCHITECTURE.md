# Beacon Application Architecture

## Overview

Beacon is a Flask-based email processing and analysis application. The application uses AI to analyze emails, detect priorities, and provide summaries to help users manage their inboxes more efficiently.

This document describes the architecture of the application, focusing on its modular structure and code organization.

## Directory Structure

```
beacon/
├── app/                    # Main application package
│   ├── __init__.py         # Application factory
│   ├── config.py           # Configuration settings
│   ├── models/             # Database models package
│   │   ├── __init__.py     # Exports models
│   │   ├── user.py         # User-related models
│   │   └── email.py        # Email-related models
│   ├── routes/             # Route definitions package
│   │   ├── __init__.py     # Route initialization
│   │   ├── static_pages.py # Static page routes
│   │   ├── test_routes.py  # Test routes
│   │   ├── user_routes.py  # User management routes
│   │   └── email/          # Email routes package
│   │       ├── __init__.py # Exports email blueprints
│   │       ├── views.py    # Main email view routes
│   │       ├── email_view.py # Email viewing routes
│   │       ├── analysis.py # Email analysis routes
│   │       ├── settings.py # Email settings routes
│   │       └── api.py      # General email API routes
│   ├── auth/               # Authentication package
│   │   ├── __init__.py     # Exports auth components
│   │   ├── decorators.py   # Auth decorators
│   │   └── routes.py       # Auth routes
│   ├── email/              # Email processing package
│   │   ├── core/           # Core email functionality
│   │   ├── models/         # Email domain models
│   │   ├── analyzers/      # Email analysis modules
│   │   ├── pipeline/       # Email processing pipeline
│   │   ├── storage/        # Email storage and caching
│   │   └── utils/          # Email utility functions
│   ├── templates/          # Jinja2 templates
│   ├── static/             # Static assets
│   └── utils/              # Utility functions
├── migrations/             # Database migrations
├── tests/                  # Test suite
├── .env                    # Environment variables
├── app.py                  # Application entry point
├── requirements.txt        # Package dependencies
└── README.md              # Project documentation
```

## Core Components

### Application Factory

The application follows the factory pattern, with the main app factory in `app/__init__.py`. This allows for flexible configuration and better testability.

```python
def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    
    # Register routes
    init_routes(app)
    
    return app
```

### Database Models

Models are organized in the `app/models/` package by domain:

1. **User Models (`user.py`):**
   - `User`: User account information
   - `UserSetting`: User preferences and settings
   - `UserActivity`: User activity tracking

2. **Email Models (`email.py`):**
   - `EmailCache`: Email caching for performance
   - `EmailAnalysis`: Email analysis results storage

### Routes

Routes are organized in the `app/routes/` package, with email routes further modularized in the `app/routes/email/` package:

1. **Email Routes:**
   - `views.py`: Main email UI routes
   - `email_view.py`: Email viewing and management
   - `analysis.py`: Email analysis functionality
   - `settings.py`: Email settings
   - `api.py`: General email API endpoints

2. **Other Routes:**
   - `user_routes.py`: User management
   - `static_pages.py`: Static pages
   - `test_routes.py`: Testing endpoints

### Email Processing

Email processing is handled by the `app/email/` package, which is organized into submodules:

1. **Core (`core/`):**
   - Email connection and client implementation
   - Email processing orchestration
   - Email parsing and extraction

2. **Models (`models/`):**
   - Email domain models
   - Analysis command model

3. **Analyzers (`analyzers/`):**
   - Content analyzers for extracting meaning
   - Semantic analyzers using AI
   - Priority scoring

4. **Pipeline (`pipeline/`):**
   - Processing pipeline definition
   - Pipeline stages and processors

5. **Storage (`storage/`):**
   - Email caching mechanisms
   - Redis integration for caching

## Design Patterns

The application uses several design patterns:

1. **Factory Pattern:**
   - Application factory for flexible app creation

2. **Repository Pattern:**
   - Model classes with static methods for data access

3. **Command Pattern:**
   - Analysis commands encapsulate processing requests

4. **Blueprint Pattern:**
   - Flask blueprints for route organization

5. **Pipeline Pattern:**
   - Email processing stages in a pipeline

## Modularity

The codebase is designed to be modular, with clear separation of concerns:

1. **Independent Modules:**
   - Email processing functionality can be extracted as a standalone package
   - User management is independent of email functionality

2. **Interface-Based Design:**
   - Clear interfaces between components
   - Dependencies are injected via Flask application context

3. **Reusable Components:**
   - Email analyzers can be reused in other contexts
   - User settings framework is generalized

## Future Improvements

Potential areas for further modularization:

1. **Email Module as Package:**
   - Extract email processing into a separate Python package
   - Create a formal API for the email processing functionality

2. **Microservice Architecture:**
   - Split email analysis into a separate microservice
   - Use message queues for asynchronous processing

3. **Plugin System:**
   - Implement a plugin system for email analyzers
   - Allow custom analyzers to be added dynamically

## Coding Standards

The codebase follows these standards:

1. **Documentation:**
   - Docstrings for all modules, classes, and functions
   - Type hints for function parameters and return values

2. **Code Style:**
   - PEP 8 compliance
   - Maximum line length of 80 characters

3. **Testing:**
   - Unit tests for all components
   - Integration tests for key workflows

4. **Error Handling:**
   - Consistent error handling patterns
   - Proper logging of errors and exceptions 