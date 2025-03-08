"""Email processing and filtering utilities.

This module provides functions for processing and filtering emails,
including AI analysis, batch processing, and criteria-based filtering.
"""

import logging
import gc
from typing import List, Dict, Set, Tuple, Optional, AsyncGenerator, Any
from datetime import timezone

from app.email.models.processed_email import ProcessedEmail
from app.email.storage.base_cache import EmailCache
from app.email.pipeline.orchestrator import AnalysisCommand
from app.email.parsing.parser import EmailMetadata
from app.email.processing.processor import EmailProcessor
from app.utils.memory_profiling import log_memory_usage


async def process_without_ai(
    parsed_emails: List[EmailMetadata],
    user_email: str,
    cache_duration: int,
    stats: Dict,
    cache: Optional[EmailCache] = None,
    logger: Optional[logging.Logger] = None
) -> AsyncGenerator[Dict, None]:
    """Process emails without AI features.
    
    Creates basic processed emails with minimal metadata and
    without AI-powered analysis.
    
    Args:
        parsed_emails: List of parsed email metadata
        user_email: The user's email address
        cache_duration: Cache duration in days
        stats: Dictionary to track stats
        cache: Optional email cache implementation
        logger: Optional logger for logging events
        
    Yields:
        Status updates and processed emails
    """
    logger = logger or logging.getLogger(__name__)
    logger.info("AI features disabled, skipping batch analysis")
    basic_emails = []
    
    for parsed_email in parsed_emails:
        email_date = parsed_email.date
        if email_date.tzinfo is None:
            email_date = email_date.replace(tzinfo=timezone.utc)
        else:
            email_date = email_date.astimezone(timezone.utc)
            
        processed_email = ProcessedEmail(
            id=parsed_email.id,
            subject=parsed_email.subject,
            sender=parsed_email.sender,
            body=parsed_email.body,
            date=email_date,
            urgency=False,
            entities={},
            key_phrases=[],
            sentence_count=0,
            sentiment_indicators={},
            structural_elements={},
            needs_action=False,
            category='Informational',
            action_items=[],
            summary='No summary available',
            priority=30,
            priority_level='LOW'
        )
        basic_emails.append(processed_email)
        
        # Cache each email without redundant logging
        if cache:
            await cache.store_many([processed_email], user_email, ttl_days=cache_duration)
    
    # Yield all basic emails at once since no real processing needed
    if basic_emails:
        stats["batches"] = 1
        yield {
            'type': 'batch',
            'data': {'emails': [email.dict() for email in basic_emails]}
        }
        
    stats.update({
        "successfully_analyzed": len(basic_emails),
        "successfully_parsed": len(parsed_emails),
        "failed_parsing": len(parsed_emails) - len(basic_emails),
        "failed_analysis": 0
    })


async def process_in_batches(
    parsed_emails: List[EmailMetadata],
    command: AnalysisCommand,
    user_id: int,
    user_email: str,
    ai_enabled: bool,
    cache_duration: int,
    stats: Dict,
    processor: Optional[EmailProcessor] = None,
    cache: Optional[EmailCache] = None,
    logger: Optional[logging.Logger] = None
) -> AsyncGenerator[Dict, None]:
    """Process emails in batches with AI features.
    
    Args:
        parsed_emails: List of parsed email metadata
        command: The analysis command with parameters
        user_id: The user's ID
        user_email: The user's email address
        ai_enabled: Whether AI features are enabled
        cache_duration: Cache duration in days
        stats: Dictionary to track stats
        processor: Email processor implementation
        cache: Optional email cache implementation
        logger: Optional logger for logging events
        
    Yields:
        Status updates and batches of processed emails
        
    Raises:
        RuntimeError: If processor is None
    """
    logger = logger or logging.getLogger(__name__)
    
    if processor is None:
        raise RuntimeError("Email processor is required")
    
    batch_count = (len(parsed_emails) + command.batch_size - 1) // command.batch_size
    stats["batches"] = batch_count
    
    # Keep only this critical memory log point
    log_memory_usage(logger, "Before Starting Batch Processing")
    
    logger.info(f"Starting Batch Processing: {len(parsed_emails)} emails, batch size {command.batch_size}, total batches {batch_count}\n")
    logger.debug(f"Starting Batch Processing\n"
        f"    Total Emails to Process: {len(parsed_emails)}\n"
        f"    Batch Size: {command.batch_size}\n"
        f"    Total Batches: {batch_count}"
    )
    
    for i in range(0, len(parsed_emails), command.batch_size):
        logger.info(f"===========Batch {i // command.batch_size + 1} of {batch_count}===========")
        batch = parsed_emails[i:i + command.batch_size]
        batch_results = await processor.analyze_parsed_emails(batch, user_id=user_id, ai_enabled=ai_enabled)
        
        # Cache batch results
        if cache and batch_results:
            await cache.store_many(batch_results, user_email, ttl_days=cache_duration)
        
        # Process and yield batch results
        async for result in process_batch_results(batch_results, i, command.batch_size, len(parsed_emails), stats):
            yield result


