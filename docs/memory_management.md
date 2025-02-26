# Memory Management in Beacon

This document provides information about the memory management strategies implemented in the Beacon application, particularly for handling the high memory usage associated with SpaCy NLP processing.

## Memory Usage Challenges

The application faces several memory-related challenges:

1. **SpaCy Model Size**: SpaCy language models can consume significant memory (~300MB+), especially when processing multiple emails.
2. **Python Memory Allocation**: Python's memory allocator rarely returns memory to the operating system, leading to high RSS (Resident Set Size) values.
3. **Memory Fragmentation**: Over time, memory can become fragmented, making it difficult for the process to reuse freed memory.
4. **Limited Server Resources**: Production environments may have constrained memory resources (e.g., 2GB limit).

## Implementation Solutions

### 1. Subprocess NLP Processing

The most effective solution implemented is processing NLP tasks in separate, short-lived subprocesses:

- **How it works**: Each batch of texts is sent to a new Python process that loads SpaCy, processes the texts, and terminates.
- **Advantages**: 
  - Memory is completely released when the process exits
  - Main application memory remains stable regardless of NLP workload
  - Protects against memory leaks in SpaCy or third-party libraries
- **Files involved**:
  - `app/email/analyzers/subprocess_nlp.py`: Manages the subprocess communication
  - `app/email/analyzers/process_nlp.py`: Self-contained script that runs in subprocesses
  - `app/email/analyzers/content_analyzer_subprocess.py`: Drop-in replacement for ContentAnalyzer

### 2. SpaCy Optimizations

Even within subprocesses, we've optimized SpaCy usage:

- Disabled unused components like vectors, text categorization, and transformers
- Limited text size to 10,000 characters
- Established explicit cleanup procedures for SpaCy Doc objects

### 3. Memory Monitoring

The application includes comprehensive memory monitoring:

- **Logging**: Memory usage is logged at critical points in the processing pipeline
- **Profiling**: Memory profiling middleware tracks usage across HTTP requests
- **Cleanup**: Garbage collection is forced at strategic points

## Switching Between Approaches

The application supports two NLP processing approaches:

### In-Process Approach (Original)

```python
# In app/__init__.py
text_analyzer = ContentAnalyzer(nlp_model)
```

### Subprocess Approach (Memory-Optimized)

```python
# In app/__init__.py
text_analyzer = ContentAnalyzerSubprocess()  # No need to pass nlp_model
```

## Troubleshooting Memory Issues

If you continue to experience memory issues:

1. **Reduce batch sizes**: Adjust the batch size in ContentAnalyzerSubprocess (default: 5)
2. **Use a smaller SpaCy model**: Switch to 'en_core_web_sm' instead of larger models
3. **Implement a memory watchdog**: Add code to restart workers if memory exceeds thresholds
4. **Increase server resources**: If available, upgrade server memory

## Monitoring Memory Usage

To monitor memory usage in production:

```bash
# Display real-time memory usage
watch -n 1 'ps -o pid,rss,command | grep python'

# Check system memory status
free -m
```

For more detailed analysis, consider using tools like `memray` or `memory_profiler` in development. 