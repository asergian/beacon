"""
app/email_utils.py

This module contains utility functions for interacting with an email server 
using the IMAP protocol. It includes functions to connect to the email server, 
search for emails, fetch email content (such as subject, sender, and body), 
and extract relevant data from email messages.

Functions:
- connect_to_email_server: Establishes a connection to the email server using IMAP.
- search_emails: Searches for emails in the INBOX folder based on a date range (days/weeks).
- fetch_email_data: Fetches the envelope (metadata) and body of a specific email by its message ID.
- decode_subject: Decodes a raw email subject header into a human-readable string.
- decode_sender: Decodes the sender’s email address from a structured address object.
- extract_email_body: Extracts the plain text or HTML body from an email message.
- extract_emails: Extracts subject, sender, and body for each email given a list of message IDs.
- fetch_emails: Connects to the server, searches for emails from the past week, and returns relevant data.

Dependencies:
- imapclient: For connecting to and interacting with the email server.
- email: For parsing email messages.
- email.header: For decoding email headers (like subject).
- datetime: For manipulating date and time (searching for emails within specific date ranges).
- bs4 (BeautifulSoup): For extracting text from HTML bodies.

Raises:
- ValueError: If input parameters are invalid (e.g., non-positive integers or missing required parameters).
- IMAPClient.Error: If errors occur during connection, login, or IMAP operations.
- KeyError: If an expected message ID is missing in the server response.
- TypeError: If input types are incorrect (e.g., non-string types for subject).
- AttributeError: If required attributes are missing from sender address objects.

This module is useful for automating the process of retrieving and processing email data, such as 
email content analysis, archiving, or triggering actions based on email content.
"""

from . import app  # Import the Config class from config.py

import logging

from imapclient import IMAPClient
import email
from email.header import decode_header
from datetime import datetime, timedelta

from bs4 import BeautifulSoup

def connect_to_email_server(server, email, password):
    """
    Establishes a connection to an email server using IMAP.

    Args:
        server (str): The hostname or IP address of the email server.
        email (str): The email address used to log in to the server.
        password (str): The password associated with the email address.

    Returns:
        IMAPClient: An instance of IMAPClient representing the connection to the server.

    Raises:
        ValueError: If any input parameter is invalid (e.g., empty or None).
        IMAPClient.Error: If the login attempt fails or the server is unreachable.
    """

    # Validate input parameters
    if not isinstance(server, str) or not server:
        raise ValueError("The server must be a non-empty string.")
    if not isinstance(email, str) or not email:
        raise ValueError("The email must be a non-empty string.")
    if not isinstance(password, str) or not password:
        raise ValueError("The password must be a non-empty string.")

    try:
        logging.info("Attempting to connect to the email server at %s", server)
        # Initialize the IMAP client with the provided server details
        client = IMAPClient(server)

        logging.info("Attempting to log in as %s", email)
        # Attempt to log in with the provided email and password
        client.login(email, password)
        logging.info("Successfully logged in as %s", email)

    except IMAPClient.Error as e:
        # Handle login or connection errors gracefully
        logging.error("Failed to connect or log in to the email server: %s", e)
        raise IMAPClient.Error(f"Failed to connect or log in to the email server: {e}")
    
    return client

def search_emails(client, days=None, weeks=None):
    """
    Searches for emails in the INBOX folder based on the specified date range.

    Args:
        client (IMAPClient): The email client object connected to the server.
        days (int, optional): Number of days from today to search emails. 
                              Must be a positive integer if provided.
        weeks (int, optional): Number of weeks from today to search emails.
                               Must be a positive integer if provided.

    Returns:
        list: A list of email IDs matching the search criteria.

    Raises:
        ValueError: If neither 'days' nor 'weeks' is provided, or if the values are invalid.
        IMAPClient.Error: If there's an issue with the IMAP operations.
    """
    # Validate input parameters
    if days is None and weeks is None:
        logging.error("Neither 'days' nor 'weeks' is provided.")
        raise ValueError("Either 'days' or 'weeks' parameter must be provided.")
    if days is not None and (not isinstance(days, int) or days <= 0):
        logging.error("'days' must be a positive integer but got %s", days)
        raise ValueError("'days' must be a positive integer.")
    if weeks is not None and (not isinstance(weeks, int) or weeks <= 0):
        logging.error("'weeks' must be a positive integer but got %s", weeks)
        raise ValueError("'weeks' must be a positive integer.")

    try:
        logging.info("Selecting the INBOX folder for searching.")
        # Ensure the INBOX folder is selected for searching
        client.select_folder("INBOX")
    except IMAPClient.Error as e:
        logging.error("Failed to select INBOX folder: %s", e)
        raise IMAPClient.Error(f"Failed to select INBOX folder: {e}")

    try:
        # Calculate the start date based on input
        if days is not None:
            start_date = datetime.now() - timedelta(days=days)
        elif weeks is not None:
            start_date = datetime.now() - timedelta(weeks=weeks)

        # Format the date as required by IMAP (DD-MMM-YYYY)
        start_date_str = start_date.strftime("%d-%b-%Y")
        logging.info("Searching for emails since %s", start_date_str)

        # Perform the search
        email_ids = client.search(["SINCE", start_date_str])
        logging.info("Found %d email(s) matching the search criteria.", len(email_ids))
    
    except IMAPClient.Error as e:
        logging.error("Failed to search emails: %s", e)
        raise IMAPClient.Error(f"Failed to search emails: {e}")

    return email_ids

