"""Email processing module.

This module handles the processing and analysis of emails, combining
various analyzers and processors to extract meaningful information.
"""

import logging
from typing import List, Any
from datetime import datetime

from .email_parsing import EmailMetadata
from ..analyzers.semantic_analyzer import SemanticAnalyzer
from ..analyzers.content_analyzer import ContentAnalyzer
from ..utils.priority_scoring import PriorityScorer
from ..models.processed_email import ProcessedEmail
from ..models.exceptions import EmailProcessingError

class EmailProcessor:
    """Processes emails through various analyzers and combines results."""
    
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

    async def analyze_recent_emails(self, days_back: int = 1) -> List[ProcessedEmail]:
        """
        Fetch and analyze recent emails.
        
        Args:
            days_back: Number of days to look back
            
        Returns:
            List of processed emails with analysis results
        """
        try:
            raw_emails = await self.email_client.fetch_emails(days_back)
            parsed_emails = []
            
            for email in raw_emails:
                parsed = self.parser.extract_metadata(email)
                if parsed:
                    parsed_emails.append(parsed)
            
            return await self.analyze_parsed_emails(parsed_emails)
            
        except Exception as e:
            self.logger.error(f"Error analyzing recent emails: {e}")
            raise

    async def analyze_parsed_emails(self, parsed_emails: List[EmailMetadata]) -> List[ProcessedEmail]:
        """
        Analyze parsed emails using all available analyzers.
        
        Args:
            parsed_emails: List of parsed EmailMetadata objects
            
        Returns:
            List of ProcessedEmail objects with complete analysis
        """
        processed_emails = []
        
        for email_data in parsed_emails:
            try:
                # Debug logging
                self.logger.info(f"Processing email: {email_data.sender}")
                
                # Extract text content and headers
                text_content = email_data.body
                #headers = email_data.headers
                
                # Debug logging for headers
                #self.logger.info(f"Email headers: {headers.keys()}")
                
                # Run text analysis
                text_analysis = self.text_analyzer.analyze(text_content)
                print(f"Text analysis complete")
                # Prepare data for LLM analysis
                # llm_input = {
                #     'subject': email_data.subject,
                #     'body': text_content,
                #     'from': email_data.sender
                #     #'to': email_data.recipient
                # }

                #print(f"LLM input: {llm_input.get('subject')}")
                
                # Run LLM analysis
                llm_analysis = await self.llm_analyzer.analyze(email_data, text_analysis)
                print(f"LLM analysis complete")
                
                # Calculate priority
                #sender = email_data.sender
                priority_score, priority_level = self.priority_calculator.score(
                    email_data.sender,
                    text_analysis,
                    llm_analysis
                )
                
                # Create processed email object with safe dictionary access
                processed_email = ProcessedEmail(
                    id=email_data.id,
                    subject=email_data.subject,
                    sender=email_data.sender,
                    #recipient=headers.get('to', ''),
                    body=text_content,
                    date=email_data.date or datetime.now(),

                    urgency=text_analysis.get('urgency', False),
                    entities=text_analysis.get('entities', {}),
                    key_phrases=text_analysis.get('key_phrases', []),
                    sentence_count=text_analysis.get('sentence_count', 0),
                    sentiment_indicators=text_analysis.get('sentiment_indicators', {}),
                    structural_elements=text_analysis.get('structural_elements', {}),

                    needs_action=llm_analysis.get('needs_action', False),
                    category=llm_analysis.get('category', 'uncategorized'),
                    action_items=llm_analysis.get('action_items', []),
                    summary=llm_analysis.get('summary', ''),
                    
                    #has_attachments=email_data.has_attachments
                    priority=priority_score,
                    priority_level=priority_level
                )
                
                processed_emails.append(processed_email)
                self.logger.info(f"Successfully processed email {email_data.id}")
                
            except Exception as e:
                self.logger.error(f"Error processing email {email_data.id}: {e}")
                continue
        
        return processed_emails

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