"""Script to generate pre-analyzed demo emails."""

import os
import sys
from pathlib import Path
import traceback

# Add the app directory to Python path
app_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(app_dir))

from app.email.demo_emails import get_demo_email_bodies
from app.email.demo_analysis import generate_all_demo_analysis, save_analysis_cache, load_analysis_cache
from app.routes.email_routes import get_demo_emails

def main():
    """Generate and save analysis for all demo emails."""
    try:
        print("\n=== Starting Demo Email Analysis Generation ===")
        
        # Try to load existing cache
        print("\nChecking for existing analysis cache...")
        load_analysis_cache()
        
        # Get demo emails
        print("\nFetching demo emails...")
        demo_emails = get_demo_emails()
        print(f"Found {len(demo_emails)} demo emails")
        
        # Process all emails
        print("\nStarting analysis generation...")
        print(f"This will test {len(demo_emails)} emails × 6 combinations (2 models × 3 context lengths)")
        print(f"Total API calls: {len(demo_emails) * 6}")
        
        # Generate analysis for all combinations
        generate_all_demo_analysis(demo_emails)
        
        # Save the analysis cache
        print("\nSaving analysis cache...")
        save_analysis_cache()
        
        print("\n=== Analysis Generation Complete ===")
        
    except Exception as e:
        print("\n!!! Error during analysis generation !!!")
        print(f"Error: {str(e)}")
        print("\nFull traceback:")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main() 