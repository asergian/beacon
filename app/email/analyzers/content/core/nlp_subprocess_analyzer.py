"""Content NLP Subprocess Analyzer for memory-efficient content processing.

This module provides the NLPSubprocessAnalyzer class that handles content analysis
in a separate process to optimize memory usage and prevent memory leaks.

The analyzer implements several features:
- Memory-isolated NLP processing
- Batch text analysis
- Result standardization
- Error handling and logging

Typical usage:
    analyzer = ContentAnalyzerSubprocess()
    results = await analyzer.analyze_batch(texts)
"""

import logging
import time
from typing import Dict, List, Any

from ..processing.subprocess_manager import SubprocessNLPAnalyzer
from ..utils.result_formatter import format_nlp_result, create_error_response
from ....models.analysis_settings import ProcessingConfig
from ...base import BaseAnalyzer

class ContentAnalyzerSubprocess(BaseAnalyzer):
    """Analyzes text using SpaCy in isolated subprocesses to prevent memory leaks.
    
    This class provides a memory-safe implementation of content analysis by running
    SpaCy operations in separate processes. It handles batch processing, result
    formatting, and error handling.

    Attributes:
        logger: Logger instance for this class
        nlp_analyzer: Subprocess manager for NLP operations
        batch_size: Number of texts to process in each batch
    """
    
    def __init__(self, nlp_model=None, batch_size: int = 5):
        """Initialize the ContentAnalyzerSubprocess.
        
        Args:
            nlp_model: Ignored, included for compatibility with original ContentAnalyzer
            batch_size: Number of texts to process in each batch. Defaults to 5.
        """
        self.logger = logging.getLogger(__name__)
        self.nlp_analyzer = SubprocessNLPAnalyzer()
        self.batch_size = batch_size
        
        self.logger.info(f"ContentAnalyzerSubprocess initialized with batch size {self.batch_size}")

    async def analyze_batch(self, texts: List[str]) -> List[Dict[str, Any]]:
        """Analyze a batch of texts efficiently using subprocess isolation.
        
        Args:
            texts: List of texts to analyze
            
        Returns:
            List of dictionaries containing analysis results for each text.
            If processing fails, returns error responses.
        """
        from app.utils.memory_profiling import log_memory_usage

        log_memory_usage(self.logger, "ContentAnalyzer Batch Start")
        
        try:
            start_time = time.time()
            self.logger.debug(
                f"Starting batch NLP analysis of {len(texts)} texts\n"
                f"    Batch size: {self.batch_size}"
            )
            
            # Process texts in isolated subprocess
            nlp_results = await self.nlp_analyzer.analyze_batch(texts)
            
            # Format and validate results
            results = await self._process_results(texts, nlp_results)
            
            # Log processing time
            processing_time = time.time() - start_time
            self.logger.debug(
                f"NLP Analysis completed - Subprocess: {processing_time:.2f}s "
                f"(avg {processing_time/len(texts):.3f}s/text)"
            )
            
            log_memory_usage(self.logger, "ContentAnalyzer Batch Complete")
            return results
            
        except Exception as e:
            self.logger.error(f"Batch analysis failed: {str(e)}")
            return [create_error_response() for _ in texts]

    async def _process_results(
        self, 
        texts: List[str], 
        nlp_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Process and format the results from NLP analysis.
        
        Args:
            texts: Original input texts
            nlp_results: Raw results from NLP processing
            
        Returns:
            List of formatted result dictionaries
        """
        # Validate result count matches input count
        if len(nlp_results) != len(texts):
            self.logger.warning(
                f"Mismatch between input texts ({len(texts)}) and NLP results "
                f"({len(nlp_results)}). Adjusting results list."
            )
            nlp_results = self._adjust_result_count(nlp_results, len(texts))
        
        # Format each result
        results = []
        for i, (nlp_result, text) in enumerate(zip(nlp_results, texts)):
            try:
                result = format_nlp_result(nlp_result, text)
                results.append(result)
            except Exception as e:
                self.logger.error(f"Error processing result {i}: {e}")
                results.append(create_error_response())
                
        return results

    def _adjust_result_count(
        self, 
        results: List[Dict[str, Any]], 
        expected_count: int
    ) -> List[Dict[str, Any]]:
        """Adjust the number of results to match the expected count.
        
        Args:
            results: List of result dictionaries
            expected_count: Expected number of results
            
        Returns:
            Adjusted list of results
        """
        if len(results) < expected_count:
            results.extend([{} for _ in range(expected_count - len(results))])
        elif len(results) > expected_count:
            results = results[:expected_count]
        return results 