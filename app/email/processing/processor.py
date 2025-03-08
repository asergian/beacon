"""Email processing module with analytics tracking."""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
import time
from flask import session, current_app
import json

from app.models.activity import log_activity
from ..parsing.parser import EmailMetadata
from ..analyzers.semantic.analyzer import SemanticAnalyzer
from ..analyzers.content.core.nlp_analyzer import ContentAnalyzer
from ..utils.priority_scorer import PriorityScorer
from ..models.processed_email import ProcessedEmail
from ..models.exceptions import EmailProcessingError
from ..models.analysis_command import AnalysisCommand
from app.utils.memory_profiling import log_memory_usage, log_memory_cleanup

class EmailProcessor:
    """Handles the processing and analysis of emails.
    
    This class orchestrates the email processing pipeline, including parsing raw emails,
    analyzing them with NLP and LLM models, and generating insights. It handles both
    batch and individual email processing with comprehensive error handling.
    
    Attributes:
        email_client: Client for fetching emails from the email provider
        text_analyzer: Component for NLP analysis of email content
        llm_analyzer: Component for semantic analysis using LLM
        priority_calculator: Component for calculating email priority scores
        parser: Component for parsing raw emails into structured metadata
        logger: Logger instance for tracking processing events
        processed_count: Counter for total emails processed
    """
    
    def __init__(
        self,
        email_client: Any,  # Can be either EmailConnection or GmailClient
        text_analyzer: Any,  # ContentAnalyzer
        llm_analyzer: Any,  # SemanticAnalyzer
        priority_calculator: Any,  # PriorityScorer
        parser: Any  # EmailParser
    ):
        """Initialize the email processor with its components.
        
        Args:
            email_client: Client for fetching emails from the provider
            text_analyzer: Component for NLP analysis
            llm_analyzer: Component for LLM-based semantic analysis
            priority_calculator: Component for scoring email priority
            parser: Component for parsing raw emails
        """
        self.email_client = email_client
        self.text_analyzer = text_analyzer
        self.llm_analyzer = llm_analyzer
        self.priority_calculator = priority_calculator
        self.parser = parser
        self.logger = logging.getLogger(__name__)
        self.processed_count = 0  # Track number of processed emails

    # =========================================================================
    # Public Methods
    # =========================================================================

    async def analyze_recent_emails(self, command: AnalysisCommand, user_id: Optional[int] = None) -> List[ProcessedEmail]:
        """Analyze recent emails from the email provider.
        
        Fetches recent emails based on the command parameters, parses them, 
        and delegates to analyze_parsed_emails for detailed analysis.
        
        Args:
            command: Configuration parameters for the analysis including days_back
            user_id: Optional user ID for tracking and personalization
            
        Returns:
            List of processed emails with analysis results
            
        Raises:
            EmailProcessingError: If any part of the processing pipeline fails
        """
        try:
            start_time = time.time()
            self.logger.info(f"Processing recent emails for user ID: {user_id}")
            
            # Fetch emails
            raw_emails = await self.email_client.fetch_emails(command.days_back)
            self.logger.info(f"Fetched {len(raw_emails)} raw emails")
            
            # Parse emails and collect stats
            parsed_emails, stats = self._parse_raw_emails(raw_emails)
            
            # Delegate to analyze_parsed_emails for processing
            processed_emails = await self.analyze_parsed_emails(
                parsed_emails=parsed_emails,
                user_id=user_id
            )
            
            # Complete stats and log activity
            stats['successfully_analyzed'] = len(processed_emails)
            stats['processing_time_ms'] = round((time.time() - start_time) * 1000)
            
            # Log activity if we have a user
            if user_id:
                self._log_email_processing_activity(user_id, processed_emails, stats)
                    
            return processed_emails
            
        except Exception as e:
            self.logger.error(f"Email processing failed: {e}")
            raise EmailProcessingError(f"Email processing failed: {str(e)}")

    async def analyze_parsed_emails(self, parsed_emails: List[EmailMetadata], user_id: Optional[int] = None, ai_enabled: Optional[bool] = None) -> List[ProcessedEmail]:
        """Analyze already parsed emails using NLP and LLM models.
        
        Processes a list of parsed email metadata objects through the analysis pipeline,
        including NLP analysis, LLM analysis (if enabled), and fallback processing if needed.
        
        Args:
            parsed_emails: List of parsed email metadata objects
            user_id: Optional user ID for tracking and personalization
            ai_enabled: Whether to enable AI features (defaults to True if None)
            
        Returns:
            List of processed emails with full analysis results
            
        Raises:
            Exception: If the batch processing fails
        """
        # Start timing
        start_time = time.time()
        
        # Track how many emails we've processed
        self.processed_count += len(parsed_emails)
        
        # Log the batch size and user ID for analytics
        self.logger.info(f"Starting batch analysis of {len(parsed_emails)} emails for user {user_id}")
        
        # Keep only essential batch start memory logging
        log_memory_usage(self.logger, "Email Batch Start")
        
        try:
            # Process emails in chunks to avoid memory issues
            email_batch = parsed_emails
            
            # Step 1: Run NLP analysis
            nlp_results = await self._perform_nlp_analysis(email_batch)
            
            # Step 2: Run LLM analysis if enabled
            processed_emails = []
            if ai_enabled is not False:  # Default to True if not specified
                processed_emails = await self._perform_llm_analysis(email_batch, nlp_results)
            
            # Step 3: Fall back to basic processing if needed
            if not processed_emails and email_batch:
                processed_emails = self._perform_fallback_processing(email_batch, nlp_results)
        
        except Exception as e:
            self.logger.error(f"Email batch processing failed: {e}")
            raise
        
        self.logger.info(f"Completed batch analysis of {len(processed_emails)} emails")
        
        # Log memory at batch end - keep this for overall batch memory tracking
        log_memory_usage(self.logger, "Email Batch End")
        
        # Keep these cleanup steps which are important for memory management
        log_memory_cleanup(self.logger, "After Email Processing")
        
        return processed_emails

    # =========================================================================
    # Private Methods - Email Fetching and Parsing
    # =========================================================================

    def _parse_raw_emails(self, raw_emails: List[Dict]) -> Tuple[List[EmailMetadata], Dict]:
        """Parse raw emails into EmailMetadata objects and collect stats.
        
        Args:
            raw_emails: List of raw email data from the email client
            
        Returns:
            Tuple containing:
                - List of parsed EmailMetadata objects
                - Dictionary of processing statistics
        """
        stats = {
            'emails_fetched': len(raw_emails),
            'successfully_parsed': 0,
            'failed_parsing': 0
        }
        
        parsed_emails = []
        for raw_email in raw_emails:
            try:
                parsed_email = self.parser.extract_metadata(raw_email)
                if parsed_email:
                    stats['successfully_parsed'] += 1
                    parsed_emails.append(parsed_email)
                else:
                    stats['failed_parsing'] += 1
            except Exception as e:
                self.logger.error(f"Email parsing failed: {e}")
                stats['failed_parsing'] += 1
        
        return parsed_emails, stats

    # =========================================================================
    # Private Methods - Analysis Pipeline
    # =========================================================================

    async def _perform_nlp_analysis(self, email_batch: List[EmailMetadata]) -> List[Dict]:
        """Perform Natural Language Processing analysis on a batch of emails.
        
        Extracts entities, key phrases, sentiment, and other text features
        from the email bodies.
        
        Args:
            email_batch: List of email metadata objects
            
        Returns:
            List of NLP analysis results dictionaries
        """
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
            
            return nlp_results
        
        except Exception as e:
            self.logger.error(f"Batch NLP processing failed: {e}")
            # Create default response for failed NLP processing
            return [{}] * len(email_batch)

    async def _perform_llm_analysis(self, email_batch: List[EmailMetadata], nlp_results: List[Dict]) -> List[ProcessedEmail]:
        """Perform LLM analysis on emails with their NLP results.
        
        Uses large language models to analyze emails for deeper semantic understanding,
        including categorization, action item extraction, and summary generation.
        
        Args:
            email_batch: List of email metadata objects
            nlp_results: List of NLP analysis results
            
        Returns:
            List of processed emails with full analysis
        """
        processed_emails = []
        
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
        
        return processed_emails

    def _perform_fallback_processing(self, email_batch: List[EmailMetadata], nlp_results: List[Dict]) -> List[ProcessedEmail]:
        """Process emails with just NLP results when LLM processing fails.
        
        Creates basic processed emails using only NLP analysis results
        when the LLM analysis fails or is disabled.
        
        Args:
            email_batch: List of email metadata objects
            nlp_results: List of NLP analysis results
            
        Returns:
            List of processed emails with basic analysis
        """
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
        
        return processed_emails

    # =========================================================================
    # Private Methods - Email Processing Helpers
    # =========================================================================

    def _create_processed_email(self, email: EmailMetadata, nlp_result: Dict, llm_result: Dict) -> ProcessedEmail:
        """Create a processed email from NLP and LLM results.
        
        Combines the original email metadata with analysis results to create
        a fully processed email with all insights.
        
        Args:
            email: Original email metadata
            nlp_result: Results from NLP analysis
            llm_result: Results from LLM analysis (may be empty)
            
        Returns:
            Fully processed email with all analysis results
        """
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

    def _ensure_utc_date(self, date: datetime) -> datetime:
        """Ensure a datetime is in UTC timezone.
        
        Args:
            date: The datetime to convert
            
        Returns:
            The datetime in UTC timezone
        """
        if date.tzinfo is None:
            return date.replace(tzinfo=timezone.utc)
        return date.astimezone(timezone.utc)

    def _get_priority_level(self, score: int) -> str:
        """Convert numerical priority score to level.
        
        Args:
            score: Numerical priority score (0-100)
            
        Returns:
            String priority level ('HIGH', 'MEDIUM', or 'LOW')
        """
        if score >= 80:
            return 'HIGH'
        elif score >= 50:
            return 'MEDIUM'
        else:
            return 'LOW'

    # =========================================================================
    # Private Methods - Utility Methods
    # =========================================================================

    def _log_email_processing_activity(self, user_id: int, processed_emails: List[ProcessedEmail], stats: Dict) -> None:
        """Log email processing activity for a user.
        
        Args:
            user_id: The ID of the user
            processed_emails: The list of processed emails
            stats: Processing statistics to log
        """
        try:
            self.logger.info(f"Logging email processing activity for user {user_id}")
            log_activity(
                user_id=user_id,
                activity_type='email_processing',
                description=f"Processed {len(processed_emails)} emails",
                metadata={
                    'processing_stats': stats
                }
            )
        except Exception as e:
            self.logger.error(f"Failed to log email processing activity: {e}")


# =========================================================================
# Exception Classes
# =========================================================================

class EmailProcessingError(Exception):
    """Base class for email processing errors."""
    pass


class LLMProcessingError(EmailProcessingError):
    """Raised when LLM processing fails."""
    pass


class NLPProcessingError(EmailProcessingError):
    """Raised when NLP processing fails."""
    pass