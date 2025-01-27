"""Email processing system that analyzes emails using NLP and LLM capabilities.

This module provides classes and methods to analyze emails, extract key information,
calculate priorities, and handle errors effectively. It utilizes OpenAI's language model
and spaCy for natural language processing.
"""

import asyncio
import logging
from typing import List

from .email_connection import EmailConnection
from .email_parsing import EmailParser, EmailMetadata
from ..analyzers.semantic_analyzer import SemanticAnalyzer
from ..analyzers.content_analyzer import ContentAnalyzer
from ..utils.priority_scoring import PriorityScorer
from ..models.processed_email import ProcessedEmail
from ..models.exceptions import EmailProcessingError

class EmailProcessor:
    """Main coordinator for email analysis process."""
    
    def __init__(
        self,
        email_client: EmailConnection,
        text_analyzer: SemanticAnalyzer,
        llm_analyzer: ContentAnalyzer,
        priority_calculator: PriorityScorer,
        parser: EmailParser
    ):
        self.email_client = email_client
        self.text_analyzer = text_analyzer
        self.llm_analyzer = llm_analyzer
        self.priority_calculator = priority_calculator
        self.parser = parser
        self.logger = logging.getLogger(__name__)

    # async def process_recent_emails(self, days_back: int = 1) -> List[ProcessedEmail]:
    #     """Analyzes recent emails within the specified number of days."""
    #     async with self:
    #         raw_emails = await self.email_client.fetch_emails(days=days_back)
    #         results = await asyncio.gather(
    #             *[self._process_single_email(email) for email in raw_emails],
    #             return_exceptions=True
    #         )
    #         return [r for r in results if isinstance(r, ProcessedEmail)]

    async def process_parsed_emails(self, parsed_emails: List[EmailMetadata]) -> List[ProcessedEmail]:
        """Analyzes a list of already parsed emails."""
        results = await asyncio.gather(
            *[self._process_single_email(email) for email in parsed_emails],
            return_exceptions=True
        )
        return [r for r in results if isinstance(r, ProcessedEmail)]

    async def _process_single_email(self, metadata: EmailMetadata) -> ProcessedEmail:
        """Analyzes a single parsed email."""
        try:
            print(f"Starting processing for email: {metadata.id}")
            self.logger.info("Starting processing for email: %s", metadata.subject[:50])

            nlp_results = self.text_analyzer.analyze(metadata.body)
            self.logger.info("NLP processing - entities: %d, urgent: %s", 
                           len(nlp_results.get('entities', {})), 
                           nlp_results.get('is_urgent', False))

            llm_results = await self.llm_analyzer.analyze(metadata, nlp_results)
            self.logger.info("LLM processing - category: %s, needs_action: %s", 
                           llm_results.get('category'), 
                           llm_results.get('needs_action'))

            priority_score, priority_level = self.priority_calculator.score(
                metadata.sender, nlp_results, llm_results
            )
            self.logger.info("Priority calculated - sender: %s, score: %d, level: %s", 
                           metadata.sender[:30], priority_score, priority_level)

            return ProcessedEmail(
                id=metadata.id,
                subject=metadata.subject,
                sender=metadata.sender,
                body=metadata.body,
                date=metadata.date,
                needs_action=llm_results['needs_action'],
                category=llm_results['category'],
                action_items=llm_results['action_items'],
                summary=llm_results['summary'],
                priority=priority_score,
                priority_level=priority_level
            )
        except Exception as e:
            self.logger.error(f"Failed to process email: {e}")
            raise EmailProcessingError(f"Processing failed: {str(e)}")

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