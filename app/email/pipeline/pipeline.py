"""Email processing pipeline module.

This module provides the pipeline for processing and analyzing emails,
combining various components like email fetching, parsing, and analysis.

The pipeline uses two time-based parameters:
- days_back: Number of days to fetch emails for (1 = today, 2 = today and yesterday, etc.)
- cache_duration_days: Number of days to keep emails in cache (1 = last 24 hours, etc.)
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, AsyncGenerator
from datetime import datetime, timezone
import logging
from flask import session
import time
import gc
from zoneinfo import ZoneInfo

from ..core.email_processor import EmailProcessor
from ..models.processed_email import ProcessedEmail
from ..storage.cache import EmailCache
from ..core.gmail_client import GmailClient
from ..core.email_parsing import EmailParser
from app.models.activity import log_activity
from ..models.analysis_command import AnalysisCommand
from app.models.user import User
from app.utils.memory_profiling import log_memory_usage

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
        """
        log_memory_usage(self.logger, "Pipeline Start")
        errors = []
        stats = {
            "emails_fetched": 0,
            "new_emails": 0,
            "successfully_parsed": 0,
            "successfully_analyzed": 0,
            "failed_parsing": 0,
            "failed_analysis": 0
        }

        print("Getting analyzed emails")
        try:
            # First ensure we have user context
            if 'user' not in session:
                raise ValueError("No user found in session")
                
            user_id = int(session['user'].get('id'))
            user_email = session['user'].get('email')
            if not user_email:
                raise ValueError("No user email found in session")

            self.logger.info(f"Starting Email Pipeline: User: {user_email} (ID: {user_id}), Days Back: {command.days_back}, Cache Duration: {command.cache_duration_days} days")    
            self.logger.debug(f"Starting Email Pipeline\n"
                f"    User: {user_email} (ID: {user_id})\n"
                f"    Days Back: {command.days_back}\n"
                f"    Cache Duration: {command.cache_duration_days} days"
            )
            
            # Get user settings
            user = User.query.get(user_id)
            if not user:
                raise ValueError("User not found in database")
                
            # Verify user email matches database
            if user.email != user_email:
                raise ValueError("User email mismatch")
                
            # Get user timezone setting, fall back to PST if not set
            user_timezone = user.get_setting('timezone', 'US/Pacific')
            timezone_obj = timezone.utc
            try:
                # Try to parse the timezone from string (e.g., 'America/New_York')
                timezone_obj = ZoneInfo(user_timezone)
                self.logger.debug(f"Using user timezone: {user_timezone}")
            except (ImportError, Exception) as e:
                self.logger.warning(f"Could not use user timezone ({user_timezone}), falling back to US/Pacific: {e}")
                try:
                    timezone_obj = ZoneInfo('US/Pacific')
                except Exception:
                    timezone_obj = timezone.utc
            
            # Check AI features once at the pipeline level
            ai_enabled = user.get_setting('ai_features.enabled', True)
            if not ai_enabled:
                self.logger.info("AI features disabled for this pipeline run")
            
            # Get cache duration from settings
            cache_duration = user.get_setting('email_preferences.cache_duration_days', 7)
            
            # Ensure cache_duration is an integer
            try:
                cache_duration = int(cache_duration)
            except (ValueError, TypeError):
                self.logger.warning(f"Invalid cache_duration value: {cache_duration}, using default of 7 days")
                cache_duration = 7
            
            # Fetch emails from cache first if enabled
            cached_emails = []
            if self.cache and command.use_cache and cache_duration > 0:
                try:
                    cached_emails = await self.cache.get_recent(
                        cache_duration, 
                        command.days_back,
                        user_email,
                        user_timezone
                    )
                    
                    self.logger.info(f"Retrieved {len(cached_emails)} cached emails")
                    
                except Exception as e:
                    self.logger.error(f"Cache retrieval error: {e}")
                    errors.append({"error": f"Cache retrieval error: {str(e)}", "timestamp": datetime.now()})
                    stats["cache_errors"] += 1
            
            # Now that user context is set up, connect to Gmail with user email
            await self.connection.connect(user_email)
            try:
                # Fetch emails from Gmail
                raw_emails = await self.connection.fetch_emails(
                    days_back=command.days_back,
                    user_email=user_email,
                    user_timezone=user_timezone
                )
                
                stats["emails_fetched"] = len(raw_emails)
                
                # Get the IDs of emails currently in Gmail for filtering out deleted emails from cache
                gmail_email_ids = {email.get('id') for email in raw_emails}
                
                # Filter cached emails to keep only those still in Gmail
                if cached_emails:
                    original_cached_count = len(cached_emails)
                    cached_emails = [email for email in cached_emails if email.id in gmail_email_ids]
                    filtered_out_count = original_cached_count - len(cached_emails)
                    if filtered_out_count > 0:
                        self.logger.info(f"Filtered out {filtered_out_count} cached emails that were deleted from Gmail")
                        stats["deleted_emails_filtered"] = filtered_out_count
                
                # Filter out already cached emails
                new_raw_emails = [email for email in raw_emails if email.get('id') not in [email.id for email in cached_emails]]
                stats["new_emails"] = len(new_raw_emails)
                
                self.logger.info(f"Email Retrieval Complete: {len(cached_emails)} cached, {len(raw_emails)} total, {len(new_raw_emails)} new")
                self.logger.debug(
                    "Email Retrieval Complete\n"
                    f"    From Cache: {len(cached_emails)} emails\n"
                    f"    From Gmail: {len(raw_emails)} emails\n"
                    f"    New Emails: {len(new_raw_emails)} emails"
                )
                
                # Only process new emails if there are any
                analyzed_emails = []
                if new_raw_emails:
                    parsed_emails = [email for email in [self.parser.extract_metadata(email) for email in new_raw_emails] if email is not None]
                    
                    # If AI is disabled, create basic metadata without batch processing
                    if not ai_enabled:
                        self.logger.info("AI features disabled, skipping batch analysis")
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
                            analyzed_emails.append(processed_email)
                            
                        stats.update({
                            "successfully_analyzed": len(analyzed_emails),
                            "successfully_parsed": len(parsed_emails),
                            "failed_parsing": len(new_raw_emails) - len(parsed_emails),
                            "failed_analysis": 0
                        })
                    
                    # Only do batch processing if AI is enabled
                    else:
                        if command.batch_size:
                            analyzed_batch = []
                            batch_count = (len(parsed_emails) + command.batch_size - 1) // command.batch_size
                            
                            # Log memory before starting batch processing
                            log_memory_usage(self.logger, "Before Starting Batch Processing")
                            
                            self.logger.info(f"Starting Batch Processing\n"
                                f"    Total Emails to Process: {len(parsed_emails)}\n"
                                f"    Batch Size: {command.batch_size}\n"
                                f"    Total Batches: {batch_count}"
                            )
                            
                            for i in range(0, len(parsed_emails), command.batch_size):
                                batch = parsed_emails[i:i + command.batch_size]
                                batch_results = await self.processor.analyze_parsed_emails(batch, user_id=user_id, ai_enabled=ai_enabled)
                                analyzed_batch.extend(batch_results)
                                self.logger.info(f"Progress: {i + len(batch_results)} / {len(parsed_emails)} emails processed")
                            analyzed_emails = analyzed_batch
                        else:
                            analyzed_emails = await self.processor.analyze_parsed_emails(parsed_emails, user_id=user_id, ai_enabled=ai_enabled)

                        stats.update({
                            "successfully_analyzed": len(analyzed_emails),
                            "successfully_parsed": len(parsed_emails),
                            "failed_parsing": len(new_raw_emails) - len(parsed_emails),
                            "failed_analysis": len(parsed_emails) - len(analyzed_emails)
                        })

                    # Cache new results if cache available
                    if self.cache and analyzed_emails:
                        try:
                            stats["processed"] = len(analyzed_emails)  # Track processed count
                            await self.cache.store_many(analyzed_emails, user_email, ttl_days=cache_duration)
                        except Exception as e:
                            errors.append({"error": f"Cache storage error: {str(e)}", "timestamp": datetime.now()})
                            stats["cache_errors"] += 1
                            self.logger.error(f"Failed to cache emails: {e}")
                
                # Combine cached and newly analyzed emails
                all_emails = cached_emails + analyzed_emails
                
                # Apply filters to all emails
                filtered_emails = self._apply_filters(all_emails, command)

                # Log final pipeline stats
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

                try:
                    start_time = time.time()
                    log_activity(
                        user_id=user_id,
                        activity_type='email_analysis',
                        description=f"Analyzed {len(filtered_emails)} emails",
                        metadata={
                            'analysis_stats': {
                                'total_fetched': stats.get('emails_fetched', 0),
                                'new_emails': stats.get('new_emails', 0),
                                'cached_emails': len(cached_emails),
                                'successfully_parsed': stats.get('successfully_parsed', 0),
                                'successfully_analyzed': stats.get('successfully_analyzed', 0),
                                'failed_parsing': stats.get('failed_parsing', 0),
                                'failed_analysis': stats.get('failed_analysis', 0),
                                'categories': {
                                    'Work': sum(1 for email in filtered_emails if email.category == 'Work'),
                                    'Personal': sum(1 for email in filtered_emails if email.category == 'Personal'),
                                    'Promotions': sum(1 for email in filtered_emails if email.category == 'Promotions'),
                                    'Informational': sum(1 for email in filtered_emails if email.category == 'Informational')
                                },
                                'priority_levels': {
                                    'HIGH': sum(1 for email in filtered_emails if email.priority_level == 'HIGH'),
                                    'MEDIUM': sum(1 for email in filtered_emails if email.priority_level == 'MEDIUM'),
                                    'LOW': sum(1 for email in filtered_emails if email.priority_level == 'LOW')
                                },
                                'needs_action': sum(1 for email in filtered_emails if email.needs_action),
                                'has_deadline': sum(1 for email in filtered_emails if any(item.get('due_date') for item in email.action_items)),
                                'processing_time': time.time() - start_time
                            },
                            'analysis_params': {
                                'days_back': command.days_back,
                                'cache_duration_days': command.cache_duration_days,
                                'batch_size': command.batch_size,
                                'priority_threshold': command.priority_threshold,
                                'categories': command.categories,
                                'ai_enabled': ai_enabled
                            },
                            'timestamp': datetime.now().isoformat()
                        }
                    )
                except Exception as e:
                    self.logger.error(f"Failed to log pipeline activity: {e}")

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

        except Exception as e:
            errors.append({"error": str(e), "timestamp": datetime.now()})
            stats["errors"] += 1
            raise

    def _apply_filters(self, emails: List[ProcessedEmail], command: AnalysisCommand) -> List[ProcessedEmail]:
        """Apply priority and category filters to email list"""
        filtered = emails
        if command.priority_threshold:
            filtered = [e for e in filtered if e.priority >= command.priority_threshold]
        if command.categories:
            filtered = [e for e in filtered if e.category in command.categories]
        return filtered

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
            # Log memory at start of streaming pipeline
            log_memory_usage(self.logger, "Streaming Pipeline Start")
            
            # First ensure we have user context
            if 'user' not in session:
                raise ValueError("No user found in session")
                
            user_id = int(session['user'].get('id'))
            user_email = session['user'].get('email')
            if not user_email:
                raise ValueError("No user email found in session")
                
            self.logger.info(f"Starting Email Pipeline (Streaming) User: {user_email} (ID: {user_id}), Days Back: {command.days_back}, Cache Duration: {command.cache_duration_days} days")
            self.logger.debug(f"Starting Email Pipeline (Streaming)\n"
                f"    User: {user_email} (ID: {user_id})\n"
                f"    Days Back: {command.days_back}\n"
                f"    Cache Duration: {command.cache_duration_days} days"
            )
            
            # Get user settings
            user = User.query.get(user_id)
            if not user:
                raise ValueError("User not found in database")
                
            # Verify user email matches database
            if user.email != user_email:
                raise ValueError("User email mismatch between session and database")
            
            # Get user timezone setting, fall back to PST if not set
            user_timezone = user.get_setting('timezone', 'US/Pacific')
            timezone_obj = timezone.utc
            try:
                # Try to parse the timezone from string (e.g., 'America/New_York')
                timezone_obj = ZoneInfo(user_timezone)
                self.logger.debug(f"Using user timezone: {user_timezone}")
            except (ImportError, Exception) as e:
                self.logger.warning(f"Could not use user timezone ({user_timezone}), falling back to US/Pacific: {e}")
                try:
                    timezone_obj = ZoneInfo('US/Pacific')
                except Exception:
                    timezone_obj = timezone.utc
            
            # Check AI features once at the pipeline level
            ai_enabled = user.get_setting('ai_features.enabled', True)
            if not ai_enabled:
                self.logger.info("AI features disabled for this pipeline run")
            
            # Get cache duration from settings
            cache_duration = user.get_setting('email_preferences.cache_duration_days', 7)
            
            # Ensure cache_duration is an integer
            try:
                cache_duration = int(cache_duration)
            except (ValueError, TypeError):
                self.logger.warning(f"Invalid cache_duration value: {cache_duration}, using default of 7 days")
                cache_duration = 7
            
            # Set up cache and get cached emails
            cached_ids = set()
            if self.cache:
                # Send status update as dictionary
                yield {
                    'type': 'status',
                    'data': {'message': 'Checking cache...'}
                }
                
                cached_emails = await self.cache.get_recent(command.cache_duration_days, command.days_back, user_email, user_timezone)
                cached_ids = {email.id for email in cached_emails}
                stats["cached"] = len(cached_ids)
                
                # Yield cached emails first if we have any
                if cached_emails:
                    yield {
                        'type': 'cached',
                        'data': {'emails': [email.dict() for email in cached_emails]}
                    }
                    yield {
                        'type': 'status',
                        'data': {'message': f'Loading {len(cached_emails)} cached emails'}
                    }
            
            # Now that user context is set up, connect to Gmail
            await self.connection.connect(user_email)
            try:
                raw_emails = await self.connection.fetch_emails(
                    days_back=command.days_back,
                    user_email=user_email,
                    user_timezone=user_timezone
                )
                stats["emails_fetched"] = len(raw_emails)
                
                # Log memory after Gmail fetch
                log_memory_usage(self.logger, "After Streaming Gmail Fetch")
                
                # Get the IDs of emails currently in Gmail for filtering out deleted emails from cache
                gmail_email_ids = {email.get('id') for email in raw_emails}
                
                # Filter cached emails to keep only those still in Gmail
                if len(cached_ids) > 0:
                    original_cached_count = len(cached_emails)
                    cached_emails = [email for email in cached_emails if email.id in gmail_email_ids]
                    filtered_out_count = original_cached_count - len(cached_emails)
                    cached_ids = {email.id for email in cached_emails}  # Update cached_ids
                    
                    if filtered_out_count > 0:
                        self.logger.info(f"Filtered out {filtered_out_count} cached emails that were deleted from Gmail")
                        stats["deleted_emails_filtered"] = filtered_out_count
                        
                        # If we've filtered some emails, re-send the updated cached emails
                        yield {
                            'type': 'cached',
                            'data': {'emails': [email.dict() for email in cached_emails]}
                        }
                
                # Filter out already cached emails
                new_raw_emails = [email for email in raw_emails if email.get('id') not in cached_ids]
                stats["new_emails"] = len(new_raw_emails)
                
                self.logger.info(f"Email Retrieval Complete: {len(raw_emails)} total, {len(cached_emails)} cached)\n")
                self.logger.debug(f"Email Retrieval Complete\n"
                    f"    From Gmail: {len(raw_emails)} emails\n"
                    f"    Already Cached: {len(cached_ids)} emails\n"
                    f"    New Emails: {len(new_raw_emails)} emails"
                )
                
                # If we have no new emails to process, yield stats and return
                if not new_raw_emails:
                    yield {
                        'type': 'stats',
                        'data': {
                            'total_fetched': stats['emails_fetched'],
                            'new_emails': 0,
                            'cached': len(cached_ids)
                        }
                    }
                    return
                
                # Send initial stats so UI can show total emails to process
                yield {
                    'type': 'initial_stats',
                    'data': {
                        'total_fetched': stats['emails_fetched'],
                        'new_emails': stats['new_emails'],
                        'cached': len(cached_ids)
                    }
                }
                
                if new_raw_emails:
                    yield {
                        'type': 'status',
                        'data': {'message': 'Starting email analysis...'}
                    }
                    yield {
                        'type': 'status',
                        'data': {'message': f'Found {len(new_raw_emails)} new emails to process'}
                    }
                    
                    parsed_emails = [email for email in [self.parser.extract_metadata(email) for email in new_raw_emails] if email is not None]
                    
                    # If AI is disabled, create basic metadata without batch processing
                    if not ai_enabled:
                        self.logger.info("AI features disabled, skipping batch analysis")
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
                            if self.cache:
                                await self.cache.store_many([processed_email], user_email, ttl_days=cache_duration)
                        
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
                            "failed_parsing": len(new_raw_emails) - len(parsed_emails),
                            "failed_analysis": 0
                        })
                    
                    # Only do batch processing if AI is enabled
                    else:
                        if command.batch_size:
                            batch_count = (len(parsed_emails) + command.batch_size - 1) // command.batch_size
                            stats["batches"] = batch_count
                            
                            # Keep only this critical memory log point
                            log_memory_usage(self.logger, "Before Starting Streaming Batch Processing")
                            
                            self.logger.info(f"Starting Batch Processing: {len(parsed_emails)} emails, batch size {command.batch_size}, total batches {batch_count}")
                            self.logger.debug(f"Starting Batch Processing\n"
                                f"    Total Emails to Process: {len(parsed_emails)}\n"
                                f"    Batch Size: {command.batch_size}\n"
                                f"    Total Batches: {batch_count}"
                            )
                            
                            for i in range(0, len(parsed_emails), command.batch_size):
                                batch = parsed_emails[i:i + command.batch_size]
                                batch_results = await self.processor.analyze_parsed_emails(batch, user_id=user_id, ai_enabled=ai_enabled)
                                
                                # Cache batch results
                                if self.cache and batch_results:
                                    await self.cache.store_many(batch_results, user_email, ttl_days=cache_duration)
                                
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
                                stats["processed"] = i + min(command.batch_size, len(parsed_emails) - i if parsed_emails else 0)
                                yield {
                                    'type': 'status',
                                    'data': {
                                        'message': f'Processed {stats["processed"]}/{stats["new_emails"]} emails',
                                        'progress': i / stats["new_emails"] if stats["new_emails"] > 0 else 1
                                    }
                                }
                            
                            # Once all batches are done, if using cache, save newly processed emails
                            if self.cache:
                                try:
                                    # We no longer need to save anything here since we've been caching each batch as we go
                                    self.logger.debug("All batches have been cached individually already")
                                except Exception as e:
                                    self.logger.error(f"Failed to store emails in cache: {e}")
                            
                            # Final stats
                            yield {
                                'type': 'complete',
                                'data': {
                                    'processed': stats.get("processed", 0),
                                    'cached': stats.get("cached", 0),
                                    'total': stats.get("cached", 0) + stats.get("processed", 0),
                                }
                            }
                            
                            # Clear any remaining large objects to free memory
                            batch_results = None
                            
                            # Force garbage collection
                            gc.collect()
                            
                            # Log memory at end of pipeline
                            log_memory_usage(self.logger, "Streaming Pipeline Complete")
                        
                        else:
                            # Process all at once if no batch size specified
                            # Log memory before processing all emails at once
                            log_memory_usage(self.logger, "Before Processing All Emails")
                            
                            analyzed_emails = await self.processor.analyze_parsed_emails(parsed_emails, user_id=user_id, ai_enabled=ai_enabled)
                            stats["batches"] = 1
                            
                            # Log memory after processing all emails
                            log_memory_usage(self.logger, "After Processing All Emails")
                            
                            # Cache results
                            if self.cache and analyzed_emails:
                                stats["processed"] = len(analyzed_emails)  # Track processed count
                                await self.cache.store_many(analyzed_emails, user_email, ttl_days=cache_duration)
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

                        stats.update({
                            "successfully_parsed": len(parsed_emails),
                            "failed_parsing": len(new_raw_emails) - len(parsed_emails)
                        })

                # Log final pipeline stats
                success_rate_parse = f"{stats['successfully_parsed']}/{stats['new_emails']}" if stats['new_emails'] > 0 else "N/A"
                success_rate_analyze = f"{stats['successfully_analyzed']}/{stats['successfully_parsed']}" if stats['successfully_parsed'] > 0 else "N/A"
                
                self.logger.info(f"Pipeline Complete: {stats['emails_fetched']} total emails, {stats['new_emails']} new")
                self.logger.info(f"Pipeline Success Stats: {stats['successfully_parsed']}/{stats['new_emails']} parsed, {stats['successfully_analyzed']}/{stats['new_emails']} analyzed\n")
                self.logger.debug(f"Pipeline Complete\n"
                    f"Email Processing Summary:\n"
                    f"    Total Processed: {stats['emails_fetched']} emails\n"
                    f"    New Emails: {stats['new_emails']} emails\n"
                    f"    Success Rates:\n"
                    f"        Parsing: {success_rate_parse}\n"
                    f"        Analysis: {success_rate_analyze}"
                )

                # Keep only this critical end log point
                log_memory_usage(self.logger, "Streaming Pipeline End")

                # Yield final stats as a dictionary
                yield {
                    'type': 'stats',
                    'data': {
                        'total_processed': stats.get('emails_fetched', 0),
                        'new_emails': stats.get('new_emails', 0),
                        'successfully_parsed': stats.get('successfully_parsed', 0),
                        'successfully_analyzed': stats.get('successfully_analyzed', 0),
                        'failed_parsing': stats.get('failed_parsing', 0),
                        'failed_analysis': stats.get('failed_analysis', 0),
                        'success_rate_parse': success_rate_parse,
                        'success_rate_analyze': success_rate_analyze,
                        'batches': stats.get('batches', 0),
                        'total': stats.get('cached', 0) + stats.get('processed', 0)  # Use safe get method
                    }
                }

            finally:
                # Even though the route will handle disconnection,
                # we ensure resources are cleaned up here as well
                try:
                    await self.connection.disconnect()
                    log_memory_usage(self.logger, "Streaming Pipeline After Disconnection")
                except Exception as e:
                    self.logger.error(f"Error during streaming pipeline disconnect: {e}")
                
        except Exception as e:
            self.logger.error(f"Pipeline error: {e}")
            yield {
                'type': 'error',
                'data': {'message': str(e)}
            }
            raise

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