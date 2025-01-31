"""Email processing module with analytics tracking."""

import logging
from typing import List, Dict, Any
from datetime import datetime, timezone
import time
from flask import session, current_app

from ...models import log_activity
from .email_parsing import EmailMetadata
from ..analyzers.semantic_analyzer import SemanticAnalyzer
from ..analyzers.content_analyzer import ContentAnalyzer
from ..utils.priority_scoring import PriorityScorer
from ..models.processed_email import ProcessedEmail
from ..models.exceptions import EmailProcessingError

class EmailProcessor:
    """Processes emails using various analyzers and tracks analytics."""
    
    def __init__(
        self,
        email_client: Any,  # Can be either EmailConnection or GmailClient
        text_analyzer: ContentAnalyzer,
        llm_analyzer: SemanticAnalyzer,
        priority_calculator: PriorityScorer,
        parser: Any  # EmailParser
    ):
        """Initialize the email processor with its components."""
        self.email_client = email_client
        self.text_analyzer = text_analyzer
        self.llm_analyzer = llm_analyzer
        self.priority_calculator = priority_calculator
        self.parser = parser
        self.logger = logging.getLogger(__name__)

    def _ensure_utc_date(self, date: datetime) -> datetime:
        """Ensure a datetime is in UTC timezone."""
        if date.tzinfo is None:
            return date.replace(tzinfo=timezone.utc)
        return date.astimezone(timezone.utc)

    async def analyze_recent_emails(self, days_back: int = 1) -> List[ProcessedEmail]:
        """Analyze recent emails with detailed analytics tracking."""
        try:
            start_time = time.time()
            user_id = session.get('user', {}).get('id')
            
            # Initialize analytics
            processing_stats = {
                'emails_fetched': 0,
                'new_emails': 0,
                'successfully_parsed': 0,
                'successfully_analyzed': 0,
                'failed_parsing': 0,
                'failed_analysis': 0
            }
            
            # Fetch emails
            raw_emails = await self.email_client.fetch_emails(days=days_back)
            processing_stats['emails_fetched'] = len(raw_emails)
            
            # Track already processed emails
            processed_ids = set()  # In a real app, get this from your database
            
            processed_emails = []
            for raw_email in raw_emails:
                email_id = raw_email.get('id')
                
                if email_id not in processed_ids:
                    processing_stats['new_emails'] += 1
                    
                    try:
                        # Parse email
                        parsed_email = self.parser.extract_metadata(raw_email)
                        if parsed_email:
                            processing_stats['successfully_parsed'] += 1
                            
                            # Track NLP processing
                            nlp_start_time = time.time()
                            nlp_results = self.text_analyzer.analyze(parsed_email.body)
                            nlp_processing_time = time.time() - nlp_start_time
                            
                            if user_id:
                                log_activity(
                                    user_id=user_id,
                                    activity_type='nlp_processing',
                                    description=f"NLP analysis for email {email_id}",
                                    metadata={
                                        'processing_time': nlp_processing_time,
                                        'entities_extracted': len(nlp_results.get('entities', [])),
                                        'sentiment_analyses': 1 if nlp_results.get('sentiment') else 0,
                                        'keywords_extracted': len(nlp_results.get('keywords', []))
                                    }
                                )
                            
                            # LLM Analysis
                            try:
                                llm_start_time = time.time()
                                llm_results = await self.llm_analyzer.analyze(parsed_email, nlp_results)
                                
                                if user_id:
                                    log_activity(
                                        user_id=user_id,
                                        activity_type='llm_request',
                                        description=f"LLM analysis for email {email_id}",
                                        metadata={
                                            'model': llm_results.get('model', 'unknown'),
                                            'total_tokens': llm_results.get('total_tokens', 0),
                                            'prompt_length': len(str(parsed_email.body)),
                                            'processing_time': time.time() - llm_start_time,
                                            'cost': llm_results.get('cost', 0)
                                        }
                                    )
                                
                                processing_stats['successfully_analyzed'] += 1
                                
                                # Calculate priority
                                try:
                                    priority_score, priority_level = self.priority_calculator.score(
                                        parsed_email.sender,  # Pass just the sender string
                                        nlp_results,
                                        llm_results
                                    )
                                except Exception as e:
                                    self.logger.warning(f"Priority calculation failed for email {parsed_email.id}, using defaults: {e}")
                                    priority_score = 0
                                    priority_level = "LOW"
                                
                                # Ensure date is in UTC
                                email_date = self._ensure_utc_date(parsed_email.date)
                                
                                processed_email = ProcessedEmail(
                                    id=parsed_email.id,
                                    subject=parsed_email.subject,
                                    sender=parsed_email.sender,
                                    body=parsed_email.body,
                                    date=email_date,
                                    urgency=nlp_results.get('is_urgent', False),
                                    entities=nlp_results.get('entities', {}),
                                    key_phrases=nlp_results.get('key_phrases', []),
                                    sentence_count=nlp_results.get('sentence_count'),
                                    sentiment_indicators=nlp_results.get('sentiment_indicators', {}),
                                    structural_elements=nlp_results.get('structural_elements', {}),
                                    needs_action=llm_results.get('needs_action', False),
                                    category=llm_results.get('category'),
                                    action_items=llm_results.get('action_items', []),
                                    summary=llm_results.get('summary'),
                                    priority=priority_score,
                                    priority_level=priority_level
                                )
                                processed_emails.append(processed_email)
                                
                            except Exception as e:
                                self.logger.error(f"LLM analysis failed for email {email_id}: {e}")
                                processing_stats['failed_analysis'] += 1
                        else:
                            processing_stats['failed_parsing'] += 1
                            
                    except Exception as e:
                        self.logger.error(f"Email processing failed for {email_id}: {e}")
                        processing_stats['failed_parsing'] += 1
            
            # Log overall processing stats
            if user_id:
                log_activity(
                    user_id=user_id,
                    activity_type='email_processing',
                    description=f"Processed {len(raw_emails)} emails",
                    metadata={
                        'processing_time': time.time() - start_time,
                        **processing_stats
                    }
                )
            
            return processed_emails
            
        except Exception as e:
            self.logger.error(f"Email analysis failed: {e}")
            raise

    async def analyze_parsed_emails(self, parsed_emails: List[EmailMetadata]) -> List[ProcessedEmail]:
        """Analyze a list of already parsed emails."""
        processed_emails = []
        user_id = session.get('user', {}).get('id')
        
        for parsed_email in parsed_emails:
            try:
                # Track NLP processing
                nlp_start_time = time.time()
                nlp_results = self.text_analyzer.analyze(parsed_email.body)
                nlp_processing_time = time.time() - nlp_start_time
                
                if user_id:
                    log_activity(
                        user_id=user_id,
                        activity_type='nlp_processing',
                        description=f"NLP analysis for email {parsed_email.id}",
                        metadata={
                            'processing_time': nlp_processing_time,
                            'entities_extracted': len(nlp_results.get('entities', [])),
                            'sentiment_analyses': 1 if nlp_results.get('sentiment') else 0,
                            'keywords_extracted': len(nlp_results.get('keywords', []))
                        }
                    )
                
                # LLM Analysis
                try:
                    llm_start_time = time.time()
                    llm_results = await self.llm_analyzer.analyze(parsed_email, nlp_results)
                    
                    if user_id:
                        log_activity(
                            user_id=user_id,
                            activity_type='llm_request',
                            description=f"LLM analysis for email {parsed_email.id}",
                            metadata={
                                'model': llm_results.get('model', 'unknown'),
                                'total_tokens': llm_results.get('total_tokens', 0),
                                'prompt_length': len(str(parsed_email.body)),
                                'processing_time': time.time() - llm_start_time,
                                'cost': llm_results.get('cost', 0)
                            }
                        )
                    
                    # Calculate priority
                    try:
                        priority_score, priority_level = self.priority_calculator.score(
                            parsed_email.sender,  # Pass just the sender string
                            nlp_results,
                            llm_results
                        )
                    except Exception as e:
                        self.logger.warning(f"Priority calculation failed for email {parsed_email.id}, using defaults: {e}")
                        priority_score = 0
                        priority_level = "LOW"
                    
                    # Ensure date is in UTC
                    email_date = self._ensure_utc_date(parsed_email.date)
                    
                    # Create ProcessedEmail object
                    processed_email = ProcessedEmail(
                        id=parsed_email.id,
                        subject=parsed_email.subject,
                        sender=parsed_email.sender,
                        body=parsed_email.body,
                        date=email_date,
                        urgency=nlp_results.get('is_urgent', False),
                        entities=nlp_results.get('entities', {}),
                        key_phrases=nlp_results.get('key_phrases', []),
                        sentence_count=nlp_results.get('sentence_count'),
                        sentiment_indicators=nlp_results.get('sentiment_indicators', {}),
                        structural_elements=nlp_results.get('structural_elements', {}),
                        needs_action=llm_results.get('needs_action', False),
                        category=llm_results.get('category'),
                        action_items=llm_results.get('action_items', []),
                        summary=llm_results.get('summary'),
                        priority=priority_score,
                        priority_level=priority_level
                    )
                    processed_emails.append(processed_email)
                    
                except Exception as e:
                    self.logger.error(f"LLM analysis failed for email {parsed_email.id}: {e}")
                    continue
                    
            except Exception as e:
                self.logger.error(f"Email processing failed for {parsed_email.id}: {e}")
                continue
        
        return processed_emails

    def _get_priority_level(self, score: int) -> str:
        """Convert numerical priority score to level."""
        if score >= 80:
            return 'HIGH'
        elif score >= 50:
            return 'MEDIUM'
        else:
            return 'LOW'

    async def __aenter__(self):
        """Enters the asynchronous context."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exits the asynchronous context and cleans up resources."""
        await self.email_client.close()

class EmailProcessingError(Exception):
    """Base class for email processing errors."""
    pass

class LLMProcessingError(EmailProcessingError):
    """Raised when LLM processing fails."""
    pass

class NLPProcessingError(EmailProcessingError):
    """Raised when NLP processing fails."""
    pass