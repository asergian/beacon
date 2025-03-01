"""Self-contained NLP processor for running in separate processes."""

import spacy
import re
import json
import gc
import os
from typing import List, Dict, Any
import argparse
import logging

def load_optimized_model(model_name="en_core_web_sm"):
    """Load a highly optimized SpaCy model with minimal memory footprint."""
    # Force garbage collection before loading
    gc.collect()
    gc.collect()
    
    # Load with minimal components
    nlp = spacy.load(model_name, disable=[
        'vectors',       # Disable word vectors (massive memory savings)
        'textcat',       # Disable text categorization
        'lemmatizer',    # Disable lemmatization
        'attribute_ruler',
        'tok2vec'        # Transformer component
    ])
    
    # Limit maximum text length
    nlp.max_length = 50000  # Reduced from 100,000
    
    return nlp

def cleanup_doc(doc):
    """Manually clean up a SpaCy Doc object to release memory.
    Without relying on custom extensions."""
    # Clear user data
    if hasattr(doc, 'user_data'):
        doc.user_data.clear()
    
    # Release references to tokens
    for token in doc:
        if hasattr(token, 'user_data'):
            token.user_data.clear()
    
    # Clear spans
    if hasattr(doc, 'spans'):
        for span_group_name in list(doc.spans.keys()):
            doc.spans[span_group_name] = []
    
    # Remove entity references
    doc.ents = []
    
    # Clear other attributes when possible
    doc.tensor = None

def process_texts(texts: List[str]) -> List[Dict[str, Any]]:
    """Process multiple texts with SpaCy and return structured results.
    
    This function is designed to run in a separate process and handles all
    NLP processing internally, returning only serializable results.
    """
    # Pre-compile regex patterns for efficiency
    positive_patterns = {
        'gratitude': re.compile(r'\b(thank|thanks|grateful|appreciate)\b'),
        'positive': re.compile(r'\b(great|excellent|good|wonderful)\b')
    }
    
    negative_patterns = {
        'urgency': re.compile(r'\b(urgent|asap|emergency|immediate)\b'),
        'dissatisfaction': re.compile(r'\b(disappointed|concerned|issue|problem)\b')
    }
    
    # Load model
    nlp = load_optimized_model()
    
    # Preprocess texts - limit to most relevant parts
    preprocessed = [text[:10000] for text in texts]  # Limit to 10K chars
    
    # Process all texts
    results = []
    
    # Process texts one at a time to minimize memory usage
    for text in preprocessed:
        try:
            # Process with SpaCy
            doc = nlp(text)
            
            # Extract entities
            entities = {}
            for ent in doc.ents:
                if ent.label_ in {'PERSON', 'ORG', 'GPE', 'DATE', 'TIME'}:
                    entities[ent.text] = ent.label_
            
            # Extract key phrases (noun chunks)
            noun_chunks = list(doc.noun_chunks)
            key_phrases = [chunk.text for chunk in noun_chunks[:5]]
            
            # Count sentences
            sentence_count = len(list(doc.sents))
            
            # Extract questions
            questions = [sent.text for sent in doc.sents if sent.text.strip().endswith('?')][:3]
            
            # Check for sentiment patterns
            text_lower = text.lower()
            positive_matches = {k: bool(v.search(text_lower)) for k, v in positive_patterns.items()}
            negative_matches = {k: bool(v.search(text_lower)) for k, v in negative_patterns.items()}
            
            # Create result
            result = {
                'entities': entities,
                'key_phrases': key_phrases,
                'sentence_count': sentence_count,
                'questions': questions,
                'sentiment': {
                    'positive': any(positive_matches.values()),
                    'negative': any(negative_matches.values()),
                    'patterns': {**positive_matches, **negative_matches}
                },
                'has_deadline': bool(re.search(r'\b(deadline|due|by)\b.*\b(today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b', text_lower))
            }
            
            results.append(result)
            
            # Clean up the document to release memory
            cleanup_doc(doc)
            doc = None
            
        except Exception as e:
            results.append({
                'error': str(e),
                'entities': {},
                'key_phrases': [],
                'sentence_count': 0
            })
        
        # Force garbage collection after each document
        gc.collect()
    
    # Final cleanup
    nlp = None
    gc.collect()
    gc.collect()
    
    return results

# This function can be called directly from the subprocess
if __name__ == "__main__":
    import sys
    
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Process texts with SpaCy NLP')
    parser.add_argument('--file', type=str, help='Input JSON file containing texts to process')
    parser.add_argument('text_json', nargs='?', help='JSON string of texts to process (alternative to --file)')
    
    args = parser.parse_args()
    
    # Get input data either from file or command line
    if args.file:
        with open(args.file, 'r') as f:
            texts = json.loads(f.read())
    elif args.text_json:
        texts = json.loads(args.text_json)
    else:
        print(json.dumps({"error": "No input provided. Use --file or provide JSON string."}))
        sys.exit(1)
    
    # Log the number of texts received
    logger.info(f"Received {len(texts)} texts to process")
    
    # Process texts
    results = process_texts(texts)
    
    # Log the number of results being returned
    logger.info(f"Returning {len(results)} results")
    
    # Output JSON results - make sure we're only sending results once
    output = json.dumps(results)
    print(output, flush=True) 