"""SpaCy-based content analyzer for email text analysis.

This module provides a content analyzer that uses SpaCy for natural language processing
of email texts. It handles entity recognition, sentiment analysis, question detection,
and other text analysis features while managing memory efficiently through batch processing
and model reloading.

Key Features:

- Entity recognition and categorization
- Sentiment analysis
- Question detection and categorization
- Time sensitivity and deadline detection
- Email pattern analysis (bulk, automated)
- Memory-efficient batch processing
- Automatic model reloading to prevent memory leaks

Example::

    analyzer = ContentAnalyzer(nlp_model)
    results = await analyzer.analyze_batch(texts)
    for result in results:
        print(f"Found {len(result['entities'])} entities")
        print(f"Sentiment: {result['sentiment_analysis']}")

Memory Management:

- Batch processing with controlled batch sizes
- Regular garbage collection
- SpaCy document cleanup
- Model reloading after threshold
- Reference clearing
"""

import spacy
from typing import Dict, List, Set
from concurrent.futures import ThreadPoolExecutor
import time
import logging
import asyncio
import gc
from app.utils.memory_profiling import log_memory_usage

from ...base import BaseAnalyzer
from ..utils.spacy_utils import load_optimized_model, cleanup_doc
from ..utils.pattern_matchers import (
    analyze_sentiment,
    detect_email_patterns,
    check_urgency,
    VALID_ENTITY_LABELS,
    HTML_INDICATORS,
    QUESTION_WORDS,
    MODAL_VERBS,
    DEADLINE_WORDS
)
from ..utils.result_formatter import (
    create_error_response,
    format_nlp_result,
    _format_sentiment,
    _format_email_patterns,
    _format_questions,
    _format_time_sensitivity,
    _format_structural_elements
)

