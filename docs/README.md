# Beacon Documentation

This directory contains comprehensive documentation for the Beacon email processing application, designed to help users, developers, and recruiters understand the application's capabilities and architecture.

## Core Documentation

| Document | Description |
|----------|-------------|
| [**Architecture Guide**](ARCHITECTURE.md) | Overview of the system design, components, and code organization |
| [**Technical Features**](TECHNICAL_FEATURES.md) | Detailed explanation of key technical features and implementation highlights |
| [**Email Processing Pipeline**](email_processing.md) | In-depth explanation of the email processing pipeline |
| [**Memory Management**](memory_management.md) | Strategies implemented for optimizing memory usage |

## API Documentation

The API documentation is automatically generated from docstrings using Sphinx:

```bash
cd sphinx
make html
```

After building, access the HTML documentation at [sphinx/build/html/index.html](sphinx/build/html/index.html).

## For Developers

Each module within the application includes its own README.md file with specific implementation details, usage examples, and design choices. These module-level READMEs follow a standardized format to ensure consistency across the codebase.

## Key Technical Highlights

Beacon demonstrates several advanced software engineering practices:

1. **AI Integration**: Uses both traditional NLP (spaCy) and LLMs (OpenAI) for email analysis
2. **Memory Optimization**: Implements subprocess isolation for memory-intensive operations
3. **Modular Architecture**: Cleanly separates concerns with a well-organized module structure
4. **Error Handling**: Implements comprehensive error handling and graceful degradation
5. **Documentation**: Features extensive documentation at multiple levels (application, module, function)

## Repository Organization

```
beacon/
├── app/                  # Main application package
│   ├── email/            # Email processing modules
│   │   ├── analyzers/    # Content and semantic analysis
│   │   ├── clients/      # Email service clients (Gmail, IMAP)
│   │   ├── models/       # Email data models
│   │   └── pipeline/     # Processing pipeline
│   ├── routes/           # Flask routes and views
│   ├── services/         # Application services
│   ├── models/           # Database models
│   ├── utils/            # Utility functions
│   └── ...
├── docs/                 # Documentation (you are here)
├── tests/                # Test suite
└── scripts/              # Utility scripts
```

## Future Plans

The application roadmap includes:
- Enhanced AI capabilities for better email categorization
- Implementation of a plugin system for custom email processors
- Expansion of supported email providers beyond Gmail and IMAP

## Contributing

Contributions to both code and documentation are welcome. Please see [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.
