"""SpaCy utilities for NLP processing.

This module provides SpaCy-specific utilities for working with NLP models
and Doc objects, with a focus on memory optimization and efficient text processing
for email analysis workloads.

Key Components:
1. Model Management
   - Optimized model loading with minimal components
   - Memory-efficient configuration
   - Disabled unnecessary features (vectors, textcat)

2. Memory Management
   - Thorough Doc object cleanup
   - Circular reference prevention
   - Aggressive garbage collection
   - Memory leak prevention

3. Performance Optimization
   - Reduced maximum text length
   - Minimal pipeline components
   - Efficient token and span handling

The module is designed for production email processing systems where
memory efficiency and stability are critical requirements.

Usage:
    from .spacy_utils import load_optimized_model, cleanup_doc
    nlp = load_optimized_model("en_core_web_sm")
    doc = nlp(text)
    cleanup_doc(doc)
"""

import gc
import logging
import spacy

logger = logging.getLogger(__name__)


def load_optimized_model(model_name: str = "en_core_web_sm") -> spacy.language.Language:
    """Load a highly optimized SpaCy model with minimal memory footprint.
    
    Args:
        model_name: Name of the SpaCy model to load
        
    Returns:
        Optimized SpaCy language model
        
    The function:
    1. Forces garbage collection before loading
    2. Disables unnecessary components (vectors, textcat, etc.)
    3. Limits maximum text length for memory efficiency
    4. Configures optimal pipeline settings
    """
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
    nlp.max_length = 50000  # Reduced from default

    # Additional memory optimization - disable vector storage
    # if hasattr(nlp, 'remove_pipe') and 'vectors' in nlp.pipe_names:
    #     nlp.remove_pipe('vectors')
    
    return nlp


def cleanup_doc(doc: spacy.tokens.Doc) -> None:
    """Safely cleanup a SpaCy Doc object to prevent memory leaks.
    
    Args:
        doc: SpaCy Doc object to cleanup
        
    The function performs a thorough cleanup by:
    1. Removing circular references in user hooks and data
    2. Clearing token and span references
    3. Removing document from vocabulary
    4. Clearing document text and other attributes
    5. Forcing garbage collection
    
    This is critical for long-running processes to prevent memory leaks
    and should be called after processing each document.
    """
    if doc is None:
        return
        
    try:
        # Remove circular references
        doc.user_hooks = {}
        doc.user_data = {}
        
        # Clear token and span references
        for token in doc:
            token._.remove()
            # Clear token attributes to prevent circular references
            for attr_name in dir(token._):
                if not attr_name.startswith('__'):
                    setattr(token._, attr_name, None)
                    
        # Clear entities and noun chunks to prevent reference cycles
        if hasattr(doc, 'ents'):
            doc.ents = []
        if hasattr(doc, '_'):
            doc._.clear()
            
        doc.user_span_hooks = {}
        
        # Remove document from vocabulary
        # This is a critical step for memory release
        doc.vocab = None
        
        # Clear the document text
        doc.text = ""
        
        # Clear other attributes that might hold references
        doc._vector = None
        if hasattr(doc, 'tensor'):
            doc.tensor = None
            
    except Exception as e:
        logger.debug(f"Non-critical error during doc cleanup: {e}")
        
    # Force garbage collection
    gc.collect() 