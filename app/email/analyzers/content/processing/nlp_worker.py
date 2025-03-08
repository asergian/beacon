"""Self-contained NLP processor for running in separate processes.

This module provides a standalone NLP processing capability that can be run
in a separate process to isolate memory usage from the main application.
It loads a SpaCy model, processes text, and returns analysis results as JSON.

The module performs several types of analysis:

- Named Entity Recognition (NER)
- Key phrase extraction
- Sentiment analysis
- Email type classification (bulk/automated)
- Urgency detection
- Question identification

Typical usage example::

    # Process a single text
    python nlp_worker.py --text "Your email content here"

    # Process multiple texts from a JSON file
    python nlp_worker.py --file input.json

    # Process texts from a JSON string
    python nlp_worker.py '["text1", "text2"]'

Attributes:
    VALID_ENTITY_LABELS (List[str]): List of valid SpaCy entity labels to extract,
        imported from pattern_matchers module.

Memory Management:
    This module is designed to run in isolation and implements several memory
    management strategies:

    - Garbage collection after processing each document
    - Document cleanup using spacy_utils.cleanup_doc
    - Limited text size (10K chars) for processing
    - Model unloading after batch processing

Dependencies:
    - spacy: For NLP processing
    - pattern_matchers: Local module for text pattern matching
    - spacy_utils: Local module for SpaCy model management
"""

import argparse
import gc
import json
import logging
import os
import sys
from typing import List, Dict, Any, Optional
import spacy

# Get the absolute path of the utils module
UTILS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))
print(f"UTILS_PATH: {UTILS_PATH}")
# Add utils path to sys.path
sys.path.insert(0, UTILS_PATH)

# Now we can use imports relative to the app package
from utils.spacy_utils import load_optimized_model, cleanup_doc
from utils.pattern_matchers import (
    analyze_sentiment,
    detect_email_patterns,
    check_urgency,
    VALID_ENTITY_LABELS
)

def extract_entities(doc: spacy.tokens.Doc) -> Dict[str, List[Dict[str, Any]]]:
    """Extract named entities from a SpaCy document.
    
    Args:
        doc: A SpaCy Doc object containing processed text.
    
    Returns:
        A dictionary mapping entity labels to lists of entity information dictionaries.
        Each entity dictionary contains:
            - text: The entity text
            - start: Character start position
            - end: Character end position
    """
    entities = {}
    for ent in doc.ents:
        if ent.label_ in VALID_ENTITY_LABELS:
            if ent.label_ not in entities:
                entities[ent.label_] = []
            entities[ent.label_].append({
                'text': ent.text,
                'start': ent.start_char,
                'end': ent.end_char
            })
    return entities

def extract_key_phrases(doc: spacy.tokens.Doc, limit: int = 5) -> List[Dict[str, Any]]:
    """Extract key noun phrases from a SpaCy document.

    Args:
        doc: A SpaCy Doc object containing processed text.
        limit: Maximum number of phrases to return. Defaults to 5.

    Returns:
        A list of dictionaries containing noun phrase information:
            - text: The phrase text
            - start: Character start position
            - end: Character end position
            - root: The root word of the phrase
    """
    key_phrases = []
    for chunk in doc.noun_chunks:
        if len(chunk) < 2:
            continue
        if chunk.root.pos_ != 'NOUN':
            continue
        key_phrases.append({
            'text': chunk.text,
            'start': chunk.start_char,
            'end': chunk.end_char,
            'root': chunk.root.text
        })
    return key_phrases[:limit]

def extract_questions(doc: spacy.tokens.Doc, limit: int = 3) -> List[str]:
    """Extract questions from a SpaCy document.

    Args:
        doc: A SpaCy Doc object containing processed text.
        limit: Maximum number of questions to return. Defaults to 3.

    Returns:
        A list of question sentences.
    """
    return [sent.text for sent in doc.sents if sent.text.strip().endswith('?')][:limit]

def analyze_text(doc: spacy.tokens.Doc, text_lower: str) -> Dict[str, Any]:
    """Analyze a single document using SpaCy and pattern matching.

    Args:
        doc: A SpaCy Doc object containing processed text.
        text_lower: Lowercase version of the original text.

    Returns:
        A dictionary containing the analysis results:
            - entities: Named entity information
            - key_phrases: Important noun phrases
            - sentence_count: Number of sentences
            - questions: List of questions found
            - sentiment: Sentiment analysis results
            - email_type: Email type classification
            - urgency: Urgency indicators
            - is_question: Whether the text contains a question
            - error: Error message if processing failed
    """
    # Extract basic features
    entities = extract_entities(doc)
    key_phrases = extract_key_phrases(doc)
    questions = extract_questions(doc)
    
    # Pattern matching analysis
    sentiment_results = analyze_sentiment(text_lower)
    email_patterns = detect_email_patterns(text_lower)
    is_urgent = check_urgency(text_lower)
    
    # Combine results
    return {
        'entities': entities,
        'key_phrases': key_phrases,
        'sentence_count': len(list(doc.sents)),
        'questions': questions,
        'sentiment': {
            'is_positive': sentiment_results['is_positive'],
            'is_negative': sentiment_results['is_negative'],
            'patterns': {
                'gratitude': sentiment_results['gratitude'],
                'agreement': sentiment_results['agreement'],
                'dissatisfaction': sentiment_results['dissatisfaction'],
                'demand': sentiment_results['demand']
            }
        },
        'email_type': {
            'is_bulk': email_patterns['is_bulk'],
            'is_automated': email_patterns['is_automated']
        },
        'urgency': {
            'is_urgent': is_urgent,
            'has_deadline': email_patterns.get('has_deadline', False)
        },
        'is_question': '?' in text_lower and any(qw in text_lower for qw in ('what', 'when', 'where', 'who', 'why', 'how')),
        'error': None
    }

