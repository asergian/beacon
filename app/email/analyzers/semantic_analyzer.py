import json
import logging
from typing import Dict
from flask import g

#from ..models.processed_email import ProcessedEmail
from ..core.email_parsing import EmailMetadata
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
        
    def _estimate_token_count(self, text: str) -> int:
        """Estimates the number of tokens in a given text."""
        # A rough estimate: 1 token is approximately 4 characters or 0.75 words
        return len(text.split())  # This is a simple word count

    async def analyze(self, metadata: EmailMetadata, nlp_results: Dict) -> Dict:
        """Analyzes the email using OpenAI's model."""
        self.logger.info("Starting analysis of email: %s", metadata.subject[:50])
        try:
            client = g.get('async_openai_client')
            if not client:
                self.logger.error("OpenAI client not available.")
                raise LLMProcessingError("OpenAI client not available")

            prompt = self._create_analysis_prompt(metadata, nlp_results)
            
            # Log the token count
            token_count = self._estimate_token_count(prompt)
            self.logger.info("Estimated token count for LLM request: %d", token_count)

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

    def _create_analysis_prompt(self, metadata: EmailMetadata, nlp_results: Dict) -> str:
        """Creates a prompt for LLM analysis."""
        # Truncate body to ~800 words (roughly 1000 tokens)
        truncated_body = ' '.join(metadata.body.split()[:800])
        if len(metadata.body.split()) > 800:
            truncated_body += " [truncated]"

        # Simplify NLP results to only essential information
        simplified_nlp = {
            'entities': dict(list(nlp_results.get('entities', {}).items())[:5]),  # Top 5 entities
            'key_phrases': nlp_results.get('key_phrases', [])[:3],  # Top 3 phrases
            'urgency': nlp_results.get('urgency', False),
            'sentence_count': nlp_results.get('sentence_count', 0)
        }

        return """You are an email analysis assistant. Analyze the following email and provide a structured assessment to help prioritize inbox management.

        EMAIL CONTENT
        -------------
        Subject: {subject}
        From: {sender}
        Body: {truncated_body}

        CONTEXT
        -------
        NLP Analysis Results: {nlp_results}

        TASK
        ----
        Analyze this email and provide a JSON response with the following fields:

        1. needs_action (boolean):
           - true if the email requires a response or action
           - false if it's purely informational

        2. category (string, exactly one of):
           - "Work" - business/professional communications
           - "Personal" - friends, family, personal matters
           - "Promotions" - marketing, sales, newsletters
           - "Informational" - notifications, updates, reports

        3. action_items (array of objects):
           - Each object must have:
             * "description": clear, actionable task
             * "due_date": YYYY-MM-DD or null if no specific deadline
           - Leave empty array if no actions needed

        4. summary (string):
           - 2-3 sentences maximum
           - Focus on key points and decisions needed

        5. priority (integer 0-100):
           - 0-20: Can be ignored/archived
           - 21-40: Low priority
           - 41-60: Medium priority
           - 61-80: High priority
           - 81-100: Urgent/immediate attention

        OUTPUT FORMAT
        ------------
        Return only valid JSON matching this schema:
        {{
            "needs_action": boolean,
            "category": string,
            "action_items": array,
            "summary": string,
            "priority": integer
        }}""".format(
            subject=metadata.subject,
            sender=metadata.sender,
            truncated_body=truncated_body,
            nlp_results=json.dumps(simplified_nlp, indent=2)
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