async def process_batch_results(
    batch_results: List[ProcessedEmail],
    batch_start_index: int,
    batch_size: int,
    total_emails: int,
    stats: Dict,
    logger: Optional[logging.Logger] = None
) -> AsyncGenerator[Dict, None]:
    """Process and yield batch results.
    
    Args:
        batch_results: Results from processing a batch
        batch_start_index: Start index of this batch
        batch_size: Size of the batch
        total_emails: Total number of emails to process
        stats: Dictionary to track stats
        logger: Optional logger for logging events
        
    Yields:
        Batch results and status updates
    """
    logger = logger or logging.getLogger(__name__)
    
    # Clear out large memory objects we don't need anymore
    emails_to_process = []
    
    # Create lightweight copies of the email objects
    for email in batch_results:
        # Create a new dictionary with only essential fields
        email_dict = email.dict()
        email_copy = ProcessedEmail(**email_dict)
        emails_to_process.append(email_copy)
    
    # Clear original references
    batch_results = None
    
    # Force garbage collection
    gc.collect()
    
    # Track successfully analyzed emails count BEFORE clearing the emails_to_process variable
    analyzed_count = len(emails_to_process) if emails_to_process else 0
    stats["successfully_analyzed"] = stats.get("successfully_analyzed", 0) + analyzed_count
    
    # Stream as a batch instead of individual emails
    if emails_to_process and len(emails_to_process) > 0:
        yield {
            'type': 'batch',
            'data': {
                'emails': [email.dict() for email in emails_to_process]
            }
        }
    
    # Clear batch data
    emails_to_process = None
    
    # Yield batch completion status
    stats["processed"] = batch_start_index + min(batch_size, total_emails - batch_start_index if total_emails else 0)
    yield {
        'type': 'status',
        'data': {
            'message': f'Processed {stats["processed"]}/{stats["new_emails"]} emails',
            'progress': batch_start_index / stats["new_emails"] if stats["new_emails"] > 0 else 1
        }
    }


async def process_all_at_once(
    parsed_emails: List[EmailMetadata],
    user_id: int,
    user_email: str,
    ai_enabled: bool,
    cache_duration: int,
    stats: Dict,
    processor: Optional[EmailProcessor] = None,
    cache: Optional[EmailCache] = None,
    logger: Optional[logging.Logger] = None
) -> AsyncGenerator[Dict, None]:
    """Process all emails at once without batching.
    
    Args:
        parsed_emails: List of parsed email metadata
        user_id: The user's ID
        user_email: The user's email address
        ai_enabled: Whether AI features are enabled
        cache_duration: Cache duration in days
        stats: Dictionary to track stats
        processor: Email processor implementation
        cache: Optional email cache implementation
        logger: Optional logger for logging events
        
    Yields:
        Status updates and processed emails
        
    Raises:
        RuntimeError: If processor is None
    """
    logger = logger or logging.getLogger(__name__)
    
    if processor is None:
        raise RuntimeError("Email processor is required")
    
    # Log memory before processing all emails at once
    log_memory_usage(logger, "Before Processing All Emails")
    
    analyzed_emails = await processor.analyze_parsed_emails(parsed_emails, user_id=user_id, ai_enabled=ai_enabled)
    stats["batches"] = 1
    
    # Log memory after processing all emails
    log_memory_usage(logger, "After Processing All Emails")
    
    # Cache results
    if cache and analyzed_emails:
        stats["processed"] = len(analyzed_emails)  # Track processed count
        await cache.store_many(analyzed_emails, user_email, ttl_days=cache_duration)
    else:
        stats["processed"] = len(analyzed_emails) if analyzed_emails else 0
    
    # Yield all results at once
    if analyzed_emails:
        yield {
            'type': 'batch',
            'data': {'emails': [email.dict() for email in analyzed_emails]}
        }
    
    stats.update({
        "successfully_analyzed": stats.get("processed", 0),  # Use processed count from stats
        "failed_analysis": len(parsed_emails) - stats.get("processed", 0)
    })


def apply_filters(
    emails: List[ProcessedEmail],
    command: AnalysisCommand,
    logger: Optional[logging.Logger] = None
) -> List[ProcessedEmail]:
    """Apply filters to email list.
    
    Filters emails based on priority threshold, categories,
    and other criteria specified in the command.
    
    Args:
        emails: List of processed emails to filter
        command: The analysis command with filter parameters
        logger: Optional logger for logging events
        
    Returns:
        Filtered list of emails
    """
    logger = logger or logging.getLogger(__name__)
    filtered = emails
    
    # Apply priority filter if specified
    if command.priority_threshold:
        filtered = [e for e in filtered if e.priority >= command.priority_threshold]
        
    # Apply category filter if specified
    if command.categories:
        filtered = [e for e in filtered if e.category in command.categories]
        
    return filtered
