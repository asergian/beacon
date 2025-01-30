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

    async def get_analyzed_emails(self, command: AnalysisCommand) -> AnalysisResult:
        """Main method to get and analyze emails with caching and metrics"""
        #start_time = datetime.now()
        errors = []
        stats = {"processed": 0, "cached": 0, "errors": 0, "new": 0}

        print("Getting analyzed emails")
        try:
            # Ensure Gmail client is connected with current user's credentials
            await self.connection.connect()
            
            # Get cached emails first if cache is available
            cached_emails = []
            cached_ids = set()
            if self.cache:
                # Set the user email from session
                if 'user' in session and 'email' in session['user']:
                    await self.cache.set_user(session['user']['email'])
                else:
                    raise ValueError("No user email found in session")
                    
                cached_emails = await self.cache.get_recent(command.cache_duration_days, command.days_back)
                cached_ids = {email.id for email in cached_emails}
                stats["cached"] = len(cached_emails)

            print("Number of cached emails: ", len(cached_emails))
            print("IDs: ", cached_ids)

            # Fetch new emails
            # if self.rate_limiter:
            #     await self.rate_limiter.acquire()

            raw_emails = await self.connection.fetch_emails(command.days_back)
            print("Fetched # of emails: ", len(raw_emails))
            
            # Filter out already cached emails
            new_raw_emails = []
            for email in raw_emails:
                # Use Gmail API ID instead of Message-ID
                gmail_id = email.get('id')  # This is the hex ID from Gmail API
                if gmail_id and gmail_id not in cached_ids:
                    new_raw_emails.append(email)
                else:
                    print(f"Skipping cached email with ID: {gmail_id}")
            
            stats["new"] = len(new_raw_emails)
            print(f"New emails: {stats['new']}")
            # Only process new emails if there are any
            if new_raw_emails:
                print("Processing new emails")
                parsed_emails = [self.parser.extract_metadata(email) for email in new_raw_emails]
                # Filter out None values from parsing failures
                parsed_emails = [email for email in parsed_emails if email is not None]
                
                # Process in batches if specified
                if command.batch_size:
                    analyzed_emails = []
                    for i in range(0, len(parsed_emails), command.batch_size):
                        batch = parsed_emails[i:i + command.batch_size]
                        analyzed_batch = await self.processor.analyze_parsed_emails(batch)
                        analyzed_emails.extend(analyzed_batch)
                else:
                    analyzed_emails = await self.processor.analyze_parsed_emails(parsed_emails)

                stats["processed"] = len(analyzed_emails)

                # Cache new results if cache available
                if self.cache and analyzed_emails:
                    await self.cache.store_many(analyzed_emails)
                    cached_emails.extend(analyzed_emails)

            # Apply filters to all emails (cached + new)
            filtered_emails = self._apply_filters(cached_emails, command)

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

def create_pipeline(config: dict):
    """Create pipeline instance with configuration"""
    # Initialize Redis cache if URL provided
    email_cache = None
    if redis_url := config.get('REDIS_URL', "redis://localhost:6379"):
        try:
            redis = aioredis.from_url(redis_url)
            email_cache = RedisEmailCache(redis)
            logging.info("Redis cache initialized successfully")
        except Exception as e:
            logging.warning(f"Failed to initialize Redis cache: {e}. Continuing without caching.")
    
    # Initialize Gmail client
    email_client = GmailClient()
    
    # Initialize NLP components
    nlp = spacy.load("en_core_web_sm")
    text_analyzer = ContentAnalyzer(nlp)
    
    # Initialize LLM analyzer
    llm_analyzer = SemanticAnalyzer()
    
    # Initialize priority calculator with VIP senders
    vip_senders = set(config.get('VIP_SENDERS', []))
    priority_calculator = PriorityScorer(vip_senders, ProcessingConfig())
    
    # Initialize parser
    email_parser = EmailParser()
    
    # Initialize the email processor that combines all components
    email_processor = EmailProcessor(
        email_client=email_client,
        text_analyzer=text_analyzer,
        llm_analyzer=llm_analyzer,
        priority_calculator=priority_calculator,
        parser=email_parser
    )
    
    return EmailPipeline(
        connection=email_client,
        parser=email_parser,
        processor=email_processor,
        cache=email_cache
    ) 