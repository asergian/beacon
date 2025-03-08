# Gmail Worker Utilities

This package provides utility functions for the Gmail worker module, organized into specialized modules for different types of operations.

## Structure

The utilities package contains the following modules:

### 1. `date_utils.py`
Date and time utility functions, including:
- `calculate_cutoff_time()`: Calculate cutoff time for email filtering based on days_back parameter
- Timezone handling and conversion utilities

### 2. `file_utils.py`
File operation utilities, including:
- `parse_content_from_file()`: Read content from a file path with @ prefix

### 3. `logging_utils.py`
Logging configuration and management utilities, including:
- `get_logger()`: Get a standardized logger instance for consistent logging

### 4. `processing_utils.py`
Email and message processing utilities, including:
- `filter_emails_by_date()`: Filter emails by date using a cutoff time
- `track_message_processing()`: Track message processing for memory management

### 5. `memory_management.py`
Memory optimization and management utilities, including:
- `get_process_memory()`: Get current memory usage of the process
- `log_memory_usage()`: Log current memory usage with a label
- `log_memory_cleanup()`: Force garbage collection and log memory usage
- `track_email_processing()`: Track email processing statistics
- `get_processing_stats()`: Get current email processing statistics
- `cleanup_resources()`: Clean up all resources before exiting the process

## Usage

Import utility functions from their respective modules:

```python
from utils.date_utils import calculate_cutoff_time
from utils.memory_management import log_memory_usage
```

Or import directly from the utils package:

```python
from utils import calculate_cutoff_time, log_memory_usage
```

## Design Principles

1. **Modularity**: Each utility module has a specific responsibility
2. **Efficiency**: Utilities are designed to minimize resource usage
3. **Error Handling**: Comprehensive error handling with detailed logging
4. **Documentation**: Clear docstrings for all functions and modules

## Maintenance

When adding new utility functions:
1. Place them in the appropriate module based on functionality
2. Add proper docstrings with Args/Returns/Raises sections
3. Update the `__init__.py` file to expose the new function
4. Add type hints for parameters and return values 