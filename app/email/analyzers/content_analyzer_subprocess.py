"""Content analyzer that uses subprocess for memory isolation from SpaCy."""

import asyncio
import logging
import os
import re
import time
from typing import Dict, List, Optional

# Import our SubprocessNLPAnalyzer
from .subprocess_nlp import SubprocessNLPAnalyzer
from ..models.analysis_settings import ProcessingConfig

class ContentAnalyzerSubprocess:
    """Analyzes text using SpaCy in isolated subprocesses to prevent memory leaks."""

    # Pre-compile all regex patterns for local operations
    POSITIVE_PATTERNS = {
        'gratitude': re.compile(r'\b(thank|thanks|grateful|appreciate|appreciated)\b'),
        'positive': re.compile(r'\b(great|excellent|good|wonderful|fantastic|amazing|helpful|pleased|happy|excited)\b'),
        'agreement': re.compile(r'\b(agree|approved|confirmed|sounds good|perfect)\b')
    }
    
    NEGATIVE_PATTERNS = {
        'urgency': re.compile(r'\b(urgent|asap|emergency|immediate|critical)\b'),
        'dissatisfaction': re.compile(r'\b(disappointed|concerned|worried|unfortunately|issue|problem|error|failed|wrong)\b'),
        'demand': re.compile(r'\b(must|need|require|mandatory|asap)\b')
    }

    def __init__(self, nlp_model=None):
        """Initialize the ContentAnalyzerSubprocess.
        
        Args:
            nlp_model: Ignored, included for compatibility with original ContentAnalyzer
        """
        self.logger = logging.getLogger(__name__)
        
        # Create the subprocess analyzer
        self.nlp_analyzer = SubprocessNLPAnalyzer()
        
        # Configure batch processing
        self.batch_size = 5
        
        self.logger.info(
            f"ContentAnalyzerSubprocess initialized\n"
            f"    Using isolated subprocess for memory management\n"
            f"    Batch size: {self.batch_size}"
        )

    async def analyze_batch(self, texts: List[str]) -> List[Dict]:
        """Analyze a batch of texts efficiently using subprocess isolation."""
        from app.utils.memory_utils import log_memory_usage

        log_memory_usage(self.logger, "ContentAnalyzer Batch Start")
        
        try:
            start_time = time.time()
            self.logger.info(
                f"Starting batch NLP analysis of {len(texts)} texts\n"
                f"    Using subprocess isolation\n"
                f"    Batch size: {self.batch_size}"
            )
            
            # Process texts in isolated subprocess
            nlp_results = await self.nlp_analyzer.analyze_batch(texts)
            
            # Format results to match original ContentAnalyzer output
            results = []
            
            # Make sure the length of results and texts match
            if len(nlp_results) != len(texts):
                self.logger.warning(
                    f"Mismatch between input texts ({len(texts)}) and NLP results ({len(nlp_results)}). "
                    f"Using default responses for any missing results."
                )
                # Extend nlp_results if shorter than texts
                if len(nlp_results) < len(texts):
                    nlp_results.extend([{}] * (len(texts) - len(nlp_results)))
                # Truncate if longer (shouldn't happen normally)
                elif len(nlp_results) > len(texts):
                    nlp_results = nlp_results[:len(texts)]
            
            for i, nlp_result in enumerate(nlp_results):
                try:
                    # Get the corresponding text safely
                    text = texts[i] if i < len(texts) else ""
                    
                    # Check if the subprocess returned an error
                    if "error" in nlp_result and not nlp_result.get("entities"):
                        self.logger.error(f"Error in subprocess NLP: {nlp_result['error']}")
                        results.append(self._create_error_response())
                        continue
                    
                    # Convert the subprocess result to expected format
                    # Ensure we include all needed fields from the original ContentAnalyzer
                    result = {
                        'entities': nlp_result.get('entities', {}),
                        'key_phrases': nlp_result.get('key_phrases', []),
                        'sentence_count': nlp_result.get('sentence_count', 0),
                        'urgency': self._check_urgency(text.lower()) if text else False,
                        'sentiment_analysis': {
                            'scores': {
                                'positive': 0.5 if nlp_result.get('sentiment', {}).get('positive', False) else 0.0,
                                'negative': 0.5 if nlp_result.get('sentiment', {}).get('negative', False) else 0.0,
                                'patterns': nlp_result.get('sentiment', {}).get('patterns', {})
                            },
                            'is_positive': nlp_result.get('sentiment', {}).get('positive', False),
                            'is_strong_sentiment': False,  # Default value
                            'has_gratitude': nlp_result.get('sentiment', {}).get('patterns', {}).get('gratitude', False),
                            'has_dissatisfaction': nlp_result.get('sentiment', {}).get('patterns', {}).get('dissatisfaction', False)
                        },
                        'email_patterns': {
                            'is_bulk': False,  # Default value
                            'is_automated': False,  # Default value
                            'bulk_indicators': [],
                            'automated_indicators': []
                        },
                        'questions': {
                            'has_questions': len(nlp_result.get('questions', [])) > 0,
                            'direct_questions': nlp_result.get('questions', []),
                            'rhetorical_questions': [],  # Not implemented in subprocess
                            'request_questions': [],  # Not implemented in subprocess
                            'question_count': len(nlp_result.get('questions', []))
                        },
                        'time_sensitivity': {
                            'has_deadline': nlp_result.get('has_deadline', False),
                            'deadline_phrases': [],  # Not fully implemented
                            'time_references': []  # Not fully implemented
                        },
                        'structural_elements': {
                            'verbs': [],  # Simplified
                            'named_entities_categories': list(set(nlp_result.get('entities', {}).values())),
                            'dependencies': []  # Simplified
                        }
                    }
                    
                    results.append(result)
                except Exception as e:
                    self.logger.error(f"Error processing result {i}: {e}")
                    results.append(self._create_error_response())
            
            processing_time = time.time() - start_time
            self.logger.info(
                f"NLP Analysis completed - Subprocess: {processing_time:.2f}s "
                f"(avg {processing_time/len(texts):.3f}s/text)"
            )
            
            log_memory_usage(self.logger, "ContentAnalyzer Batch Complete")
            return results
            
        except Exception as e:
            self.logger.error(f"Batch analysis failed: {str(e)}")
            return [self._create_error_response() for _ in texts]

    def _create_error_response(self) -> Dict:
        """Create a default response for error cases."""
        return {
            'entities': {},
            'key_phrases': [],
            'urgency': False,
            'sentence_count': 0,
            'sentiment_analysis': {
                'scores': {'positive': 0.5, 'negative': 0.5, 'patterns': {}},
                'is_positive': False,
                'is_strong_sentiment': False,
                'has_gratitude': False,
                'has_dissatisfaction': False
            },
            'email_patterns': {
                'is_bulk': False,
                'is_automated': False,
                'bulk_indicators': [],
                'automated_indicators': []
            },
            'questions': {
                'has_questions': False,
                'direct_questions': [],
                'rhetorical_questions': [],
                'request_questions': [],
                'question_count': 0
            },
            'time_sensitivity': {
                'has_deadline': False,
                'deadline_phrases': [],
                'time_references': []
            },
            'structural_elements': {
                'verbs': [],
                'named_entities_categories': [],
                'dependencies': []
            }
        }

    def _check_urgency(self, text_lower: str) -> bool:
        """Checks if the text contains urgency keywords."""
        config = ProcessingConfig()
        # Clean the text by replacing special characters with spaces
        cleaned_text = re.sub(r'[^\w\s]', ' ', text_lower)
        words = cleaned_text.split()
        
        # Check for exact matches first
        if config.URGENCY_KEYWORDS & set(words):
            return True
            
        # Check for words that start with urgency keywords
        return any(
            word.startswith(keyword)
            for word in words
            for keyword in config.URGENCY_KEYWORDS
        ) 