import json
import logging
from typing import Dict
from flask import g

from ..models.processed_email import ProcessedEmail
from ..models.exceptions import LLMProcessingError

class SemanticAnalyzer:
    """Performs semantic analysis of emails using large language models."""
    
    def __init__(self, model: str = "gpt-4o-mini"):
        """Initializes the SemanticAnalyzer.

        Args:
            model (str): The model to use for analysis.
        """
        self.model = model
        self.logger = logging.getLogger(__name__)
        
    async def analyze(self, metadata: ProcessedEmail, nlp_results: Dict) -> Dict:
        """Analyzes the email using OpenAI's model."""
        self.logger.info("Starting analysis of email: %s", metadata.subject[:50])
        try:
            client = g.get('async_openai_client')
            if not client:
                self.logger.error("OpenAI client not available.")
                raise LLMProcessingError("OpenAI client not available")

            prompt = self._create_analysis_prompt(metadata, nlp_results)
            response = await client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            self.logger.info("Received OpenAI response")
            return self._parse_response(response.choices[0].message.content)
        except Exception as e:
            self.logger.error("LLM processing failed: %s", str(e)[:100])
            raise LLMProcessingError(str(e))

    def _create_analysis_prompt(self, metadata: ProcessedEmail, nlp_results: Dict) -> str:
        """Creates a prompt for LLM analysis."""
        return """Analyze the following email to help the user prioritize their inbox effectively:

        Subject: {subject}
        Sender: {sender}
        Body: {body}
        NLP Results: {nlp_results}

        Please extract the following information:
        - needs_action: boolean
        - category: string (one of Work, Personal, Promotions, Informational)
        - action_items: list of objects with keys: 'description' and 'due_date' (YYYY-MM-DD)
        - summary: string, up to 3 lines
        - priority: integer 0-100
        Return the response in JSON format.""".format(
            subject=metadata.subject,
            sender=metadata.sender,
            body=metadata.body,
            nlp_results=nlp_results
        )

    def _parse_response(self, response_content: str) -> Dict:
        """Parses the response content from the LLM."""
        if not response_content:
            self.logger.error("Received empty response from OpenAI.")
            raise LLMProcessingError("Received empty response from OpenAI.")
        
        try:
            self.logger.debug("Raw response preview: %s...", response_content[:100])
            
            cleaned_content = response_content.strip()
            if cleaned_content.startswith('```json'):
                cleaned_content = cleaned_content.replace('```json', '', 1)
            if cleaned_content.endswith('```'):
                cleaned_content = cleaned_content.rsplit('```', 1)[0]
            cleaned_content = cleaned_content.strip()
            
            response_data = json.loads(cleaned_content)
            
            return {
                'needs_action': bool(response_data.get('needs_action', False)),
                'category': str(response_data.get('category', 'general')),
                'action_items': list(response_data.get('action_items', [])),
                'summary': str(response_data.get('summary', '')),
                'priority': int(response_data.get('priority', 0))
            }
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to decode JSON response: {e}")
            self.logger.error(f"Attempted to parse content: {cleaned_content}")
            raise LLMProcessingError("Invalid JSON response from OpenAI.") 