def fetch_email_data(client, message_id):
    """
    Fetches the email envelope and body for a specific message ID.

    Args:
        client (IMAPClient): The email client object connected to the server.
        message_id (int): The ID of the email message to fetch.

    Returns:
        tuple: A tuple containing:
            - envelope (dict): Metadata about the email, such as subject, sender, and recipient.
            - email_message (email.message.Message): The full email message parsed into an object.

    Raises:
        ValueError: If the message ID is not a positive integer.
        IMAPClient.Error: If fetching the email data fails.
        KeyError: If the specified message ID is not found in the server response.
    """
    # Validate input
    if not isinstance(message_id, int) or message_id <= 0:
        logging.error("Invalid message_id: %s. Must be a positive integer.", message_id)
        raise ValueError("The message_id must be a positive integer.")

    logging.info("Fetching email data for message ID: %s", message_id)

    try:
        # Fetch envelope and body data for the given message ID
        response = client.fetch([message_id], ["ENVELOPE", "BODY[]"])

        # Ensure the message ID is present in the response
        if message_id not in response:
            logging.error("Message ID %s not found in server response.", message_id)
            raise KeyError(f"Message ID {message_id} not found in the server response.")

        envelope_data = response[message_id]
        envelope = envelope_data[b"ENVELOPE"]
        email_message = email.message_from_bytes(envelope_data[b"BODY[]"])

        # Log metadata of the fetched email
        subject = envelope.subject.decode() if envelope.subject else "No Subject"
        sender = envelope.from_[0].mailbox.decode() if envelope.from_ else "Unknown Sender"
        logging.info("Fetched email - Subject: %s, Sender: %s", subject, sender)
    except IMAPClient.Error as e:
        logging.error("Failed to fetch email data for message ID %s: %s", message_id, e)
        raise
    except KeyError as e:
        logging.error("Missing expected data for message ID %s: %s", message_id, e)
        raise

    logging.info("Successfully fetched email data for message ID: %s", message_id)
    return envelope, email_message

def decode_subject(raw_subject):
    """
    Decodes the email subject from a raw header into a human-readable string.

    Args:
        raw_subject (bytes or str): The raw subject header of the email. 
                                    Can be a string or bytes object.

    Returns:
        str: The decoded subject as a readable string. Returns "(No Subject)" if the input is empty or invalid.

    Raises:
        TypeError: If the input type is not bytes or str.
    """
    # Validate input
    if not isinstance(raw_subject, (bytes, str)):
        logging.error("Invalid input type for raw_subject: %s. Expected bytes or str.", type(raw_subject).__name__)
        raise TypeError("raw_subject must be of type bytes or str.")

    # Handle empty subject
    if not raw_subject:
        logging.warning("Empty subject provided. Returning default '(No Subject)'.")
        return "(No Subject)"

    try:
        # Decode the subject header
        if isinstance(raw_subject, bytes):
            raw_subject = raw_subject.decode(errors="replace")
        decoded = decode_header(raw_subject)
        decoded_subject = ''.join(
            part.decode(encoding or 'utf-8', errors="replace") if isinstance(part, bytes) else part
            for part, encoding in decoded
        )
        logging.info("Decoded subject successfully: %s", decoded_subject)
        return decoded_subject
    except Exception as e:
        # Log and handle unexpected decoding errors
        logging.error("Failed to decode subject. Returning default '(No Subject)': %s", e)
        return "(No Subject)"

def decode_sender(sender_address):
    """
    Decodes the sender's email address from a structured address object.

    Args:
        sender_address (object): An object with `mailbox` and `host` attributes, 
                                 which represent the local part and domain of an email address.

    Returns:
        str: The decoded email address in the format "mailbox@host".

    Raises:
        AttributeError: If the sender_address object does not have the required attributes.
        ValueError: If either the `mailbox` or `host` is missing or empty.
    """
    # Validate input
    if not hasattr(sender_address, "mailbox") or not hasattr(sender_address, "host"):
        logging.error("Invalid sender_address object. Missing 'mailbox' or 'host' attributes.")
        raise AttributeError("sender_address must have 'mailbox' and 'host' attributes.")

    # Decode mailbox and host
    try:
        mailbox = (
            sender_address.mailbox.decode() 
            if isinstance(sender_address.mailbox, bytes) 
            else sender_address.mailbox
        )
        host = (
            sender_address.host.decode() 
            if isinstance(sender_address.host, bytes) 
            else sender_address.host
        )

        # Check for missing or empty values
        if not mailbox or not host:
            logging.error("Mailbox or host is missing or empty: mailbox=%s, host=%s", mailbox, host)
            raise ValueError("Both mailbox and host must be non-empty.")

        email_address = f"{mailbox}@{host}"
        logging.info("Decoded sender email address: %s", email_address)
        return email_address
    except Exception as e:
        logging.error("Failed to decode sender address: %s", e)
        raise

