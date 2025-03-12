.. Beacon documentation master file, created by
   sphinx-quickstart on Sat Mar  8 09:45:21 2025.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to Beacon's documentation!
==================================

Beacon is a Flask-based application that processes and analyzes emails using both NLP and LLM capabilities. This documentation provides detailed information about the system architecture, key features, and API reference.

.. image:: _static/beacon-header-dark.svg
   :alt: Beacon Logo
   :align: center
   :width: 300px

Key Features
------------

* **AI-Powered Email Analysis**: Combines traditional NLP with advanced LLMs for comprehensive email understanding
* **Memory-Efficient Architecture**: Implements subprocess isolation for optimized resource usage
* **Modular Design**: Clean separation of concerns with well-defined interfaces
* **Flexible Email Provider Support**: Works with Gmail API and standard IMAP servers
* **Comprehensive Documentation**: Detailed documentation at application, module, and function levels

.. note::
   API documentation is automatically generated from docstrings in the codebase. For high-level architectural and feature documentation, refer to the Core Documentation section below.

Documentation Structure
-----------------------

- **Architecture**: Overview of the system design and architecture
- **Technical Features**: Highlights of advanced engineering concepts and practices
- **Module Documentation**: Detailed information about individual modules
- **API Reference**: Automatically generated documentation from docstrings
- **Email Processing**: Details of the email processing pipeline
- **Memory Management**: Information about memory optimization techniques
- **Development Guide**: Guidelines for developers contributing to the project

.. toctree::
   :maxdepth: 2
   :caption: Core Documentation:

   introduction
   architecture
   technical_features
   email_processing
   memory_management

.. toctree::
   :maxdepth: 2
   :caption: Module Documentation:

   module_documentation

.. toctree::
   :maxdepth: 2
   :caption: API Reference:

   api

.. toctree::
   :maxdepth: 2
   :caption: Development:

   development

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

