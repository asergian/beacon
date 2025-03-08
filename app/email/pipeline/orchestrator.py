"""Email processing pipeline module.

This module provides the pipeline for processing and analyzing emails,
combining various components like email fetching, parsing, and analysis.

The pipeline uses two time-based parameters:
- days_back: Number of days to fetch emails for (1 = today, 2 = today and yesterday, etc.)
- cache_duration_days: Number of days to keep emails in cache (1 = last 24 hours, etc.)

Note: This module has been refactored to use helper functions from the helpers/ directory.
The implementation of many helper methods has been moved to dedicated modules:
- context.py: User context setup and validation
- fetching.py: Email and cache fetching and filtering
- processing.py: Email processing and batch handling
- stats.py: Statistics and activity logging
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, AsyncGenerator, Tuple, Set
from datetime import datetime, timezone
import logging
from flask import session
import time
from datetime import tzinfo
import gc
from zoneinfo import ZoneInfo

from ..processing.processor import EmailProcessor
from ..models.processed_email import ProcessedEmail
from ..storage.base_cache import EmailCache
from ..clients.gmail.client import GmailClient
from ..parsing.parser import EmailParser, EmailMetadata
from app.models.activity import log_activity
from ..models.analysis_command import AnalysisCommand
from app.models.user import User
from app.utils.memory_profiling import log_memory_usage

# Import helper modules
from .helpers.context import setup_user_context
from .helpers.fetching import (
    send_cache_status, fetch_cached_emails, 
    fetch_emails_from_gmail, filter_cached_emails
)
from .helpers.processing import (
    process_without_ai, process_in_batches, 
    process_all_at_once, apply_filters
)
from .helpers.stats import generate_final_stats, log_activity as log_pipeline_activity

@dataclass
class AnalysisResult:
    """Represents the result of email analysis"""
    emails: List[ProcessedEmail]
    stats: Dict[str, any]  # processing stats
    errors: List[Dict]

class EmailPipeline:
    """Unified pipeline for email processing and analysis"""
    
    def __init__(
        self,
        connection: GmailClient,
        parser: EmailParser,
        processor: EmailProcessor,
        cache: Optional[EmailCache] = None,
    ):
        self.connection = connection
        self.parser = parser
        self.processor = processor
        self.cache = cache
        self.logger = logging.getLogger(__name__)

    async def get_analyzed_emails(self, command: AnalysisCommand) -> AnalysisResult:
        """Main method to get and analyze emails with caching and metrics
        
        Args:
            command: AnalysisCommand containing:
                - days_back: Number of days to fetch (1 = today, 2 = today and yesterday)
                - cache_duration_days: Number of days to keep in cache
                - other filtering parameters
            
        Returns:
            AnalysisResult object containing processed emails, stats, and any errors
            
        Raises:
            ValueError: If user context is invalid
            Exception: If email processing fails
        """
        log_memory_usage(self.logger, "Pipeline Start")
        errors = []
        stats = {
            "emails_fetched": 0,
            "new_emails": 0,
            "successfully_parsed": 0,
            "successfully_analyzed": 0,
            "failed_parsing": 0,
            "failed_analysis": 0,
            "cache_errors": 0,
            "errors": 0
        }

        try:
            # Set up user context and validate using context helper
            user_id, user_email, timezone_obj, ai_enabled, cache_duration = setup_user_context(command, self.logger)
            
            # Fetch cached emails using fetching helper
            cached_emails, cached_ids = await fetch_cached_emails(
                command, user_email, timezone_obj, stats, self.cache, self.logger
            )
            
            # Fetch emails from Gmail using fetching helper
            raw_emails, gmail_email_ids, new_raw_emails = await fetch_emails_from_gmail(
                command, user_email, timezone_obj, cached_ids, cached_emails, 
                stats, self.connection, self.logger
            )
            
            # Filter cached emails using fetching helper
            cached_emails, cached_ids = filter_cached_emails(
                cached_emails, gmail_email_ids, stats, self.cache, user_email, self.logger
            )
            
            # Only process new emails if there are any
            analyzed_emails = []
            if new_raw_emails:
                parsed_emails = [email for email in [self.parser.extract_metadata(email) for email in new_raw_emails] if email is not None]
                
                # Process emails based on AI settings
                if not ai_enabled:
                    # Use the processing helper for non-AI processing
                    async for result in process_without_ai(
                        parsed_emails, user_email, cache_duration, stats, self.cache, self.logger
                    ):
                        if result.get('type') == 'emails':
                            analyzed_emails = result.get('data', [])
                            
                    stats.update({
                        "successfully_analyzed": len(analyzed_emails),
                        "successfully_parsed": len(parsed_emails),
                        "failed_parsing": len(new_raw_emails) - len(parsed_emails),
                        "failed_analysis": 0
                    })
                else:
                    # Process emails with AI based on batch configuration
                    if command.batch_size:
                        # Use the batch processing helper
                        log_memory_usage(self.logger, "Before Starting Batch Processing")
                        self.logger.info(f"Starting batch processing with {len(parsed_emails)} emails")
                        
                        async for result in process_in_batches(
                            parsed_emails, command, user_id, user_email, ai_enabled,
                            cache_duration, stats, self.processor, self.cache, self.logger
                        ):
                            if result.get('type') == 'emails':
                                analyzed_emails = result.get('data', [])
                    else:
                        # Use all-at-once processing helper
                        async for result in process_all_at_once(
                            parsed_emails, user_id, user_email, ai_enabled,
                            cache_duration, stats, self.processor, self.cache, self.logger
                        ):
                            if result.get('type') == 'emails':
                                analyzed_emails = result.get('data', [])
            
            # Combine cached and newly analyzed emails
            all_emails = cached_emails + analyzed_emails
            
            # Apply filters to all emails using processing helper
            filtered_emails = apply_filters(all_emails, command, self.logger)

            # Log processing summary
            success_rate_parse = f"{stats['successfully_parsed']}/{stats['new_emails']}" if stats['new_emails'] > 0 else "N/A"
            success_rate_analyze = f"{stats['successfully_analyzed']}/{stats['successfully_parsed']}" if stats['successfully_parsed'] > 0 else "N/A"
            
            self.logger.info(
                "Pipeline Complete\n"
                "Email Processing Summary:\n"
                f"    Total Processed: {stats['emails_fetched']} emails\n"
                f"    From Cache: {len(cached_emails)} emails\n"
                f"    New Emails: {stats['new_emails']} emails\n"
                f"    Success Rates:\n"
                f"        Parsing: {success_rate_parse}\n"
                f"        Analysis: {success_rate_analyze}\n"
                f"    After Filtering: {len(filtered_emails)} emails"
            )

            if stats['failed_parsing'] > 0 or stats['failed_analysis'] > 0:
                self.logger.warning(
                    "Processing Failures:\n"
                    f"    Failed Parsing: {stats['failed_parsing']} emails\n"
                    f"    Failed Analysis: {stats['failed_analysis']} emails"
                )

            # Log activity using stats helper
            log_pipeline_activity(user_id, filtered_emails, stats, command, self.logger)
            
            # Make sure to release memory at the end of pipeline execution
            log_memory_usage(self.logger, "Pipeline Complete")
            
            # Create a copy of the filtered emails list to avoid memory leaks
            # from keeping references to the larger original objects
            filtered_emails_copy = []
            for email in filtered_emails:
                # Create a new dictionary with only essential fields
                email_dict = email.dict()
                filtered_emails_copy.append(ProcessedEmail(**email_dict))
            
            # Clear original references
            filtered_emails = None
            all_emails = None
            analyzed_emails = None
            cached_emails = None
            raw_emails = None
            new_raw_emails = None
            
            # Force garbage collection
            gc.collect()
            gc.collect()
            
            log_memory_usage(self.logger, "Pipeline After Final Cleanup")
            
            return AnalysisResult(
                emails=filtered_emails_copy,
                stats=stats,
                errors=errors
            )
        finally:
            # Even though the route will handle disconnection,
            # we ensure resources are cleaned up here as well
            try:
                await self.connection.disconnect()
                log_memory_usage(self.logger, "Pipeline After Disconnection")
            except Exception as e:
                self.logger.error(f"Error during pipeline disconnect: {e}")

    async def get_analyzed_emails_stream(self, command: AnalysisCommand) -> AsyncGenerator[dict, None]:
        """Streaming version of get_analyzed_emails that yields results as they are processed"""
        errors = []
        stats = {
            "emails_fetched": 0,
            "new_emails": 0,
            "successfully_parsed": 0,
            "successfully_analyzed": 0,
            "failed_parsing": 0,
            "failed_analysis": 0,
            "cached": 0,
            "batches": 0,
            "processed": 0
        }

        try:
            log_memory_usage(self.logger, "Streaming Pipeline Start")
            
            # Set up user context and validate using context helper
            user_id, user_email, timezone_obj, ai_enabled, cache_duration = setup_user_context(command, self.logger)
            
            # Send cache status update
            async for update in send_cache_status():
                yield update
            
            # Fetch cached emails using fetching helper
            cached_emails, cached_ids = await fetch_cached_emails(
                command, user_email, timezone_obj, stats, self.cache, self.logger
            )
            
            # Send the cached emails to the client immediately if available
            if cached_emails:
                yield {
                    'type': 'cached',
                    'data': {'emails': [email.dict() for email in cached_emails]}
                }
                yield {
                    'type': 'status',
                    'data': {'message': f'Loading {len(cached_emails)} cached emails'}
                }
            
            # Fetch emails from Gmail using fetching helper
            raw_emails, gmail_email_ids, new_raw_emails = await fetch_emails_from_gmail(
                command, user_email, timezone_obj, cached_ids, cached_emails, 
                stats, self.connection, self.logger
            )
            
            # Get the original count of cached emails before filtering
            original_cached_count = len(cached_emails)
            
            # Filter cached emails using fetching helper
            cached_emails, cached_ids = filter_cached_emails(
                cached_emails, gmail_email_ids, stats, self.cache, user_email, self.logger
            )
            
            # If any emails were filtered out, resend the updated cached emails
            if original_cached_count != len(cached_emails):
                yield {
                    'type': 'cached',
                    'data': {
                        'emails': [email.dict() for email in cached_emails],
                        'replace_previous': True,  # Indicate this should replace previous cached emails
                        'filtered_count': original_cached_count - len(cached_emails)
                    }
                }
                yield {
                    'type': 'status',
                    'data': {'message': f'Removed {original_cached_count - len(cached_emails)} emails that were deleted from Gmail'}
                }
            
            # If no new emails, just return with updated stats
            if not new_raw_emails and cached_emails:
                yield {
                    'type': 'status',
                    'data': {'message': 'Using cached emails only'}
                }
                yield {
                    'type': 'initial_stats',
                    'data': {
                        'total_fetched': stats['emails_fetched'],
                        'new_emails': 0,
                        'cached': len(cached_ids)
                    }
                }
                return
            
            # Send initial stats
            yield {
                'type': 'initial_stats',
                'data': {
                    'total_fetched': stats['emails_fetched'],
                    'new_emails': stats['new_emails'],
                    'cached': len(cached_ids)
                }
            }
            
            # Status updates
            yield {
                'type': 'status',
                'data': {'message': 'Starting email analysis...'}
            }
            yield {
                'type': 'status',
                'data': {'message': f'Found {len(new_raw_emails)} new emails to process'}
            }
            
            # Parse emails
            parsed_emails = [email for email in [self.parser.extract_metadata(email) for email in new_raw_emails] if email is not None]
            
            # Process emails based on AI settings
            if not ai_enabled:
                # Process without AI using helper
                async for result in process_without_ai(
                    parsed_emails, user_email, cache_duration, stats, self.cache, self.logger
                ):
                    yield result
            else:
                # Process with AI using helpers
                if command.batch_size:
                    # Process in batches
                    async for result in process_in_batches(
                        parsed_emails, command, user_id, user_email, ai_enabled,
                        cache_duration, stats, self.processor, self.cache, self.logger
                    ):
                        yield result
                else:
                    # Process all at once
                    async for result in process_all_at_once(
                        parsed_emails, user_id, user_email, ai_enabled,
                        cache_duration, stats, self.processor, self.cache, self.logger
                    ):
                        yield result
            
            # Update final parsing stats
            stats.update({
                "successfully_parsed": len(parsed_emails),
                "failed_parsing": len(new_raw_emails) - len(parsed_emails)
            })
            
            # Yield final pipeline stats using helper
            async for result in generate_final_stats(stats, self.logger):
                yield result

        except Exception as e:
            self.logger.error(f"Pipeline error: {e}")
            yield {
                'type': 'error',
                'data': {'message': str(e)}
            }
            raise
        
        finally:
            # Clean up resources
            try:
                await self.connection.disconnect()
                log_memory_usage(self.logger, "Streaming Pipeline After Disconnection")
            except Exception as e:
                self.logger.error(f"Error during streaming pipeline disconnect: {e}")

def create_pipeline(
    connection: GmailClient,
    parser: EmailParser,
    processor: EmailProcessor,
    cache: Optional[EmailCache] = None
) -> EmailPipeline:
    """Create pipeline instance with pre-initialized components.
    
    Args:
        connection: Initialized Gmail client
        parser: Initialized email parser
        processor: Initialized email processor
        cache: Optional initialized email cache
        
    Returns:
        EmailPipeline: Configured pipeline instance
    """
    return EmailPipeline(
        connection=connection,
        parser=parser,
        processor=processor,
        cache=cache
    ) 