"""Processing components for content analysis.

This package provides the processing components:
- nlp_worker: Standalone NLP processing script
- subprocess_manager: Manages subprocess execution and communication
"""

from .subprocess_manager import SubprocessNLPAnalyzer

__all__ = ['SubprocessNLPAnalyzer']
