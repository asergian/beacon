Architecture
============

This document provides an overview of the Beacon application's architecture and design principles.

Architectural Overview
----------------------

Beacon follows a modular, layered architecture designed for maintainability, testability, and scalability:

.. code-block::

    ┌───────────────────────────────────────────────────────────────┐
    │                       Presentation Layer                      │
    │  ┌───────────────┐  ┌───────────────┐  ┌───────────────────┐  │
    │  │   Web UI      │  │   API         │  │   CLI Interface   │  │
    │  │  (Flask)      │  │  Endpoints    │  │                   │  │
    │  └───────────────┘  └───────────────┘  └───────────────────┘  │
    └───────────────────────────────────────────────────────────────┘
                                ▲
                                │
                                ▼
    ┌───────────────────────────────────────────────────────────────┐
    │                        Application Layer                      │
    │  ┌───────────────┐  ┌───────────────┐  ┌───────────────────┐  │
    │  │  Controllers  │  │  Application  │  │   Email           │  │
    │  │               │  │   Services    │  │   Pipeline        │  │
    │  └───────────────┘  └───────────────┘  └───────────────────┘  │
    └───────────────────────────────────────────────────────────────┘
                                ▲
                                │
                                ▼
    ┌───────────────────────────────────────────────────────────────┐
    │                        Domain Layer                           │
    │  ┌───────────────┐  ┌───────────────┐  ┌───────────────────┐  │
    │  │   Email       │  │   Analyzers   │  │   Models &        │  │
    │  │   Clients     │  │               │  │   Entities        │  │
    │  └───────────────┘  └───────────────┘  └───────────────────┘  │
    └───────────────────────────────────────────────────────────────┘
                                ▲
                                │
                                ▼
    ┌───────────────────────────────────────────────────────────────┐
    │                     Infrastructure Layer                      │
    │  ┌───────────────┐  ┌───────────────┐  ┌───────────────────┐  │
    │  │  Database     │  │  Email APIs   │  │   AI/LLM          │  │
    │  │  Access       │  │  (Gmail/IMAP) │  │   Services        │  │
    │  └───────────────┘  └───────────────┘  └───────────────────┘  │
    └───────────────────────────────────────────────────────────────┘

Key Components
--------------

Presentation Layer
^^^^^^^^^^^^^^^^^^

The presentation layer handles user interaction through:

* **Web UI**: Flask-based web interface
* **API Endpoints**: RESTful API for programmatic access
* **CLI Interface**: Command-line tools for administration

Application Layer
^^^^^^^^^^^^^^^^^

The application layer contains:

* **Controllers**: Handle requests from the presentation layer
* **Application Services**: Implement business logic
* **Email Pipeline**: Orchestrates the email processing workflow

Domain Layer
^^^^^^^^^^^^

The domain layer encapsulates core business logic:

* **Email Clients**: Interact with email providers
* **Analyzers**: Process email content using NLP and LLM
* **Models & Entities**: Domain objects representing emails, users, etc.

Infrastructure Layer
^^^^^^^^^^^^^^^^^^^^

The infrastructure layer provides technical capabilities:

* **Database Access**: Persistence mechanisms
* **Email APIs**: Integration with Gmail API and IMAP servers
* **AI/LLM Services**: Integration with OpenAI and other AI services

Design Patterns
---------------

The application implements several design patterns:

1. **Factory Pattern**
   
   Used to create client instances for different email providers:

   .. code-block:: python

      # Example of factory pattern
      def create_client(provider_type, **config):
          if provider_type == "gmail":
              return GmailClient(**config)
          elif provider_type == "imap":
              return IMAPClient(**config)
          else:
              raise ValueError(f"Unknown provider type: {provider_type}")

2. **Repository Pattern**
   
   Abstracts data storage operations for domain objects.

3. **Strategy Pattern**
   
   Used in the analyzer components to allow different analysis approaches.

4. **Pipeline Pattern**
   
   Implemented in the email processing pipeline to handle sequential operations.

Technology Stack
----------------

.. list-table::
   :widths: 30 70
   :header-rows: 1

   * - Component
     - Technologies
   * - Backend Framework
     - Flask, Werkzeug
   * - Database
     - SQLAlchemy, SQLite/PostgreSQL
   * - Email Integration
     - Gmail API, imaplib
   * - Natural Language Processing
     - spaCy, NLTK
   * - Artificial Intelligence
     - OpenAI API (GPT models)
   * - Frontend
     - HTML, CSS, JavaScript
   * - Testing
     - pytest, unittest
   * - Documentation
     - Sphinx, reStructuredText, MyST Markdown

Memory Management Architecture
------------------------------

One of the most innovative aspects of Beacon's architecture is its memory management strategy for NLP operations:

.. include:: memory_management.rst
   :start-line: 5
   :end-line: 20

For more detailed information on memory management, see the dedicated :doc:`memory_management` section. 