def extract_email_body(email_message):
    """
    Extracts the plain text or HTML body from an email message.

    Args:
        email_message (email.message.Message): The email message object.

    Returns:
        str: The extracted email body as plain text. If no body is found, returns "(No Body)".

    Raises:
        ValueError: If the email message is invalid or empty.
    """
    # Validate input
    if email_message is None:
        logging.error("The email_message is None. Cannot extract body.")
        raise ValueError("The email_message must not be None.")

    try:
        logging.info("Extracting body from the email message.")

        # Handle multipart emails
        if email_message.is_multipart():
            logging.info("Email is multipart. Iterating through parts.")
            for part in email_message.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))

                # Skip attachments
                if "attachment" in content_disposition:
                    continue

                payload = part.get_payload(decode=True)
                if payload:
                    if content_type == "text/plain":
                        logging.info("Plain text body found in multipart email.")
                        return payload.decode(errors="replace")
                    elif content_type == "text/html":
                        logging.info("HTML body found in multipart email. Extracting text.")
                        soup = BeautifulSoup(payload.decode(errors="replace"), "html.parser")
                        return soup.get_text()

        # Handle non-multipart emails
        logging.info("Email is not multipart. Extracting body.")
        content_type = email_message.get_content_type()
        payload = email_message.get_payload(decode=True)
        if payload:
            if content_type == "text/plain":
                logging.info("Plain text body found in non-multipart email.")
                return payload.decode(errors="replace")
            elif content_type == "text/html":
                logging.info("HTML body found in non-multipart email. Extracting text.")
                soup = BeautifulSoup(payload.decode(errors="replace"), "html.parser")
                return soup.get_text()

        # No valid body found
        logging.warning("No valid body found in the email.")
        return "(No Body)"
    except Exception as e:
        logging.error("An error occurred while extracting the email body: %s", e)
        raise

def extract_emails(client, message_ids):
    """
    Extracts the subject, sender, and body from each email identified by the provided message IDs.

    Args:
        client: The email client object used to interact with the email server.
        message_ids (list): A list of message IDs for which email data is to be extracted.

    Returns:
        list: A list of dictionaries, each containing the 'subject', 'sender', and 'body' of an email.

    Raises:
        ValueError: If no message IDs are provided or if the fetch operation fails.
    """
    if not message_ids:
        logging.error("No message IDs provided. Cannot extract emails.")
        raise ValueError("message_ids must be a non-empty list.")

    emails = []
    for message_id in message_ids:
        try:
            logging.info("Extracting data for message ID: %s", message_id)
            # Fetch the email data (envelope and message)
            envelope, email_message = fetch_email_data(client, message_id)

            # Decode subject, sender, and body
            subject = decode_subject(envelope.subject)
            sender = decode_sender(envelope.from_[0])
            body = extract_email_body(email_message)

            # Append the extracted data to the emails list
            emails.append({
                'subject': subject,
                'sender': sender,
                'body': body
            })

            logging.info("Successfully extracted email data for message ID: %s", message_id)
        except Exception as e:
            # Log errors for individual emails but continue processing the rest
            logging.error("Failed to extract data for message ID %s: %s", message_id, e)

    if not emails:
        logging.warning("No emails were successfully extracted.")
    return emails

def fetch_emails():
    """
    Connects to the email server, searches for emails from the past week, 
    and fetches relevant data (subject, sender, body) for each email.

    Returns:
        list: A list of dictionaries containing 'subject', 'sender', and 'body' for each email, 
              or None if no emails were found or if an error occurred.

    Raises:
        Exception: If there are any issues connecting to the server or fetching emails.
    """
    client = None
    try:
        logging.info("Starting to fetch emails for today.")

        # Use the configuration to get IMAP server settings
        imap_server = app.config['IMAP_SERVER']
        email = app.config['EMAIL']
        password = app.config['IMAP_PASSWORD']
        
        # Connect to the email server
        client = connect_to_email_server(imap_server, email, password)
        logging.info("Connected to email server successfully.")
        
        # Search for emails from the past week
        message_ids = search_emails(client, days=1)

        if not message_ids:
            logging.info(f"No emails found for the past week ({datetime.now().strftime('%d-%b-%Y')}).")
            return None
        else:
            logging.info(f"Found {len(message_ids)} email(s) to fetch.")
            # Fetch email content and return a list of email data
            emails = extract_emails(client, message_ids)
            return emails

    except Exception as e:
        logging.error(f"Error while fetching emails: {e}")
        print(f"Error while fetching emails: {e}")
        return None

    finally:
        # Ensure the client is logged out
        if client:
            client.logout()
            logging.info("Logged out from email server.")