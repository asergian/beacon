# app/routes.py
from .analysis_utils import process_emails, order_emails_by_priority
from .email_utils import fetch_emails

from flask import render_template, request
from . import app

print('in routes, after imports')

@app.route('/')
def home():
    try:
        print('rendering home...')
        return render_template('home.html', emails={})

    except Exception as e:
        # Handle any errors that may occur during fetching/processing
        return f"An error occurred: {e}", 500

# Initialize the global email variables outside the route
emails = []
processed_emails = []
ordered_emails = []

def fetch_and_process_emails():
    """Fetch and process emails only if not already done."""
    global emails, processed_emails, ordered_emails
    
    if not emails:  # Fetch emails only if not already fetched
        emails = fetch_emails()  # Replace with your actual email-fetching logic

    if not processed_emails:  # Process emails only if not already processed
        processed_emails = process_emails(emails)

    if not ordered_emails:  # Order emails only if not already ordered
        ordered_emails = order_emails_by_priority(processed_emails)

@app.route('/emails')
def show_emails():
    try:
        print('rendering emails...')
        # Fetch and process the emails only once
        fetch_and_process_emails()

        # Trim or modify email data
        for email in ordered_emails:
            email['body'] = email['body'][:200]  # Truncate the body for the frontend, for example

        #print(ordered_emails[0])
        # Step 3: Render the result as HTML using the 'emails.html' template
        return render_template('email_summary.html', emails=ordered_emails)

    except Exception as e:
        # Handle any errors that may occur during fetching/processing
        return f"An error occurred: {e}", 500