class ContentAnalyzer(BaseAnalyzer):
    """SpaCy-based content analyzer for processing email texts.
    
    This class provides methods for analyzing email content using SpaCy NLP,
    with optimizations for memory usage and batch processing. It handles
    entity extraction, sentiment analysis, question detection, and more.
    
    Attributes:
        logger: Logger instance for tracking analyzer operations.
        model_name: Name of the SpaCy model being used.
        nlp: SpaCy language model instance.
        batch_size: Size of batches for processing texts.
        _batch_count: Counter for tracking processed batches.
        _reload_threshold: Number of batches before model reload.
    """

    def __init__(self, nlp_model: spacy.language.Language):
        """Initialize the ContentAnalyzer with SpaCy model and configuration.
        
        Args:
            nlp_model: SpaCy language model to use for text processing.
        """
        self.logger = logging.getLogger(__name__)
        
        # Store model name rather than keeping model instance
        self.model_name = nlp_model.meta['lang'] + '_core_web_sm'
        self._batch_count = 0
        self._reload_threshold = 3  # Reload model every 3 batches
        
        # Load optimized model using spacy_utils
        self.nlp = load_optimized_model()
        
        # Configure batch processing
        self.batch_size = 100
        
        self._log_configuration()

    def _log_configuration(self):
        """Log the current configuration of the analyzer."""
        self.logger.debug(
            f"SpaCy pipeline configuration:\n"
            f"    Model: {self.model_name}\n"
            f"    Enabled components: {[pipe for pipe in self.nlp.pipe_names if pipe not in ['textcat', 'lemmatizer', 'attribute_ruler', 'vectors', 'tok2vec']]}\n"
            f"    Disabled components: ['textcat', 'lemmatizer', 'attribute_ruler', 'vectors', 'tok2vec']\n"
            f"    Max length: {self.nlp.max_length}\n"
            f"    Batch size: {self.batch_size}\n"
            f"    Reload threshold: {self._reload_threshold} batches"
        )

    def _load_nlp_model(self):
        """Load SpaCy model with optimal memory settings.
        
        Forces garbage collection before loading a new model to ensure
        clean memory state.
        """
        gc.collect()
        gc.collect()
        self.nlp = load_optimized_model()

    def _cleanup_doc(self, doc: spacy.tokens.Doc):
        """Safely cleanup SpaCy doc to free memory.
        
        Args:
            doc: SpaCy Doc object to cleanup.
        """
        cleanup_doc(doc)

    async def _process_batch(self, texts: List[str], executor: ThreadPoolExecutor) -> List[spacy.tokens.Doc]:
        """Process a batch of texts using SpaCy in a memory-efficient way.
        
        Args:
            texts: List of texts to process.
            executor: ThreadPoolExecutor for running SpaCy processing.
            
        Returns:
            List of processed SpaCy Doc objects.
            
        This method handles the core SpaCy processing, breaking the texts into
        smaller sub-batches for better memory management.
        """
        loop = asyncio.get_event_loop()
        batch_size = max(1, min(3, len(texts)))  # Reduced from 5 to 3
        batches = [texts[i:i + batch_size] for i in range(0, len(texts), batch_size)]
        
        docs = []
        for batch in batches:
            batch_docs = await loop.run_in_executor(
                executor, 
                lambda b=batch: list(self.nlp.pipe(b, batch_size=self.batch_size))
            )
            docs.extend(batch_docs)
            gc.collect()
        
        return docs

    def _process_entities(self, doc: spacy.tokens.Doc, result: Dict) -> Dict[str, str]:
        """Process entities from a SpaCy document.
        
        Args:
            doc: SpaCy Doc object to process.
            result: Result dictionary to update with entity information.
            
        Returns:
            Dictionary mapping entity text to entity label.
        """
        entity_dict = {}
        for ent in doc.ents:
            if ent.label_ in VALID_ENTITY_LABELS:
                if not any(indicator in ent.text.lower() for indicator in HTML_INDICATORS):
                    entity_dict[ent.text] = ent.label_
                    result['structural_elements']['named_entities_categories'].add(ent.label_)
                if ent.label_ in {'DATE', 'TIME'}:
                    result['time_sensitivity']['time_references'].append(ent.text)
        return entity_dict

    def _process_tokens(self, doc: spacy.tokens.Doc, result: Dict):
        """Process tokens from a SpaCy document.
        
        Args:
            doc: SpaCy Doc object to process.
            result: Result dictionary to update with token information.
        """
        for token in doc:
            if token.pos_ == 'VERB':
                result['structural_elements']['verbs'].add(token.lemma_)
            if token.dep_ in ('ROOT', 'dobj', 'iobj'):
                result['structural_elements']['dependencies'].append((token.text, token.dep_))

    def _process_sentences(self, doc: spacy.tokens.Doc, result: Dict):
        """Process sentences from a SpaCy document.
        
        Args:
            doc: SpaCy Doc object to process.
            result: Result dictionary to update with sentence information.
            
        This method handles sentence counting, question detection, and
        deadline phrase detection.
        """
        for sent in doc.sents:
            result['sentence_count'] += 1
            sent_text = sent.text.strip()
            sent_lower = sent_text.lower()
            
            self._detect_questions(sent, sent_text, result)
            self._detect_deadlines(sent, sent_lower, sent_text, result)

    def _detect_questions(self, sent: spacy.tokens.Span, sent_text: str, result: Dict):
        """Detect and categorize questions in a sentence.
        
        Args:
            sent: SpaCy Span object representing the sentence.
            sent_text: Text of the sentence.
            result: Result dictionary to update with question information.
        """
        if sent_text.endswith('?'):
            sent_tokens = {token.text.lower() for token in sent}
            has_question_word = bool(sent_tokens & QUESTION_WORDS)
            has_modal = bool(sent_tokens & MODAL_VERBS)
            
            if has_modal:
                result['questions']['request_questions'].append(sent_text)
            elif has_question_word:
                result['questions']['direct_questions'].append(sent_text)
            else:
                result['questions']['rhetorical_questions'].append(sent_text)
            
            result['questions']['question_count'] += 1

    def _detect_deadlines(self, sent: spacy.tokens.Span, sent_lower: str, sent_text: str, result: Dict):
        """Detect deadline phrases in a sentence.
        
        Args:
            sent: SpaCy Span object representing the sentence.
            sent_lower: Lowercase version of the sentence text.
            sent_text: Original sentence text.
            result: Result dictionary to update with deadline information.
        """
        if any(word in sent_lower for word in DEADLINE_WORDS):
            has_time = any(ent.label_ in {'DATE', 'TIME'} for ent in sent.ents)
            if has_time:
                result['time_sensitivity']['deadline_phrases'].append(sent_text)
                result['time_sensitivity']['has_deadline'] = True

    def _process_noun_chunks(self, doc: spacy.tokens.Doc, result: Dict):
        """Process noun chunks from a SpaCy document.
        
        Args:
            doc: SpaCy Doc object to process.
            result: Result dictionary to update with noun chunk information.
        """
        if len(result['key_phrases']) < 3:
            for chunk in doc.noun_chunks:
                if not any(indicator in chunk.text.lower() for indicator in HTML_INDICATORS):
                    result['key_phrases'].append(chunk.text)
                    if len(result['key_phrases']) >= 3:
                        break

    def _format_result(self, result: Dict, entity_dict: Dict, sentiment_results: Dict,
                      email_patterns: Dict, is_urgent: bool) -> Dict:
        """Format the analysis results into the final structure.
        
        Args:
            result: Raw result dictionary from analysis.
            entity_dict: Dictionary of extracted entities.
            sentiment_results: Results from sentiment analysis.
            email_patterns: Results from email pattern detection.
            is_urgent: Whether the text is urgent.
            
        Returns:
            Formatted result dictionary with all analysis components.
        """
        return {
            'entities': dict(list(entity_dict.items())[:5]),
            'key_phrases': result['key_phrases'][:3],
            'sentence_count': result['sentence_count'],
            'questions': _format_questions(result['questions']),
            'sentiment_analysis': _format_sentiment(sentiment_results),
            'email_patterns': _format_email_patterns(email_patterns),
            'urgency': is_urgent,
            'time_sensitivity': {
                'has_deadline': result['time_sensitivity']['has_deadline'],
                'deadline_phrases': result['time_sensitivity']['deadline_phrases'][:2],
                'time_references': result['time_sensitivity']['time_references'][:3]
            },
            'structural_elements': {
                'verbs': list(result['structural_elements']['verbs'])[:5],
                'named_entities_categories': list(result['structural_elements']['named_entities_categories'])[:3],
                'dependencies': result['structural_elements']['dependencies'][:3]
            }
        }

    def _process_analyzed_doc(self, doc: spacy.tokens.Doc, text_lower: str) -> Dict:
        """Process a single analyzed document.
        
        Args:
            doc: SpaCy Doc object to process.
            text_lower: Lowercase version of the original text.
            
        Returns:
            Dictionary containing all analysis results.
            
        This method orchestrates the complete analysis of a single document,
        including entity extraction, token processing, sentence analysis,
        and result formatting.
        """
        try:
            # Initialize result structure
            result = {
                'entities': {},
                'key_phrases': [],
                'sentence_count': 0,
                'questions': {
                    'direct_questions': [],
                    'rhetorical_questions': [],
                    'request_questions': [],
                    'question_count': 0
                },
                'time_sensitivity': {
                    'deadline_phrases': [],
                    'time_references': [],
                    'has_deadline': False
                },
                'structural_elements': {
                    'verbs': set(),
                    'named_entities_categories': set(),
                    'dependencies': []
                }
            }
            
            # Process document components
            entity_dict = self._process_entities(doc, result)
            self._process_tokens(doc, result)
            self._process_sentences(doc, result)
            self._process_noun_chunks(doc, result)
            
            # Get additional analysis results
            sentiment_results = analyze_sentiment(text_lower)
            email_patterns = detect_email_patterns(text_lower)
            is_urgent = check_urgency(text_lower)
            
            # Format final result
            formatted_result = self._format_result(
                result, entity_dict, sentiment_results, email_patterns, is_urgent
            )
            
            # Clear large intermediate objects
            entity_dict = None
            
            return formatted_result
            
        except Exception as e:
            self.logger.error(f"Document processing failed: {str(e)}")
            return create_error_response()

    async def analyze_batch(self, texts: List[str]) -> List[Dict]:
        """Analyze a batch of texts efficiently.
        
        Args:
            texts: List of texts to analyze.
            
        Returns:
            List of dictionaries containing analysis results for each text.
            
        This method handles the complete batch processing workflow, including:
        - Memory usage logging
        - Text preprocessing
        - Batch processing with SpaCy
        - Result collection and cleanup
        - Model reloading when needed
        """
        log_memory_usage(self.logger, "ContentAnalyzer Batch Start")
        
        try:
            start_time = time.time()
            self.logger.info(
                f"Starting batch NLP analysis of {len(texts)} texts\n"
                f"    Using Hypercorn worker process\n"
                f"    Batch size: {self.batch_size}"
            )
            
            # Increment batch counter and preprocess texts
            self._batch_count += 1
            texts = [text[:30000] for text in texts]
            texts_lower = [text.lower() for text in texts]
            
            # Process texts in batches
            with ThreadPoolExecutor(max_workers=1) as executor:
                docs = await self._process_batch(texts, executor)
            
            log_memory_usage(self.logger, "After SpaCy Processing")
            pipe_time = time.time() - start_time
            self._log_processing_time(pipe_time, len(texts))
            
            # Process results
            results = []
            for i, (doc, text_lower) in enumerate(zip(docs, texts_lower)):
                try:
                    result = self._process_analyzed_doc(doc, text_lower)
                    results.append(result)
                finally:
                    cleanup_doc(doc)
                    doc = None
                
                if i % 2 == 0:
                    gc.collect()
            
            # Cleanup and logging
            self._cleanup_batch_processing(docs, texts, texts_lower)
            self._log_batch_completion(start_time, pipe_time, len(results))
            
            # Check for model reload
            if self._batch_count >= self._reload_threshold:
                self._reload_model()
            
            return results
            
        except Exception as e:
            self.logger.error(f"Batch analysis failed: {str(e)}")
            raise

    def _cleanup_batch_processing(self, docs, texts, texts_lower):
        """Clean up resources after batch processing.
        
        Args:
            docs: List of SpaCy Doc objects to cleanup.
            texts: List of original texts.
            texts_lower: List of lowercase texts.
        """
        docs = None
        texts = None
        texts_lower = None
        gc.collect()
        gc.collect()
        log_memory_usage(self.logger, "After Document Processing")

    def _reload_model(self):
        """Reload the SpaCy model to prevent memory leaks."""
        self.logger.info(f"Reached reload threshold ({self._reload_threshold} batches) - Reloading SpaCy model")
        self.nlp = None
        gc.collect()
        gc.collect()
        self.nlp = load_optimized_model()
        self._batch_count = 0
        log_memory_usage(self.logger, "After Model Reload")

    def _log_processing_time(self, pipe_time: float, text_count: int):
        """Log SpaCy processing time metrics.
        
        Args:
            pipe_time: Time taken for SpaCy processing.
            text_count: Number of texts processed.
        """
        self.logger.debug(
            f"SpaCy processing completed:\n"
            f"    Total time: {pipe_time:.2f}s\n"
            f"    Average per text: {pipe_time/text_count:.3f}s"
        )

    def _log_batch_completion(self, start_time: float, pipe_time: float, result_count: int):
        """Log batch completion metrics.
        
        Args:
            start_time: Time when batch processing started.
            pipe_time: Time taken for SpaCy processing.
            result_count: Number of results processed.
        """
        total_time = time.time() - start_time
        post_process_time = total_time - pipe_time
        
        self.logger.debug(
            f"NLP Analysis Summary:\n"
            f"    Total time: {total_time:.2f}s\n"
            f"    SpaCy pipe time: {pipe_time:.2f}s\n"
            f"    Post-processing time: {post_process_time:.2f}s\n"
            f"    Average time per text: {total_time/result_count:.3f}s"
        )
        
        self.logger.info(
            f"NLP Analysis completed - SpaCy: {pipe_time:.2f}s, "
            f"Post-processing: {post_process_time:.2f}s, "
            f"Total: {total_time:.2f}s (avg {total_time/result_count:.3f}s/text)"
        )

    def _create_error_response(self) -> Dict:
        """Create a default response for error cases."""
        return create_error_response() 