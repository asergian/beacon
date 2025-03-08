Module Documentation
====================

This section provides detailed documentation for individual modules within the Beacon application.
Each module has its own README.md file with specific implementation details, usage examples, and design choices.

Email Processing Modules
------------------------

Email Clients
^^^^^^^^^^^^^

.. include:: ../../../app/email/clients/README.md
   :parser: myst_parser.sphinx_

**Submodules:**

.. toctree::
   :maxdepth: 1
   :caption: Client Modules:

   Gmail Client <module_docs/email_clients_gmail>
   IMAP Client <module_docs/email_clients_imap>

Email Analyzers
^^^^^^^^^^^^^^^

.. include:: ../../../app/email/analyzers/README.md
   :parser: myst_parser.sphinx_

**Submodules:**

.. toctree::
   :maxdepth: 1
   :caption: Analyzer Modules:

   Content Analyzer <module_docs/email_analyzers_content>
   Semantic Analyzer <module_docs/email_analyzers_semantic>

Email Pipeline
^^^^^^^^^^^^^^

.. include:: ../../../app/email/pipeline/README.md
   :parser: myst_parser.sphinx_

Core Application Modules
------------------------

Models
^^^^^^

.. include:: ../../../app/models/README.md
   :parser: myst_parser.sphinx_

Routes
^^^^^^

.. include:: ../../../app/routes/README.md
   :parser: myst_parser.sphinx_

Utils
^^^^^

.. include:: ../../../app/utils/README.md
   :parser: myst_parser.sphinx_ 