"""
app/analysis_utils.py

This module provides utility functions for processing and analyzing emails. 
It includes functions to classify email urgency, summarize email content, 
and process a list of emails by sorting them into different priority levels 
(high, medium, low). The classification and summarization use OpenAI's 
language models for processing.

Functions:
- classify_email_priority: Classifies the urgency of an email as 'high', 'medium', or 'low'.
- summarize_email_body: Summarizes the body of an email, highlighting key action items and urgent details.
- process_emails: Processes a list of emails, classifying them by priority and generating summaries.

Raises:
- ValueError: If input data is invalid or malformed.
- openai.APIError: If there is an error during the OpenAI API call.
- Exception: If any unexpected error occurs during processing.
"""

import openai
import logging
import json

def classify_email_priority(email_text):
    """
    Classifies the urgency of an email into 'high', 'medium', or 'low' priority using a language model.

    Args:
        email_text (str): The content of the email whose urgency is being classified.

    Returns:
        str: The priority classification ('high', 'medium', or 'low').

    Raises:
        ValueError: If the email_text is empty or None.
        openai.APIError: If there is an error during the OpenAI API call.
        Exception: If any other unexpected error occurs.
    """
    # Validate the input email_text
    if not email_text or not isinstance(email_text, str):
        logging.error("Invalid email text: %s", email_text)
        raise ValueError("The email text must be a non-empty string.")

    try:
        logging.info("Classifying the urgency of the email.")
        
        # Prepare the messages for the LLM prompt
        messages = [
            {"role": "system", "content": "You are a highly efficient assistant trained to analyze and extract actionable information from emails in a consistent JSON format."},
            {"role": "user", "content": f"Classify the urgency of the following email:\n\n{email_text}\n\nRespond with 'high', 'medium', or 'low'. \
            Example response: 'Low'"}
        ]

        # Make the API call to OpenAI to classify the email urgency
        response = openai.chat.completions.create(
            model="gpt-4o-mini-2024-07-18",  # You can use other models like "gpt-3.5-turbo" for faster responses
            messages=messages,
            max_tokens=10,
            temperature=0
        )

        # Extract the classification from the response
        priority = response.choices[0].message.content.strip().lower()
        
        # Log the classification result
        logging.info("Email classified with priority: %s", priority)

        return priority

    except openai.APIError as e:
        # Log and raise error related to OpenAI API call failure
        logging.error("Error during OpenAI API call: %s", e)
        raise openai.APIError(f"Failed to classify email priority: {e}")

    except Exception as e:
        # Catch any other unexpected errors
        logging.error("Unexpected error while classifying email priority: %s", e)
        raise Exception(f"An error occurred while classifying the email priority: {e}")

def process_llm_response(response):
    """
    Process the JSON output from the LLM.
    
    Args:
        response (str): The raw JSON response from the LLM.
        
    Returns:
        dict: A dictionary containing the parsed data.
        
    Raises:
        ValueError: If the response is not valid JSON or is missing required fields.
    """
    try:
        # Remove markdown-style code fences if present
        if response.startswith("```json") and response.endswith("```"):
            response = response[7:-3].strip()

        # Parse the cleaned content as JSON
        data = json.loads(response) 

        # Validate required keys
        required_keys = ["summary", "key_dates_info", "key_action_items", "priority_score", "category", "contextual_insight"]
        for key in required_keys:
            if key not in data:
                logging.error(f"Missing required field: {key}")
                raise KeyError(f"Missing required field: {key}")

        # Log successful processing
        logging.info("Successfully processed LLM response: %s", data)

        return data

    except json.JSONDecodeError as e:
        logging.error("Failed to parse JSON response: %s", e)
        raise ValueError("Invalid JSON format in response") from e

    except KeyError as e:
        logging.error("Validation error in LLM response: %s", e)
        raise ValueError(f"Missing expected data in response: {e}") from e

    except Exception as e:
        logging.error("Unexpected error while processing LLM response: %s", e)
        raise Exception(f"An error occurred while processing the email for JSON: {e}")

def summarize_email_body(email_text):
    """
    Summarizes the body of an email by extracting actionable information and highlighting urgent requests or deadlines.

    Args:
        email_text (str): The content of the email to be summarized.

    Returns:
        str: A concise summary with key action items and urgent details.

    Raises:
        ValueError: If the email_text is empty or None.
        openai.APIError: If there is an error during the OpenAI API call.
        Exception: If any other unexpected error occurs.
    """
    # Validate the input email_text
    if not email_text or not isinstance(email_text, str):
        logging.error("Invalid email text: %s", email_text)
        raise ValueError("The email text must be a non-empty string.")

    try:
        logging.info("Summarizing the email body.")

        # Prepare the messages for the LLM prompt
        messages = [
            {"role": "system", "content": "You are a highly efficient assistant trained to analyze and extract actionable information from emails in a consistent JSON format."},
            {
                "role": "user",
                "content": """
                Analyze the following email and return a response in strict JSON format with these fields:
                
                {
                  "summary": "A concise overview of the email content (max 2 lines).",
                  "key_dates_info": [
                    {"date": "yyyy-mm-dd", "info": "A brief description of the event or deadline."}
                  ],
                  "key_action_items": [
                    {"action": "Describe the action", "responsible_party": "Person or team responsible, if identifiable."}
                  ],
                  "priority_score": "An integer from 0-100 indicating the urgency/importance of the email.",
                  "category": "One of: ['High Priority', 'Work', 'Personal', 'Promotions', 'Updates'].",
                  "contextual_insight": "A short explanation of why the email is categorized as above."
                }
                
                Follow these rules:
                - Ensure all date fields are in ISO 8601 format (yyyy-mm-dd).
                - Use null for fields where no information is found.
                - If no action items are detected, set "key_action_items" to an empty array.
                - Do not include extra text or formatting outside the JSON response.
                
                --- Email ---
                {email_text}
                """
            }
        ]

        # Make the API call to OpenAI to summarize the email
        response = openai.chat.completions.create(
            model="gpt-4o-mini-2024-07-18",  # You can use other models like "gpt-3.5-turbo"
            messages=messages,
            max_tokens=200,  # Adjust based on summary length
            temperature=0.7
        )

        # Extract the summary from the response
        #summary = response.choices[0].message.content.strip()

        try:
            content = response.choices[0].message.content.strip()

            result = process_llm_response(content)
            logging.info("Processed Data: %s", result)
        except ValueError as e:
            logging.error("Error processing LLM response: %s", e)

        # Log the summary result
        logging.info("Email summary generated.")

        return result

    except openai.APIError as e:
        # Log and raise error related to OpenAI API call failure
        logging.error("Error during OpenAI API call: %s", e)
        raise openai.APIError(f"Failed to summarize email: {e}")

    except Exception as e:
        # Catch any other unexpected errors
        logging.error("Unexpected error while summarizing email: %s", e)
        raise Exception(f"An error occurred while summarizing the email: {e}")

