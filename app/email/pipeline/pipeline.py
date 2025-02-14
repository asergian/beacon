"""Email processing pipeline module.

This module provides the pipeline for processing and analyzing emails,
combining various components like email fetching, parsing, and analysis.

The pipeline uses two time-based parameters:
- days_back: Number of days to fetch emails for (1 = today, 2 = today and yesterday, etc.)
- cache_duration_days: Number of days to keep emails in cache (1 = last 24 hours, etc.)
"""

from dataclasses import dataclass
from typing import List, Optional, Dict
from datetime import datetime, timedelta, timezone
import logging
from flask import session
import time

from ..core.email_processor import EmailProcessor
from ..models.processed_email import ProcessedEmail
from ..storage.cache import EmailCache
from ..core.gmail_client import GmailClient
from ..core.email_parsing import EmailParser
from ...models import log_activity
from ..models.analysis_command import AnalysisCommand
from app.models import User

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
        #rate_limiter: Optional[RateLimiter] = None,
        #metrics: Optional[MetricsCollector] = None
    ):
        self.connection = connection
        self.parser = parser
        self.processor = processor
        self.cache = cache
        #self.rate_limiter = rate_limiter
        #self.metrics = metrics
        self.logger = logging.getLogger(__name__)

    async def get_analyzed_emails(self, command: AnalysisCommand) -> AnalysisResult:
        """Main method to get and analyze emails with caching and metrics
        
        Args:
            command: AnalysisCommand containing:
                - days_back: Number of days to fetch (1 = today, 2 = today and yesterday)
                - cache_duration_days: Number of days to keep in cache
                - other filtering parameters
        """
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
                
            self.logger.info(
                "Starting Email Pipeline\n"
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
            
            # Check AI features once at the pipeline level
            ai_enabled = user.get_setting('ai_features.enabled', True)
            if not ai_enabled:
                self.logger.info("AI features disabled for this pipeline run")
            
            # Get cache duration from settings
            cache_duration = user.get_setting('email_preferences.cache_duration_days', 7)
            
            # Set up cache if available
            cached_emails = []
            cached_ids = set()
            if self.cache:
                cached_emails = await self.cache.get_recent(cache_duration, command.days_back, user_email)
                cached_ids = {email.id for email in cached_emails}
                stats["cached"] = len(cached_emails)
            
            # Now that user context is set up, connect to Gmail with user email
            await self.connection.connect(user_email)
            try:
                raw_emails = await self.connection.fetch_emails(command.days_back, user_email)
                stats["emails_fetched"] = len(raw_emails)
                
                # Filter out already cached emails
                new_raw_emails = [email for email in raw_emails if email.get('id') not in cached_ids]
                stats["new_emails"] = len(new_raw_emails)
                
                self.logger.info(
                    "Email Retrieval Complete\n"
                    f"    From Cache: {len(cached_ids)} emails\n"
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
                            
                            self.logger.info(
                                "Starting Batch Processing\n"
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
                        await self.cache.store_many(analyzed_emails, user_email, ttl_days=cache_duration)
                
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
                    f"    From Cache: {stats.get('cached', 0)} emails\n"
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
                                'cached_emails': stats.get('cached', 0),
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

                return AnalysisResult(
                    emails=filtered_emails,
                    stats=stats,
                    errors=errors
                )
            finally:
                # No cleanup here - let the route handle disconnection
                pass

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

    async def refresh_cache(self, days: int = 1, batch_size: Optional[int] = None) -> None:
        """Force refresh of cache with recent emails"""
        if not self.cache:
            return
            
        # Set the user email from session
        if 'user' in session and 'email' in session['user']:
            await self.cache.set_user(session['user']['email'])
        else:
            raise ValueError("No user email found in session")
            
        command = AnalysisCommand(days_back=days, batch_size=batch_size)
        await self.get_analyzed_emails(command)

    async def get_analyzed_emails_stream(self, command: AnalysisCommand):
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
            "batches": 0
        }

        try:
            # First ensure we have user context
            if 'user' not in session:
                raise ValueError("No user found in session")
                
            user_id = int(session['user'].get('id'))
            user_email = session['user'].get('email')
            if not user_email:
                raise ValueError("No user email found in session")
                
            self.logger.info(
                "Starting Email Pipeline (Streaming)\n"
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
            
            # Check AI features once at the pipeline level
            ai_enabled = user.get_setting('ai_features.enabled', True)
            if not ai_enabled:
                self.logger.info("AI features disabled for this pipeline run")
            
            # Get cache duration from settings
            cache_duration = user.get_setting('email_preferences.cache_duration_days', 7)
            
            # Set up cache and get cached emails
            cached_ids = set()
            if self.cache:
                # Send status update as dictionary
                yield {
                    'type': 'status',
                    'data': {'message': 'Checking cache...'}
                }
                
                cached_emails = await self.cache.get_recent(command.cache_duration_days, command.days_back, user_email)
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
                raw_emails = await self.connection.fetch_emails(command.days_back, user_email)
                stats["emails_fetched"] = len(raw_emails)
                
                # Filter out already cached emails
                new_raw_emails = [email for email in raw_emails if email.get('id') not in cached_ids]
                stats["new_emails"] = len(new_raw_emails)
                
                self.logger.info(
                    "Email Retrieval Complete\n"
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
                            
                            # Cache each email as we process it
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
                            
                            self.logger.info(
                                "Starting Batch Processing\n"
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
                                
                                # Yield each batch as it's processed
                                if batch_results:
                                    yield {
                                        'type': 'batch',
                                        'data': {'emails': [email.dict() for email in batch_results]}
                                    }
                                    
                                    processed_so_far = i + len(batch_results)
                                    yield {
                                        'type': 'status',
                                        'data': {'message': f'Processed {processed_so_far} of {len(parsed_emails)} emails'}
                                    }
                                
                                # Update stats
                                stats["successfully_analyzed"] += len(batch_results)
                                stats["failed_analysis"] += len(batch) - len(batch_results)
                        else:
                            # Process all at once if no batch size specified
                            analyzed_emails = await self.processor.analyze_parsed_emails(parsed_emails, user_id=user_id, ai_enabled=ai_enabled)
                            stats["batches"] = 1
                            
                            # Cache results
                            if self.cache and analyzed_emails:
                                await self.cache.store_many(analyzed_emails, user_email, ttl_days=cache_duration)
                            
                            # Yield all results at once
                            if analyzed_emails:
                                yield {
                                    'type': 'batch',
                                    'data': {'emails': [email.dict() for email in analyzed_emails]}
                                }
                            
                            stats.update({
                                "successfully_analyzed": len(analyzed_emails),
                                "failed_analysis": len(parsed_emails) - len(analyzed_emails)
                            })

                        stats.update({
                            "successfully_parsed": len(parsed_emails),
                            "failed_parsing": len(new_raw_emails) - len(parsed_emails)
                        })

                # Log final pipeline stats
                success_rate_parse = f"{stats['successfully_parsed']}/{stats['new_emails']}" if stats['new_emails'] > 0 else "N/A"
                success_rate_analyze = f"{stats['successfully_analyzed']}/{stats['successfully_parsed']}" if stats['successfully_parsed'] > 0 else "N/A"
                
                self.logger.info(
                    "Pipeline Complete\n"
                    "Email Processing Summary:\n"
                    f"    Total Processed: {stats['emails_fetched']} emails\n"
                    f"    New Emails: {stats['new_emails']} emails\n"
                    f"    Success Rates:\n"
                    f"        Parsing: {success_rate_parse}\n"
                    f"        Analysis: {success_rate_analyze}"
                )

                # Yield final stats as a dictionary
                yield {
                    'type': 'stats',
                    'data': {
                        'total_processed': stats['emails_fetched'],
                        'new_emails': stats['new_emails'],
                        'successfully_parsed': stats['successfully_parsed'],
                        'successfully_analyzed': stats['successfully_analyzed'],
                        'failed_parsing': stats['failed_parsing'],
                        'failed_analysis': stats['failed_analysis'],
                        'success_rate_parse': success_rate_parse,
                        'success_rate_analyze': success_rate_analyze,
                        'batches': stats['batches']
                    }
                }

            finally:
                # No cleanup here - let the route handle disconnection
                pass
                
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