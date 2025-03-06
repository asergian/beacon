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

from app.routes.demo_routes import get_demo_emails
from app.email.demo_emails import get_demo_email_bodies
from app.email.demo_analysis import generate_all_demo_analysis, save_analysis_cache, load_analysis_cache

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
    
    The analysis generation involves multiple API calls and may take significant time
    depending on the number of demo emails and API response times.
    
    Returns:
        None
        
    Raises:
        Exception: Any errors during the analysis generation process will be
            logged with traceback and cause the script to exit with code 1.
    """
    try:
        logger.info("Starting Demo Email Analysis Generation")
        
        # Try to load existing cache
        logger.info("\nChecking for existing analysis cache...")
        load_analysis_cache()
        
        # Get demo emails
        logger.info("\nFetching demo emails...")
        demo_emails = get_demo_emails()
        logger.info(f"Found {len(demo_emails)} demo emails")
        
        # Process all emails
        logger.info("\nStarting analysis generation...")
        logger.info(f"This will test {len(demo_emails)} emails × 6 combinations (2 models × 3 context lengths)")
        logger.info(f"Total API calls: {len(demo_emails) * 6}")
        
        # Generate analysis for all combinations
        generate_all_demo_analysis(demo_emails)
        
        # Save the analysis cache
        logger.info("\nSaving analysis cache...")
        save_analysis_cache()
        
        logger.info("\n=== Analysis Generation Complete ===")
        
    except Exception as e:
        logger.error("\n!!! Error during analysis generation !!!")
        logger.error(f"Error: {str(e)}")
        logger.error("\nFull traceback:")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    """Script entry point.
    
    Calls the main function to start the analysis generation process.
    """
    main() 