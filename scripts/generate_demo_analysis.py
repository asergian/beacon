#!/usr/bin/env python3
"""Pre-generate analysis for demo emails.

This script generates and caches analysis results for all demo emails in the system.
It runs the analysis with multiple models and context lengths to ensure
all demo emails have pre-generated analysis available when accessed through the demo interface.

The script is intended to be run before deploying the application or after
adding new demo emails to ensure a smooth demo experience without API delays.

Typical usage:
    $ python scripts/generate_demo_analysis.py
"""

import os
import sys
import json
from pathlib import Path
import traceback
import logging

# Add the parent directory to sys.path
sys.path.append(str(Path(__file__).parent.parent))

# Import from the new demo module structure
from app.demo.routes import get_demo_emails
from app.demo.data import get_demo_email_bodies
from app.demo.analysis import generate_all_demo_analysis, save_analysis_cache, load_analysis_cache

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Generate and save analysis for all demo emails.
    
    This function orchestrates the entire demo analysis generation process:
    1. Loads any existing analysis cache
    2. Fetches all demo emails from the system
    3. Generates analysis for each email using multiple models and context lengths
    4. Saves the generated analysis to the cache for future use
    
    Returns:
        int: 0 for success, 1 for error
    """
    try:
        logger.info("Loading existing analysis cache")
        load_analysis_cache()
        
        logger.info("Fetching demo emails")
        demo_emails = get_demo_emails()
        
        logger.info(f"Generating analysis for {len(demo_emails)} demo emails")
        logger.info(f"This will test {len(demo_emails)} emails × 6 combinations (2 models × 3 context lengths)")
        generate_all_demo_analysis(demo_emails)
        
        logger.info("Saving analysis cache")
        save_analysis_cache()
        
        logger.info("Analysis generation complete!")
        return 0
        
    except Exception as e:
        logger.error(f"Error generating demo analysis: {e}")
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main()) 