def order_emails_by_priority(emails):
    """Order emails by priority from high to low."""
    # First, classify emails by priority
    classified_emails = {'high': [], 'medium': [], 'low': []}

    for email in emails:
        priority = email.get('priority', 'low')
        if priority == 'high':
            classified_emails['high'].append(email)
        elif priority == 'medium':
            classified_emails['medium'].append(email)
        else:
            classified_emails['low'].append(email)

    # Combine the lists in high to low priority order
    return classified_emails['high'] + classified_emails['medium'] + classified_emails['low']

def process_emails(emails):
    """
    Processes and summarizes emails, sorting them by priority (high, medium, low) using LLM.

    Args:
        emails (list of dict): A list of email dictionaries, where each dictionary contains 'sender', 'subject', and 'body' of the email.

    Returns:
        list of dict: The list of emails with added 'priority' and 'summary' fields.
    
    Raises:
        ValueError: If the input emails list is empty or malformed.
        Exception: If any unexpected error occurs during processing.
    """
    # Validate emails input
    if not emails or not isinstance(emails, list):
        logging.error("Invalid input: %s", emails)
        raise ValueError("The input must be a non-empty list of emails.")

    # Initialize a dictionary to classify emails by priority
    classified_emails = {'high': [], 'medium': [], 'low': []}

    try:
        # Step 1: Classify emails and store them by priority
        for email in emails:
            if 'sender' not in email or 'subject' not in email or 'body' not in email:
                logging.warning("Email is missing required fields: %s", email)
                continue

            email_text = f"From: {email['sender']}\nSubject: {email['subject']}\nBody: {email['body']}"
            
            # Classify the email priority
            try:
                priority = classify_email_priority(email_text)
            except Exception as e:
                logging.error("Error classifying email priority: %s", e)
                continue
            email['priority'] = priority
            
            # Store email in the appropriate priority list
            if priority == 'high':
                classified_emails['high'].append(email)
            elif priority == 'medium':
                classified_emails['medium'].append(email)
            else:
                classified_emails['low'].append(email)

        # Step 2: Process emails by priority order (high -> medium -> low)
        #for priority in ['high', 'medium', 'low']:
        for priority in ['high']:
            if classified_emails[priority]:
                logging.info(f"Processing {priority.capitalize()} Priority Emails")
                print(f"\nProcessing {priority.capitalize()} Priority Emails:\n")

                for email in classified_emails[priority]:
                    email_text = f"From: {email['sender']}\nSubject: {email['subject']}\nBody: {email['body']}"
                    try:
                        summary = summarize_email_body(email_text)
                        email.update({
                            'summary': summary.get("summary", "(No summary available)"),
                            'key_dates_info': summary.get("key_dates_info", []),
                            'key_action_items': summary.get("key_action_items", []),
                            'priority_score': summary.get("priority_score", "0"),
                            'category': summary.get("category", ""),
                            'contextual_insight': summary.get("contextual_insight", ""),
                        })

                        # Log success
                        logging.info(f"Successfully summarized email from {email['sender']} with subject '{email['subject']}'.")
                    except Exception as e:
                        # Handle errors and log them
                        logging.error(f"Error summarizing email from {email['sender']}: {e}")
                        email['summary'] = "(Error summarizing email)"
                        email['key_dates_info'] = []
                        email['key_action_items'] = []
                        email['priority_score'] = "0"
                        email['category'] = ""
                        email['contextual_insight'] = ""
                    
                    # Print basic email info (for debugging purposes)
                    print(f"From: {email['sender']}")
                    print(f"Subject: {email['subject']}")
                    print(f"Priority: {priority.capitalize()}")
                    print(f"Summary: {email.get('summary', 'No summary')}")
                    print(f"Priority Score: {email.get('priority_score')}")
                    print(f"Category: {email.get('category')}")
                    print(f"Context: {email.get('contextual_insight')}")
                    print("-" * 40)

        return emails

    except Exception as e:
        logging.error("Unexpected error during email processing: %s", e)
        raise Exception(f"An error occurred while processing emails: {e}")