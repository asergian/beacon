# Email Processing Pipeline

This document explains the design of the email processing pipeline in Beacon, particularly focusing on memory optimization through subprocess isolation and data flow between processes.

## Pipeline Architecture

The email processing pipeline consists of these main components:

1. **Gmail Client Subprocess (`gmail_client_subprocess.py`)**: Orchestrates communication with the Gmail API subprocess
2. **Gmail Subprocess (`gmail_subprocess.py`)**: Runs in isolation to fetch and parse emails
3. **Email Parser (`email_parsing.py`)**: Extracts metadata from emails
4. **Analysis Pipeline**: Performs NLP/LLM analysis on email content

## Memory Optimization Strategy

### Problem Statement

Processing emails involves memory-intensive operations:
- Fetching large volumes of raw email data from Gmail API
- Parsing MIME messages and decoding content
- Running NLP and LLM analysis on email content

These operations can lead to memory leaks, fragmentation, and high memory usage over time.

### Solution: Process Isolation

The application uses a subprocess-based approach to isolate memory-intensive operations:

1. **Gmail Subprocess**: Handles Gmail API operations and basic parsing in a separate process
2. **Main Process**: Handles higher-level business logic, persistence, and user interaction

## Data Flow Between Processes

### Gmail Subprocess → Main Process

The Gmail subprocess sends these data structures to the main process:
- Email ID, thread ID, and labels
- Extracted headers (subject, from, to, date)
- Parsed body text and HTML content 
- Parsed date in ISO format
- Attachment status flag (has_attachments)

### Important Design Considerations

#### 1. Raw Message Handling

**Key Point:** Raw messages are now handled exclusively in the subprocess.

- **Raw message data is processed in the subprocess to extract:**
  - Body text (plain text) for NLP analysis
  - HTML content for display in the UI
  - All necessary metadata
  - Attachment information

- **Benefits of this approach:**
  - Significantly reduced memory usage in the main process
  - No redundant encoding/decoding of large raw messages
  - Complete memory isolation of message parsing

#### 2. Metadata Extraction

The `extract_metadata()` function in `EmailParser` class is designed to handle both:
- Pre-parsed emails from the subprocess (preferred path)
- Raw email data (fallback path)

This dual-path design allows for flexibility but introduces some redundancy in the processing flow.

## Current Implementation

1. **Subprocess Processing**:
   - Fetches emails from Gmail API
   - Filters by date
   - Extracts headers and content
   - Parses dates
   - Base64 encodes (but does not compress) raw messages
   - Returns structured data to main process

2. **Main Process**:
   - Receives pre-parsed emails
   - Uses EmailParser to extract metadata (using the pre-parsed data path)
   - Performs additional analysis with NLP/LLM
   - Stores results in database
   - Presents data to user

## Optimization Recommendations

1. **Skip redundant parsing**: If all necessary metadata is extracted in the subprocess, consider bypassing additional parsing in the main process
2. **Ensure raw message integrity**: Never compress or modify raw messages needed for NLP/LLM analysis
3. **Balance memory and processing**: Move more processing to the subprocess to reduce main process memory footprint, but be mindful of subprocess memory usage

## Memory Usage Monitoring

Memory usage is logged at key points in the pipeline:
- Before Gmail subprocess is called
- After JSON deserialization in main process
- After email processing in main process

This allows for identifying memory bottlenecks and optimizing the pipeline accordingly. 