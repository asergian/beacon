"""Email processing system that analyzes emails using NLP and LLM capabilities.

This module provides classes and methods to analyze emails, extract key information,
calculate priorities, and handle errors effectively. It utilizes OpenAI's language model
and spaCy for natural language processing.
"""

import asyncio
import json
import logging
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
from abc import ABC, abstractmethod

import spacy
from openai import AsyncOpenAI
from flask import g

from .email_connection import IMAPEmailClient, IMAPConnectionError
from .email_parsing import EmailParser, EmailMetadata, EmailParsingError

@dataclass
class AnalyzedEmail:
    """Represents a fully analyzed email with all extracted information."""
    subject: str
    sender: str
    body: str
    date: datetime
    needs_action: bool
    category: str
    action_items: List[Dict[str, Optional[str]]]
    summary: str
    priority: int

@dataclass
class AnalyzerConfig:
    #URGENCY_KEYWORDS: set = field(default_factory=lambda: {'urgent', 'asap', 'deadline', 'immediate', 'priority'})
    URGENCY_KEYWORDS = {'urgent', 'asap', 'deadline', 'immediate', 'priority'}
    BASE_PRIORITY_SCORE: int = 50
    VIP_SCORE_BOOST: int = 20
    URGENCY_SCORE_BOOST: int = 15
    ACTION_SCORE_BOOST: int = 10
    MAX_PRIORITY: int = 100

class OpenAIAnalyzer:
    """Analyzes emails using OpenAI's language model."""

    def __init__(self, model: str = "gpt-4o-mini"):
        """Initializes the OpenAIAnalyzer.

        Args:
            model (str): The model to use for analysis.
        """
        self.model = model
        self.logger = logging.getLogger(__name__)
        
    async def analyze(self, metadata: EmailMetadata, nlp_results: Dict) -> Dict:
        """Analyzes the email using OpenAI's model.

        Args:
            metadata (EmailMetadata): Metadata of the email.
            nlp_results (Dict): Results from NLP analysis.

        Returns:
            Dict: Analysis results including needs_action, category, action_items, summary, and priority.

        Raises:
            LLMAnalysisError: If the analysis fails.
        """
        self.logger.info("Starting analysis of email.")
        try:
            client = g.get('async_openai_client')
            if not client:
                self.logger.error("OpenAI client not available.")
                raise LLMAnalysisError("OpenAI client not available")

            prompt = self._create_analysis_prompt(metadata, nlp_results)
            self.logger.debug(f"Generated prompt: {prompt}")
            response = await client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            self.logger.info("Received response from OpenAI.")
            return self._parse_response(response.choices[0].message.content)
        except Exception as e:
            self.logger.error(f"LLM analysis failed: {e}")
            raise LLMAnalysisError(str(e))

    def _create_analysis_prompt(self, metadata: EmailMetadata, nlp_results: Dict) -> str:
        """Creates a prompt for LLM analysis based on email metadata and NLP results.

        Args:
            metadata (EmailMetadata): Metadata of the email.
            nlp_results (Dict): Results from NLP analysis.

        Returns:
            str: The generated prompt for LLM analysis.
        """
        return (
            f"Analyze the following email and provide a structured JSON response:\n\n"
            f"Subject: {metadata.subject}\n"
            f"Sender: {metadata.sender}\n"
            f"Body: {metadata.body}\n"
            f"NLP Results: {nlp_results}\n\n"
            f"Please extract the following information:\n"
            f"- needs_action (boolean)\n"
            f"- category (string)\n"
            f"- action_items (list of objects with keys: 'description' and 'due_date')\n"
            f"- summary (string)\n"
            f"- priority (integer)\n"
            f"Return the response in JSON format."
        )

    def _parse_response(self, response_content: str) -> Dict:
        """Parses the response content from the LLM.

        Args:
            response_content (str): The content of the response from the LLM.

        Returns:
            Dict: Parsed response data.

        Raises:
            LLMAnalysisError: If the response is empty or invalid.
        """
        if not response_content:
            self.logger.error("Received empty response from OpenAI.")
            raise LLMAnalysisError("Received empty response from OpenAI.")
        
        try:
            response_data = response_content.strip().lstrip('```json').rstrip('```').strip()
            response_data = json.loads(response_data)
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to decode JSON response: {e}")
            raise LLMAnalysisError("Invalid JSON response from OpenAI.")
        
        return {
            'needs_action': response_data.get('needs_action', False),
            'category': response_data.get('category', 'general'),
            'action_items': response_data.get('action_items', []),
            'summary': response_data.get('summary', ''),
            'priority': response_data.get('priority', 0)
        }

class TextAnalyzer:
    """Analyzes text using spaCy for entities and urgency."""

    def __init__(self, nlp_model: spacy.language.Language):
        """Initializes the TextAnalyzer.

        Args:
            nlp_model (spacy.language.Language): The spaCy NLP model to use.
        """
        self.nlp = nlp_model
        
    def analyze(self, text: str) -> Dict:
        """Analyzes the text for entities and urgency.

        Args:
            text (str): The text to analyze.

        Returns:
            Dict: Contains extracted entities, key phrases, and urgency status.
        """
        doc = self.nlp(text)
        return {
            'entities': {ent.label_: ent.text for ent in doc.ents},
            'key_phrases': [chunk.text for chunk in doc.noun_chunks],
            'is_urgent': self._check_urgency(text)
        }
        
    def _check_urgency(self, text: str) -> bool:
        """Checks if the text contains urgency keywords.

        Args:
            text (str): The text to check for urgency.

        Returns:
            bool: True if urgent keywords are found, False otherwise.
        """
        return bool(AnalyzerConfig.URGENCY_KEYWORDS & set(text.lower().split()))

