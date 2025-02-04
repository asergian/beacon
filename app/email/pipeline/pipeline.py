"""Email processing pipeline module.

This module provides the pipeline for processing and analyzing emails,
combining various components like email fetching, parsing, and analysis.
"""

from dataclasses import dataclass
from typing import List, Optional, Dict
from datetime import datetime, timedelta
import asyncio
from redis import asyncio as aioredis
import spacy
import logging
from flask import session

from ..core.email_processor import EmailProcessor
from ..models.processed_email import ProcessedEmail
from ..storage.cache import EmailCache, RedisEmailCache
# from ..rate_limiting import RateLimiter
# from ..metrics import MetricsCollector
from ..core.gmail_client import GmailClient
from ..core.email_parsing import EmailParser
from ..analyzers.semantic_analyzer import SemanticAnalyzer
from ..analyzers.content_analyzer import ContentAnalyzer
from ..utils.priority_scoring import PriorityScorer
from ..models.analysis_settings import ProcessingConfig
from ..utils.clean_message_id import clean_message_id
from ...models import log_activity

@dataclass
class AnalysisCommand:
    """Represents a request to analyze emails"""
    days_back: int
    cache_duration_days: int
    batch_size: Optional[int] = None
    priority_threshold: Optional[int] = None
    categories: Optional[List[str]] = None

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
        """Main method to get and analyze emails with caching and metrics"""
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
                
            self.logger.info(f"Processing emails for user: {user_email} (ID: {user_id})")
            
            # Set up cache if available
            cached_emails = []
            cached_ids = set()
            if self.cache:
                await self.cache.set_user(user_email)
                cached_emails = await self.cache.get_recent(command.cache_duration_days, command.days_back)
                cached_ids = {email.id for email in cached_emails}
                stats["cached"] = len(cached_emails)
                self.logger.info(f"Found {len(cached_ids)} cached email IDs")
            
            # Now that user context is set up, connect to Gmail
            await self.connection.connect()
            raw_emails = await self.connection.fetch_emails(command.days_back)
            stats["emails_fetched"] = len(raw_emails)
            self.logger.info(f"Stats after fetch: emails_fetched={stats['emails_fetched']}")
            
            # Filter out already cached emails
            new_raw_emails = []
            for email in raw_emails:
                # Use Gmail API ID for comparison
                gmail_id = email.get('id')  # This is the hex ID from Gmail API
                if gmail_id and gmail_id not in cached_ids:
                    new_raw_emails.append(email)
            
            stats["new_emails"] = len(new_raw_emails)
            self.logger.info(f"Stats after new email check: new_emails={stats['new_emails']}")
            
            # Only process new emails if there are any
            analyzed_emails = []
            if new_raw_emails:
                self.logger.info("Processing new emails")
                parsed_emails = [self.parser.extract_metadata(email) for email in new_raw_emails]
                # Filter out None values from parsing failures
                parsed_emails = [email for email in parsed_emails if email is not None]
                self.logger.info(f"Parsing results: attempted={len(new_raw_emails)}, successful={len(parsed_emails)}")
                
                # Process in batches if specified
                if command.batch_size:
                    analyzed_batch = []
                    for i in range(0, len(parsed_emails), command.batch_size):
                        batch = parsed_emails[i:i + command.batch_size]
                        batch_results = await self.processor.analyze_parsed_emails(batch, user_id=user_id)
                        self.logger.info(f"Batch analysis results: input={len(batch)}, output={len(batch_results)}")
                        analyzed_batch.extend(batch_results)
                    analyzed_emails = analyzed_batch
                else:
                    analyzed_emails = await self.processor.analyze_parsed_emails(parsed_emails, user_id=user_id)
                    self.logger.info(f"Full analysis results: input={len(parsed_emails)}, output={len(analyzed_emails)}")

                stats["successfully_analyzed"] = len(analyzed_emails)
                stats["successfully_parsed"] = len(parsed_emails)
                stats["failed_parsing"] = len(new_raw_emails) - len(parsed_emails)
                stats["failed_analysis"] = len(parsed_emails) - len(analyzed_emails)
                
                self.logger.info(f"Final stats: {stats}")

                # Cache new results if cache available
                if self.cache and analyzed_emails:
                    await self.cache.store_many(analyzed_emails)
                    self.logger.info(f"Cached {len(analyzed_emails)} new emails")
            else:
                self.logger.info("No new emails to process")
            
            # Combine cached and newly analyzed emails
            all_emails = cached_emails + analyzed_emails
            self.logger.info(f"Total emails after combining: cached={len(cached_emails)}, new={len(analyzed_emails)}, total={len(all_emails)}")
            
            # Apply filters to all emails
            filtered_emails = self._apply_filters(all_emails, command)
            self.logger.info(f"Emails after filtering: {len(filtered_emails)}")

            # Log pipeline stats
            self.logger.info(f"About to log pipeline activity with stats: {stats}")
            self.logger.info(f"User ID for logging: {user_id}")

            try:
                log_activity(
                    user_id=user_id,
                    activity_type='pipeline_processing',
                    description=f"Pipeline processed {len(filtered_emails)} emails",
                    metadata={
                        'stats': stats,
                        'command': {
                            'days_back': command.days_back,
                            'cache_duration_days': command.cache_duration_days,
                            'batch_size': command.batch_size,
                            'priority_threshold': command.priority_threshold,
                            'categories': command.categories
                        }
                    }
                )
                self.logger.info("Successfully logged pipeline activity")
            except Exception as e:
                self.logger.error(f"Failed to log pipeline activity: {e}")
                # Don't raise the exception - we don't want to fail the whole pipeline if logging fails

            # Collect metrics
            # if self.metrics:
            #     await self.metrics.record_analysis(stats, datetime.now() - start_time)

            return AnalysisResult(
                emails=filtered_emails,
                stats=stats,
                errors=errors
            )

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