def process_single_text(text: str, nlp: spacy.language.Language) -> Dict[str, Any]:
    """Process a single text with SpaCy and return analysis results.

    Args:
        text: The text to analyze.
        nlp: A loaded SpaCy language model.

    Returns:
        A dictionary containing the analysis results or an error response.
    """
    try:
        # Skip empty texts
        if not text or len(text.strip()) < 3:
            return create_empty_result()
            
        # Process with SpaCy
        doc = nlp(text)
        text_lower = text.lower()
        
        # Analyze and get results
        result = analyze_text(doc, text_lower)
        
        # Clean up
        cleanup_doc(doc)
        return result
        
    except Exception as e:
        return create_error_result(str(e))

def process_texts(texts: List[str]) -> List[Dict[str, Any]]:
    """Process multiple texts with SpaCy and return structured results.
    
    This function handles the complete pipeline of loading the model,
    processing each text, and cleaning up resources. It's designed to run
    in a separate process and handles all NLP processing internally.
    
    Args:
        texts: List of texts to process.
    
    Returns:
        List of dictionaries containing analysis results for each text.
        Each dictionary contains:
            - entities: Named entity information
            - key_phrases: Important noun phrases
            - sentence_count: Number of sentences
            - questions: List of questions found
            - sentiment: Sentiment analysis results
            - email_type: Email type classification
            - urgency: Urgency indicators
            - is_question: Whether the text contains a question
            - error: Error message if processing failed
    """
    # Load model
    nlp = load_optimized_model()
    
    # Preprocess texts - limit to most relevant parts
    preprocessed = [text[:10000] for text in texts]  # Limit to 10K chars
    
    # Process all texts
    results = []
    for text in preprocessed:
        results.append(process_single_text(text, nlp))
        gc.collect()  # Force garbage collection after each document
    
    # Final cleanup
    nlp = None
    gc.collect()
    gc.collect()
    
    return results

def create_empty_result() -> Dict[str, Any]:
    """Create an empty result for skipped texts.

    Returns:
        A dictionary containing default values for all analysis fields.
    """
    return {
        'entities': {},
        'key_phrases': [],
        'sentence_count': 0,
        'questions': [],
        'sentiment': {
            'is_positive': False,
            'is_negative': False,
            'patterns': {
                'gratitude': False,
                'agreement': False,
                'dissatisfaction': False,
                'demand': False
            }
        },
        'email_type': {
            'is_bulk': False,
            'is_automated': False
        },
        'urgency': {
            'is_urgent': False,
            'has_deadline': False
        },
        'is_question': False,
        'error': None
    }

def create_error_result(error_message: str) -> Dict[str, Any]:
    """Create an error result for failed processing.

    Args:
        error_message: The error message to include in the result.

    Returns:
        A dictionary containing default values and the error message.
    """
    result = create_empty_result()
    result['error'] = error_message
    return result

def main(args: Optional[argparse.Namespace] = None) -> None:
    """Main entry point for the script.

    Args:
        args: Optional parsed command line arguments.
            If None, arguments will be parsed from sys.argv.
    """
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    if args is None:
        # Set up argument parser
        parser = argparse.ArgumentParser(description='Process texts with SpaCy NLP')
        parser.add_argument('--file', type=str, help='Input JSON file containing texts to process')
        parser.add_argument('--text', type=str, help='Text to analyze directly')
        parser.add_argument('text_json', nargs='?', help='JSON string of texts to process (alternative to --file)')
        args = parser.parse_args()
    
    try:
        # Get input data either from file or command line
        if args.file:
            with open(args.file, 'r') as f:
                texts = json.loads(f.read())
        elif args.text:
            texts = [args.text]
        elif args.text_json:
            texts = json.loads(args.text_json)
        else:
            print(json.dumps({"error": "No input provided. Use --file, --text, or provide JSON string."}))
            sys.exit(1)
        
        # Log the number of texts received
        logger.info(f"Received {len(texts)} texts to process")
        
        # Process texts
        results = process_texts(texts)
        
        # Log the number of results being returned
        logger.info(f"Returning {len(results)} results")
        
        # Output JSON results - make sure we're only sending results once
        print(json.dumps(results), flush=True)
        
    except Exception as e:
        logger.error(f"Error: {e}")
        print(json.dumps([{"error": str(e)}]), flush=True)
        sys.exit(1)

if __name__ == "__main__":
    main() 