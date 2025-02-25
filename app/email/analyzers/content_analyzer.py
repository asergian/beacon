import spacy
import re
from typing import Dict, List, Tuple
from concurrent.futures import ThreadPoolExecutor
import time
from ..models.analysis_settings import ProcessingConfig
import os
import logging
import multiprocessing
import asyncio
from concurrent.futures import ProcessPoolExecutor
import math
import gc

class ContentAnalyzer:
    """Analyzes text using spaCy for entities and urgency."""

    # Pre-compile all regex patterns
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

    BULK_PATTERNS = {
        'marketing': re.compile(r'\b(subscribe|unsubscribe|newsletter|marketing|offer|promotion|discount|sale|deal)\b'),
        'mass_email': re.compile(r'\b(view in browser|email preferences|opt out|mailing list)\b')
    }

    AUTOMATED_PATTERNS = {
        'system': re.compile(r'\b(system|automated|automatic|bot|daemon|notification)\b'),
        'noreply': re.compile(r'\b(no[- ]?reply|do[- ]?not[- ]?reply|auto[- ]?generated)\b')
    }

    # Pre-define sets for faster lookups
    VALID_ENTITY_LABELS = {'PERSON', 'ORG', 'GPE', 'DATE', 'TIME', 'MONEY', 'PERCENT', 'PRODUCT', 'EVENT', 'WORK_OF_ART'}
    HTML_INDICATORS = {'<', '>', '/', 'http', 'www', 'html', 'css'}
    QUESTION_WORDS = {'what', 'when', 'where', 'who', 'why', 'how'}
    MODAL_VERBS = {'could', 'would', 'can', 'will', 'should'}
    DEADLINE_WORDS = {'deadline', 'due', 'by', 'until', 'before'}

    def __init__(self, nlp_model: spacy.language.Language):
        """Initialize the ContentAnalyzer."""
        self.logger = logging.getLogger(__name__)
        
        # Create a single optimized NLP pipeline
        self.nlp = spacy.load(nlp_model.meta['lang'] + '_core_web_sm')
        
        # Configure pipeline for maximum efficiency
        self.nlp.max_length = 2000000  # Increase max length
        
        # Disable unnecessary components
        disabled_pipes = ['textcat', 'lemmatizer', 'attribute_ruler']
        for pipe in disabled_pipes:
            if pipe in self.nlp.pipe_names:
                self.nlp.disable_pipe(pipe)
        
        # Configure batch processing
        self.batch_size = 100
        
        # Log pipeline configuration
        self.logger.debug(
            f"SpaCy pipeline configuration:\n"
            f"    Enabled components: {[pipe for pipe in self.nlp.pipe_names if not pipe in disabled_pipes]}\n"
            f"    Disabled components: {disabled_pipes}\n"
            f"    Max length: {self.nlp.max_length}\n"
            f"    Batch size: {self.batch_size}"
        )

    def _cleanup_doc(self, doc: spacy.tokens.Doc):
        """Safely cleanup spaCy doc to free memory."""
        try:
            # Remove circular references
            doc.user_hooks = {}
            doc.user_data = {}
            # Clear token and span references
            for token in doc:
                token._.remove()
            doc.user_span_hooks = {}
            # Remove document from vocabulary
            doc.vocab = None
            # Clear the document text
            doc.text = ""
        except Exception as e:
            self.logger.debug(f"Non-critical error during doc cleanup: {e}")

    async def analyze_batch(self, texts: List[str]) -> List[Dict]:
        """Analyze a batch of texts efficiently."""
        try:
            start_time = time.time()
            self.logger.info(
                f"Starting batch NLP analysis of {len(texts)} texts\n"
                f"    Using Hypercorn worker process\n"
                f"    Batch size: {self.batch_size}"
            )
            
            # Preprocess texts
            texts = [text[:1000000] for text in texts]  # Limit length
            texts_lower = [text.lower() for text in texts]  # Convert to lower case once
            
            # Process with optimized batch size
            # Use ThreadPoolExecutor for parallel processing within the same process
            with ThreadPoolExecutor() as executor:
                loop = asyncio.get_event_loop()
                
                # Split texts into smaller batches for better parallelization
                batch_size = max(1, len(texts) // 4)  # Split into 4 batches
                batches = [texts[i:i + batch_size] for i in range(0, len(texts), batch_size)]
                
                # Process batches in parallel
                async def process_batch(batch):
                    return list(self.nlp.pipe(batch, batch_size=self.batch_size))
                
                tasks = [loop.run_in_executor(executor, lambda b=batch: list(self.nlp.pipe(b, batch_size=self.batch_size))) 
                        for batch in batches]
                chunk_results = await asyncio.gather(*tasks)
                
                # Flatten results
                docs = [doc for chunk in chunk_results for doc in chunk]
            
            pipe_time = time.time() - start_time
            self.logger.debug(
                f"SpaCy processing completed:\n"
                f"    Total time: {pipe_time:.2f}s\n"
                f"    Average per text: {pipe_time/len(texts):.3f}s"
            )
            
            # Process results and cleanup immediately
            results = []
            for doc, text_lower in zip(docs, texts_lower):
                try:
                    result = self._process_analyzed_doc(doc, text_lower)
                    results.append(result)
                finally:
                    # Cleanup spaCy doc
                    self._cleanup_doc(doc)
            
            # Clear references to large objects
            docs = None
            texts = None
            texts_lower = None
            chunk_results = None
            batches = None
            
            # Force garbage collection after large batch processing
            gc.collect()
            
            post_process_time = time.time() - start_time - pipe_time
            
            self.logger.debug(
                f"Post-processing completed:\n"
                f"    Total time: {post_process_time:.2f}s\n"
                f"    Average: {post_process_time/len(results):.3f}s per text"
            )
            
            total_time = time.time() - start_time
            self.logger.debug(
                f"NLP Analysis Summary:\n"
                f"    Total time: {total_time:.2f}s\n"
                f"    SpaCy pipe time: {pipe_time:.2f}s\n"
                f"    Post-processing time: {post_process_time:.2f}s\n"
                f"    Average time per text: {total_time/len(results):.3f}s"
            )
            
            self.logger.info(f"NLP Analysis completed - SpaCy: {pipe_time:.2f}s, Post-processing: {post_process_time:.2f}s, Total: {total_time:.2f}s (avg {total_time/len(results):.3f}s/text)")
            
            return results
            
        except Exception as e:
            self.logger.error(f"Batch analysis failed: {str(e)}")
            raise

    def _process_analyzed_doc(self, doc: spacy.tokens.Doc, text_lower: str) -> Dict:
        """Process a single analyzed document."""
        try:
            # Initialize all collectors
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
            
            # Process entities and tokens first
            entity_dict = {}
            for ent in doc.ents:
                if ent.label_ in self.VALID_ENTITY_LABELS:
                    if not any(indicator in ent.text.lower() for indicator in self.HTML_INDICATORS):
                        entity_dict[ent.text] = ent.label_
                        result['structural_elements']['named_entities_categories'].add(ent.label_)
                    if ent.label_ in {'DATE', 'TIME'}:
                        result['time_sensitivity']['time_references'].append(ent.text)
            
            # Process tokens
            for token in doc:
                if token.pos_ == 'VERB':
                    result['structural_elements']['verbs'].add(token.lemma_)
                if token.dep_ in ('ROOT', 'dobj', 'iobj'):
                    result['structural_elements']['dependencies'].append((token.text, token.dep_))
            
            # Process sentences
            for sent in doc.sents:
                result['sentence_count'] += 1
                sent_text = sent.text.strip()
                sent_lower = sent_text.lower()
                
                # Question detection
                if sent_text.endswith('?'):
                    sent_tokens = {token.text.lower() for token in sent}  # Use set for faster lookups
                    has_question_word = bool(sent_tokens & self.QUESTION_WORDS)
                    has_modal = bool(sent_tokens & self.MODAL_VERBS)
                    
                    if has_modal:
                        result['questions']['request_questions'].append(sent_text)
                    elif has_question_word:
                        result['questions']['direct_questions'].append(sent_text)
                    else:
                        result['questions']['rhetorical_questions'].append(sent_text)
                    
                    result['questions']['question_count'] += 1
                
                # Deadline detection
                if any(word in sent_lower for word in self.DEADLINE_WORDS):
                    has_time = any(ent.label_ in {'DATE', 'TIME'} for ent in sent.ents)
                    if has_time:
                        result['time_sensitivity']['deadline_phrases'].append(sent_text)
                        result['time_sensitivity']['has_deadline'] = True
            
            # Process noun chunks (only if we have space for more key phrases)
            if len(result['key_phrases']) < 3:
                for chunk in doc.noun_chunks:
                    if not any(indicator in chunk.text.lower() for indicator in self.HTML_INDICATORS):
                        result['key_phrases'].append(chunk.text)
                        if len(result['key_phrases']) >= 3:
                            break
            
            # Get sentiment and pattern matches
            sentiment_scores = self._analyze_sentiment(text_lower)
            email_patterns = self._detect_email_patterns(text_lower)
            
            # Convert sets to lists and limit sizes
            result.update({
                'entities': dict(list(entity_dict.items())[:5]),
                'key_phrases': result['key_phrases'][:3],
                'urgency': self._check_urgency(text_lower),
                'sentiment_analysis': {
                    'scores': sentiment_scores,
                    'is_positive': sentiment_scores['positive'] > sentiment_scores['negative'],
                    'is_strong_sentiment': abs(sentiment_scores['positive'] - sentiment_scores['negative']) > 0.5,
                    'has_gratitude': sentiment_scores['patterns']['gratitude'] > 0,
                    'has_dissatisfaction': sentiment_scores['patterns']['dissatisfaction'] > 0
                },
                'email_patterns': email_patterns,
                'questions': {
                    'has_questions': result['questions']['question_count'] > 0,
                    'direct_questions': result['questions']['direct_questions'][:2],
                    'rhetorical_questions': result['questions']['rhetorical_questions'][:2],
                    'request_questions': result['questions']['request_questions'][:2],
                    'question_count': result['questions']['question_count']
                },
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
            })
            
            # Clear large intermediate objects
            entity_dict = None
            sentiment_scores = None
            email_patterns = None
            
            return result
            
        except Exception as e:
            self.logger.error(f"Document processing failed: {str(e)}")
            return self._create_error_response()

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

    def _analyze_sentiment(self, text_lower: str) -> Dict:
        """Analyze sentiment patterns in text."""
        # Use pre-compiled patterns
        positive_matches = {
            category: len(pattern.findall(text_lower))
            for category, pattern in self.POSITIVE_PATTERNS.items()
        }
        
        negative_matches = {
            category: len(pattern.findall(text_lower))
            for category, pattern in self.NEGATIVE_PATTERNS.items()
        }
        
        total_positive = sum(positive_matches.values())
        total_negative = sum(negative_matches.values())
        total_matches = total_positive + total_negative
        
        if total_matches == 0:
            return {
                'positive': 0.5,
                'negative': 0.5,
                'patterns': {**positive_matches, **negative_matches}
            }
        
        return {
            'positive': total_positive / total_matches,
            'negative': total_negative / total_matches,
            'patterns': {**positive_matches, **negative_matches}
        }

    def _detect_email_patterns(self, text_lower: str) -> Dict:
        """Detect various email patterns."""
        # Use pre-compiled patterns
        bulk_matches = {
            category: bool(pattern.search(text_lower))
            for category, pattern in self.BULK_PATTERNS.items()
        }
        
        automated_matches = {
            category: bool(pattern.search(text_lower))
            for category, pattern in self.AUTOMATED_PATTERNS.items()
        }
        
        return {
            'is_bulk': any(bulk_matches.values()),
            'is_automated': any(automated_matches.values()),
            'bulk_indicators': [k for k, v in bulk_matches.items() if v],
            'automated_indicators': [k for k, v in automated_matches.items() if v]
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