class PriorityCalculator:
    """Calculates priority scores for emails based on various factors."""

    def __init__(self, vip_senders: Set[str], config: AnalyzerConfig):
        """Initializes the PriorityCalculator.

        Args:
            vip_senders (Set[str]): Set of VIP sender addresses.
            config (AnalyzerConfig): Configuration for priority calculation.
        """
        self.vip_senders = vip_senders
        self.config = config
        
    def calculate(self, sender: str, nlp_results: Dict, llm_results: Dict) -> int:
        """Calculates the priority score for an email.

        Args:
            sender (str): The sender of the email.
            nlp_results (Dict): Results from NLP analysis.
            llm_results (Dict): Results from LLM analysis.

        Returns:
            int: The calculated priority score.
        """
        score = self.config.BASE_PRIORITY_SCORE
        
        if sender in self.vip_senders:
            score += self.config.VIP_SCORE_BOOST
        if nlp_results['is_urgent']:
            score += self.config.URGENCY_SCORE_BOOST
        if llm_results['needs_action']:
            score += self.config.ACTION_SCORE_BOOST
            
        return min(score, self.config.MAX_PRIORITY)

class EmailAnalyzer:
    """Analyzes emails using NLP and LLM to extract key information and priorities."""

    def __init__(
        self,
        email_client: IMAPEmailClient,
        text_analyzer: TextAnalyzer,
        llm_analyzer: OpenAIAnalyzer,
        priority_calculator: PriorityCalculator,
        parser: EmailParser
    ):
        """Initializes the EmailAnalyzer.

        Args:
            email_client (IMAPEmailClient): The email client to fetch emails.
            text_analyzer (TextAnalyzer): The text analyzer for NLP.
            llm_analyzer (OpenAIAnalyzer): The LLM analyzer for email analysis.
            priority_calculator (PriorityCalculator): The calculator for email priority.
            parser (EmailParser): The parser for extracting email metadata.
        """
        self.email_client = email_client
        self.text_analyzer = text_analyzer
        self.llm_analyzer = llm_analyzer
        self.priority_calculator = priority_calculator
        self.parser = parser
        self.logger = logging.getLogger(__name__)

    async def analyze_recent_emails(self, days_back: int = 1) -> List[AnalyzedEmail]:
        """Analyzes recent emails within the specified number of days.

        Args:
            days_back (int): The number of days to look back for emails.

        Returns:
            List[AnalyzedEmail]: A list of analyzed email objects.
        """
        async with self:  # Uses context manager for cleanup
            raw_emails = await self.email_client.fetch_emails(days=days_back)
            results = await asyncio.gather(
                *[self._analyze_single_email(email) for email in raw_emails],
                return_exceptions=True
            )
            return [r for r in results if isinstance(r, AnalyzedEmail)]

    async def _analyze_single_email(self, raw_email: Dict) -> AnalyzedEmail:
        """Analyzes a single email and returns an AnalyzedEmail object.

        Args:
            raw_email (Dict): The raw email data.

        Returns:
            AnalyzedEmail: The analyzed email object.

        Raises:
            EmailAnalysisError: If the analysis fails.
        """
        try:
            self.logger.info("Starting analysis for email: %s", raw_email.get('subject', 'No Subject'))
            metadata = self.parser.extract_metadata(raw_email)
            self.logger.info("Extracted metadata")

            nlp_results = self.text_analyzer.analyze(metadata.body)
            self.logger.info("NLP analysis results: %s", nlp_results)

            llm_results = await self.llm_analyzer.analyze(metadata, nlp_results)
            self.logger.info("LLM analysis results: %s", llm_results)

            priority = self.priority_calculator.calculate(
                metadata.sender, nlp_results, llm_results
            )
            self.logger.info("Calculated priority for email from %s: %d", metadata.sender, priority)

            return AnalyzedEmail(
                subject=metadata.subject,
                sender=metadata.sender,
                body=metadata.body,
                date=metadata.date,
                needs_action=llm_results['needs_action'],
                category=llm_results['category'],
                action_items=llm_results['action_items'],
                summary=llm_results['summary'],
                priority=priority
            )
        except Exception as e:
            self.logger.error(f"Failed to analyze email: {e}")
            raise EmailAnalysisError(f"Analysis failed: {str(e)}")

    async def __aenter__(self):
        """Enters the asynchronous context for the EmailAnalyzer."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exits the asynchronous context and cleans up resources.

        Args:
            exc_type (type): The exception type, if any.
            exc_val (Exception): The exception value, if any.
            exc_tb (traceback): The traceback object, if any.
        """
        # Cleanup resources
        await self.email_client.close()

class EmailAnalysisError(Exception):
    """Base class for email analysis errors."""
    pass

class LLMAnalysisError(EmailAnalysisError):
    """Raised when LLM analysis fails."""
    pass

class NLPAnalysisError(EmailAnalysisError):
    """Raised when NLP analysis fails."""
    pass