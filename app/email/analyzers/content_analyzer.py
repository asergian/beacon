import spacy
import re
from typing import Dict
from ..models.analysis_settings import ProcessingConfig

class ContentAnalyzer:
    """Analyzes text using spaCy for entities and urgency."""

    # Sentiment patterns
    POSITIVE_PATTERNS = {
        'gratitude': r'\b(thank|thanks|grateful|appreciate|appreciated)\b',
        'positive': r'\b(great|excellent|good|wonderful|fantastic|amazing|helpful|pleased|happy|excited)\b',
        'agreement': r'\b(agree|approved|confirmed|sounds good|perfect)\b'
    }
    
    NEGATIVE_PATTERNS = {
        'urgency': r'\b(urgent|asap|emergency|immediate|critical)\b',
        'dissatisfaction': r'\b(disappointed|concerned|worried|unfortunately|issue|problem|error|failed|wrong)\b',
        'demand': r'\b(must|need|require|mandatory|asap)\b'
    }

    # Email patterns
    BULK_PATTERNS = {
        'marketing': r'\b(subscribe|unsubscribe|newsletter|marketing|offer|promotion|discount|sale|deal)\b',
        'mass_email': r'\b(view in browser|email preferences|opt out|mailing list)\b'
    }

    AUTOMATED_PATTERNS = {
        'system': r'\b(system|automated|automatic|bot|daemon|notification)\b',
        'noreply': r'\b(no[- ]?reply|do[- ]?not[- ]?reply|auto[- ]?generated)\b'
    }

    def __init__(self, nlp_model: spacy.language.Language):
        """Initialize the ContentAnalyzer.

        Args:
            nlp_model: The spaCy NLP model to use.
        """
        self.nlp = nlp_model
        
    def analyze(self, text: str) -> Dict:
        """Analyzes the text for entities, urgency, and additional linguistic features."""
        doc = self.nlp(text)

        # Get sentiment analysis
        sentiment_scores = self._analyze_sentiment(text)
        
        # Detect email patterns
        email_patterns = self._detect_email_patterns(text)

        # Filter out HTML-like entities and keep only meaningful ones
        valid_entity_labels = {'PERSON', 'ORG', 'GPE', 'DATE', 'TIME', 'MONEY', 'PERCENT', 'PRODUCT', 'EVENT', 'WORK_OF_ART'}
        filtered_entities = [
            (ent.label_, ent.text) for ent in doc.ents 
            if (ent.label_ in valid_entity_labels and 
                not any(html_indicator in ent.text.lower() for html_indicator in ['<', '>', '/', 'http', 'www', 'html', 'css']))
        ]

        # Get meaningful noun chunks (avoid HTML/code fragments)
        valid_chunks = [
            chunk.text for chunk in doc.noun_chunks
            if not any(html_indicator in chunk.text.lower() for html_indicator in ['<', '>', '/', 'http', 'www', 'html', 'css'])
        ]

        # Detect questions more accurately
        questions = self._detect_questions(doc)

        # Detect deadlines and time sensitivity
        time_sensitivity = self._detect_time_sensitivity(doc)

        return {
            'entities': dict(filtered_entities[:5]),  # Top 5 valid entities
            'key_phrases': valid_chunks[:3],  # Top 3 valid phrases
            'urgency': self._check_urgency(text),
            'sentence_count': len(list(doc.sents)),
            'sentiment_analysis': {
                'scores': sentiment_scores,
                'is_positive': sentiment_scores['positive'] > sentiment_scores['negative'],
                'is_strong_sentiment': abs(sentiment_scores['positive'] - sentiment_scores['negative']) > 0.5,
                'has_gratitude': sentiment_scores['patterns']['gratitude'] > 0,
                'has_dissatisfaction': sentiment_scores['patterns']['dissatisfaction'] > 0
            },
            'email_patterns': email_patterns,
            'questions': questions,
            'time_sensitivity': time_sensitivity,
            'structural_elements': {
                'verbs': [token.lemma_ for token in doc if token.pos_ == 'VERB'][:5],  # Top 5 verbs
                'named_entities_categories': list(set(ent.label_ for ent in doc.ents if ent.label_ in valid_entity_labels))[:3],  # Top 3 valid entity types
                'dependencies': [(token.text, token.dep_) for token in doc if token.dep_ in ('ROOT', 'dobj', 'iobj')][:3]  # Top 3 dependencies
            }
        }

    def _analyze_sentiment(self, text: str) -> Dict:
        """Analyze sentiment patterns in text."""
        text_lower = text.lower()
        
        # Count pattern matches
        positive_matches = {
            category: len(re.findall(pattern, text_lower))
            for category, pattern in self.POSITIVE_PATTERNS.items()
        }
        
        negative_matches = {
            category: len(re.findall(pattern, text_lower))
            for category, pattern in self.NEGATIVE_PATTERNS.items()
        }
        
        # Calculate scores
        total_positive = sum(positive_matches.values())
        total_negative = sum(negative_matches.values())
        total_matches = total_positive + total_negative
        
        if total_matches == 0:
            positive_score = 0.5  # Neutral
            negative_score = 0.5
        else:
            positive_score = total_positive / total_matches
            negative_score = total_negative / total_matches
        
        return {
            'positive': positive_score,
            'negative': negative_score,
            'patterns': {**positive_matches, **negative_matches}
        }

    def _detect_email_patterns(self, text: str) -> Dict:
        """Detect various email patterns."""
        text_lower = text.lower()
        
        bulk_matches = {
            category: bool(re.search(pattern, text_lower))
            for category, pattern in self.BULK_PATTERNS.items()
        }
        
        automated_matches = {
            category: bool(re.search(pattern, text_lower))
            for category, pattern in self.AUTOMATED_PATTERNS.items()
        }
        
        return {
            'is_bulk': any(bulk_matches.values()),
            'is_automated': any(automated_matches.values()),
            'bulk_indicators': [k for k, v in bulk_matches.items() if v],
            'automated_indicators': [k for k, v in automated_matches.items() if v]
        }

    def _detect_questions(self, doc: spacy.tokens.Doc) -> Dict:
        """Detect different types of questions in the text."""
        direct_questions = []
        rhetorical_questions = []
        request_questions = []
        
        for sent in doc.sents:
            if sent.text.strip().endswith('?'):
                # Check for question words using proper token iteration
                sent_tokens = [token for token in sent]
                has_question_word = any(token.text.lower() in {'what', 'when', 'where', 'who', 'why', 'how'} for token in sent_tokens)
                
                # Check for modal verbs indicating requests
                has_modal = any(token.text.lower() in {'could', 'would', 'can', 'will', 'should'} for token in sent_tokens)
                
                if has_modal:
                    request_questions.append(sent.text)
                elif has_question_word:
                    direct_questions.append(sent.text)
                else:
                    rhetorical_questions.append(sent.text)
        
        return {
            'has_questions': bool(direct_questions or rhetorical_questions or request_questions),
            'direct_questions': direct_questions[:2],  # Limit to first 2 questions
            'rhetorical_questions': rhetorical_questions[:2],
            'request_questions': request_questions[:2],
            'question_count': len(direct_questions) + len(rhetorical_questions) + len(request_questions)
        }

    def _detect_time_sensitivity(self, doc: spacy.tokens.Doc) -> Dict:
        """Detect time-sensitive elements and deadlines."""
        time_entities = [ent for ent in doc.ents if ent.label_ in {'DATE', 'TIME'}]
        
        # Look for deadline-related phrases
        deadline_phrases = [
            sent.text for sent in doc.sents
            if any(word in sent.text.lower() for word in ['deadline', 'due', 'by', 'until', 'before'])
            and any(ent.label_ in {'DATE', 'TIME'} for ent in sent.ents)
        ]
        
        return {
            'has_deadline': bool(deadline_phrases),
            'deadline_phrases': deadline_phrases[:2],  # Limit to first 2 deadlines
            'time_references': [ent.text for ent in time_entities][:3]  # Limit to first 3 time references
        }
        
    def _check_urgency(self, text: str) -> bool:
        """Checks if the text contains urgency keywords."""
        config = ProcessingConfig()
        # Clean the text by replacing special characters with spaces
        cleaned_text = re.sub(r'[^\w\s]', ' ', text.lower())
        words = cleaned_text.split()
        
        # Check for exact matches first
        if config.URGENCY_KEYWORDS & set(words):
            return True
            
        # Check for words that start with urgency keywords
        for word in words:
            for keyword in config.URGENCY_KEYWORDS:
                if word.startswith(keyword):
                    return True
        
        return False 