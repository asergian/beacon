# Gmail Worker Package

This package provides a modular implementation of the Gmail worker process for memory-isolated email operations.

## Structure

The package is organized into the following modules:

- `__init__.py`: Package initialization
- `main.py`: Main entry point and CLI interface
- `memory_management.py`: Memory optimization utilities
- `api_client.py`: Gmail API client implementation
- `email_parser.py`: Email parsing and decoding
- `email_fetcher.py`: Email fetching functionality
- `email_sender.py`: Email sending functionality

## Usage

The worker is typically invoked by the `client_subprocess.py` module, but can also be run directly:

```bash
python main.py --credentials @/path/to/creds.json --user_email user@gmail.com --query "after:2023/01/01" --days_back 7
```

## Design Principles

1. **Memory Efficiency**: The worker is designed to minimize memory usage through careful resource management.
2. **Modularity**: Each component has a single responsibility and clear interfaces.
3. **Error Handling**: Comprehensive error handling with detailed logging.
4. **Performance**: Batch processing and concurrent operations for optimal performance.

## Google Coding Standards

This package follows Google coding standards:
- Clear docstrings with Args/Returns/Raises sections
- Type hints for all parameters and return values
- Consistent naming conventions
- Comprehensive error handling
- Modular design with single responsibility principle 