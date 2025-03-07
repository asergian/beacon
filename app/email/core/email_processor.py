"""Email processing module with analytics tracking."""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import time
from flask import session, current_app
import json

from app.models.activity import log_activity
from .email_parsing import EmailMetadata
from ..analyzers.semantic.analyzer import SemanticAnalyzer
from ..analyzers.content.core.nlp_analyzer import ContentAnalyzer
from ..utils.priority_scorer import PriorityScorer
from ..models.processed_email import ProcessedEmail
from ..models.exceptions import EmailProcessingError
from ..models.analysis_command import AnalysisCommand
from app.utils.memory_profiling import log_memory_usage, log_memory_cleanup

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
        self.processed_count = 0  # Track number of processed emails

    def _ensure_utc_date(self, date: datetime) -> datetime:
        """Ensure a datetime is in UTC timezone."""
        if date.tzinfo is None:
            return date.replace(tzinfo=timezone.utc)
        return date.astimezone(timezone.utc)

    async def analyze_recent_emails(self, command: AnalysisCommand, user_id: Optional[int] = None) -> List[ProcessedEmail]:
        """Analyze recent emails with detailed analytics tracking."""
        try:
            start_time = time.time()
            
            # Debug logging for session data
            self.logger.info(f"Processing emails for user ID: {user_id} (type: {type(user_id)})")
            
            # Get user settings if user_id is provided
            if user_id:
                from app.models.user import User
                user = User.query.get(user_id)
                if user:
                    # Check if AI features are enabled first
                    ai_enabled = user.get_setting('ai_features.enabled', True)
                    if not ai_enabled:
                        self.logger.info("AI features disabled, skipping analysis")
                        # Fetch emails but return basic metadata only
                        raw_emails = await self.email_client.fetch_emails(command.days_back)
                        processed_emails = []
                        for raw_email in raw_emails:
                            parsed_email = self.parser.extract_metadata(raw_email)
                            if parsed_email:
                                email_date = self._ensure_utc_date(parsed_email.date)
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
                                    priority_level='LOW',
                                    custom_categories={}
                                )
                                processed_emails.append(processed_email)
                        return processed_emails
                    
                    priority_threshold = user.get_setting('ai_features.priority_threshold', 50)
                    self.priority_calculator.set_priority_threshold(priority_threshold)
            
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
            raw_emails = await self.email_client.fetch_emails(command.days_back)
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
                            
                            # Clean HTML before any analysis
                            clean_body = self.llm_analyzer._strip_html(parsed_email.body)
                            
                            # Create clean version of email metadata
                            clean_email = EmailMetadata(
                                id=parsed_email.id,
                                subject=parsed_email.subject,
                                sender=parsed_email.sender,
                                body=clean_body,
                                date=parsed_email.date
                            )
                            
                            # Track NLP processing with clean text
                            nlp_start_time = time.time()
                            nlp_results = self.text_analyzer.analyze(clean_body)
                            nlp_processing_time = time.time() - nlp_start_time
                            
                            if user_id:
                                log_activity(
                                    user_id=user_id,
                                    activity_type='nlp_processing',
                                    description=f"NLP analysis for email {email_id}",
                                    metadata={
                                        'processing_time': nlp_processing_time,
                                        'entities': nlp_results.get('entities', {}),
                                        'sentence_count': nlp_results.get('sentence_count', 0),
                                        'is_urgent': nlp_results.get('urgency', False),
                                        'sentiment_indicators': nlp_results.get('sentiment_indicators', {}),
                                        'structural_elements': nlp_results.get('structural_elements', {})
                                    }
                                )
                            
                            # LLM Analysis with clean email
                            try:
                                llm_start_time = time.time()
                                llm_results = await self.llm_analyzer.analyze(parsed_email, nlp_results)
                                llm_processing_time = time.time() - llm_start_time
                                
                                if user_id:
                                    log_activity(
                                        user_id=user_id,
                                        activity_type='llm_request',
                                        description=f"LLM analysis for email {email_id}",
                                        metadata={
                                            # Model info
                                            'model': llm_results.get('model', 'unknown'),
                                            
                                            # Token metrics
                                            'total_tokens': llm_results.get('total_tokens', 0),
                                            
                                            # Performance metrics
                                            'processing_time_ms': round(llm_processing_time * 1000),
                                            
                                            # Cost tracking (in cents for easier display)
                                            'cost_cents': round(llm_results.get('cost', 0) * 100, 2),
                                            
                                            # Email categorization
                                            'category': llm_results.get('category', 'Informational'),
                                            'priority_level': self._get_priority_level(llm_results.get('priority', 0)),
                                            'needs_action': llm_results.get('needs_action', False),
                                            'action_items': llm_results.get('action_items', []),
                                            
                                            # Status for monitoring
                                            'status': 'success',
                                            
                                            # Timestamp for time-series
                                            'timestamp': datetime.now().isoformat()
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
                                    priority_level=priority_level,
                                    custom_categories=llm_results.get('custom_categories', {})
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
                self.logger.info(f"About to log email processing activity with stats: {processing_stats}")
                try:
                    log_activity(
                        user_id=user_id,
                        activity_type='email_processing',
                        description=f"Processed {len(raw_emails)} emails",
                        metadata={
                            'stats': {
                                # Basic processing stats
                                'total_fetched': len(raw_emails),
                                'new_emails': len(raw_emails),  # All are new in direct processing
                                'successfully_parsed': processing_stats['successfully_parsed'],
                                'successfully_analyzed': processing_stats['successfully_analyzed'],
                                'failed_parsing': processing_stats['failed_parsing'],
                                'failed_analysis': processing_stats['failed_analysis'],
                                
                                # Category distribution
                                'categories': {
                                    'Work': sum(1 for email in processed_emails if email.category == 'Work'),
                                    'Personal': sum(1 for email in processed_emails if email.category == 'Personal'),
                                    'Promotions': sum(1 for email in processed_emails if email.category == 'Promotions'),
                                    'Informational': sum(1 for email in processed_emails if email.category == 'Informational')
                                },
                                
                                # Priority distribution
                                'priority_levels': {
                                    'HIGH': sum(1 for email in processed_emails if email.priority_level == 'HIGH'),
                                    'MEDIUM': sum(1 for email in processed_emails if email.priority_level == 'MEDIUM'),
                                    'LOW': sum(1 for email in processed_emails if email.priority_level == 'LOW')
                                },
                                
                                # Action metrics
                                'needs_action': sum(1 for email in processed_emails if email.needs_action),
                                'has_deadline': sum(1 for email in processed_emails if any(item.get('due_date') for item in email.action_items)),
                                
                                # Processing time
                                'processing_time': time.time() - start_time
                            }
                        }
                    )
                    self.logger.info("Successfully logged email processing activity")
                except Exception as e:
                    self.logger.error(f"Failed to log email processing activity: {e}")
            
            return processed_emails
            
        except Exception as e:
            self.logger.error(f"Email analysis failed: {e}")
            raise

    async def analyze_parsed_emails(self, parsed_emails: List[EmailMetadata], user_id: Optional[int] = None, ai_enabled: Optional[bool] = None) -> List[ProcessedEmail]:
        """
        Analyze parsed emails using NLP and LLM models.
        
        Args:
            parsed_emails: List of parsed email metadata
            user_id: Optional user ID for tracking
            ai_enabled: Whether to enable AI features
            
        Returns:
            List of processed emails with analysis
        """
        
        # Start timing
        start_time = time.time()
        
        # Track how many emails we've processed
        self.processed_count += len(parsed_emails)
        
        # Log the batch size and user ID for analytics
        self.logger.info(f"Starting batch analysis of {len(parsed_emails)} emails for user {user_id}")
        
        # Keep only essential batch start memory logging
        log_memory_usage(self.logger, "Email Batch Start")
        
        processed_emails = []
        
        try:
            # Process emails in chunks to avoid memory issues
            email_batch = parsed_emails
            
            # Analyze content with NLP
            try:
                # Process all bodies together for efficiency
                email_bodies = [email.body for email in email_batch]
                nlp_start = time.time()
                
                # Execute NLP analysis asynchronously
                nlp_results = await self.text_analyzer.analyze_batch(email_bodies)
                
                # Log memory after NLP - this is a critical point to track
                log_memory_usage(self.logger, "After NLP Analysis")
                
                nlp_end = time.time()
                self.logger.info(f"Batch NLP processing completed in {nlp_end - nlp_start:.2f} seconds (avg / email: {(nlp_end - nlp_start)/len(email_batch):.2f} seconds)")
            
            except Exception as e:
                self.logger.error(f"Batch NLP processing failed: {e}")
                # Create default response for failed NLP processing
                nlp_results = [{}] * len(email_batch)
                
            # Analyze with LLM if enabled
            if ai_enabled is not False:  # Default to True if not specified
                try:
                    # Get all emails ready for LLM processing
                    llm_batch = []
                    for i, email in enumerate(email_batch):
                        # Create a tuple with email and NLP results as expected by analyze_batch
                        nlp_result = nlp_results[i] if i < len(nlp_results) else {}
                        llm_batch.append((email, nlp_result))
                    
                    # Process with LLM in a batch
                    llm_start = time.time()
                    llm_results = await self.llm_analyzer.analyze_batch(llm_batch)
                    
                    # Log memory after LLM - this is a critical point to track
                    log_memory_usage(self.logger, "After LLM Analysis")
                    
                    llm_end = time.time()
                    self.logger.info(f"Batch LLM processing completed in {llm_end - llm_start:.2f} seconds (avg / email: {(llm_end - llm_start)/len(email_batch):.2f} seconds)")
                    
                    # Now combine all results into final processed emails
                    for i, email in enumerate(email_batch):
                        nlp_result = nlp_results[i] if i < len(nlp_results) else {}
                        llm_result = llm_results[i] if i < len(llm_results) else {}
                        
                        # Combine results
                        processed_email = self._create_processed_email(email, nlp_result, llm_result)
                        processed_emails.append(processed_email)
                        
                except Exception as e:
                    self.logger.error(f"Batch LLM processing failed: {e}")
            
            # Process emails individually for more robust error handling
            if not processed_emails and email_batch:
                self.logger.info("No emails were processed by LLM, falling back to individual processing")
                processed_emails = []
                
                # Process each email individually
                for i, email in enumerate(email_batch):
                    try:
                        # Get NLP result for this email
                        nlp_result = nlp_results[i] if i < len(nlp_results) else {}
                        
                        # Create a processed email without LLM
                        processed_email = self._create_processed_email(email, nlp_result, {})
                        processed_emails.append(processed_email)
                        
                    except Exception as e:
                        self.logger.error(f"Error processing email: {e}")
            
        except Exception as e:
            self.logger.error(f"Email batch processing failed: {e}")
            raise
        
        self.logger.info(f"Completed batch analysis of {len(processed_emails)} emails")
        
        # Log memory at batch end - keep this for overall batch memory tracking
        log_memory_usage(self.logger, "Email Batch End")
        
        # Keep these cleanup steps which are important for memory management
        log_memory_cleanup(self.logger, "After Email Processing")
        
        return processed_emails

    def _create_interim_result(self, email: EmailMetadata, nlp_result: Dict) -> Dict:
        """Create intermediate representation for LLM processing."""
        return {
            'id': email.id,
            'subject': email.subject,
            'sender': email.sender,
            'body': email.body,
            'date': email.date.isoformat() if hasattr(email.date, 'isoformat') else str(email.date),
            'nlp_results': nlp_result
        }
        
    def _create_processed_email(self, email: EmailMetadata, nlp_result: Dict, llm_result: Dict) -> ProcessedEmail:
        """Create a processed email from NLP and LLM results."""
        # Ensure date is in UTC
        email_date = self._ensure_utc_date(email.date)
        
        # Get priority score and level
        try:
            priority_score, priority_level = self.priority_calculator.score(
                email.sender,
                nlp_result,
                llm_result
            )
        except Exception as e:
            self.logger.warning(f"Priority calculation failed for email {email.id}, using defaults: {e}")
            priority_score = 30
            priority_level = "LOW"
            
        return ProcessedEmail(
            id=email.id,
            subject=email.subject,
            sender=email.sender,
            body=email.body,
            date=email_date,
            urgency=nlp_result.get('is_urgent', False),
            entities=nlp_result.get('entities', {}),
            key_phrases=nlp_result.get('key_phrases', []),
            sentence_count=nlp_result.get('sentence_count', 0),
            sentiment_indicators=nlp_result.get('sentiment_indicators', {}),
            structural_elements=nlp_result.get('structural_elements', {}),
            needs_action=llm_result.get('needs_action', False),
            category=llm_result.get('category', 'Informational'),
            action_items=llm_result.get('action_items', []),
            summary=llm_result.get('summary', 'No summary available'),
            priority=priority_score,
            priority_level=priority_level,
            custom_categories=llm_result.get('custom_categories', {})
        )

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