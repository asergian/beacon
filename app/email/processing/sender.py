import smtplib
import logging
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

class EmailSendingError(Exception):
    """Exception raised when email sending fails."""
    pass

class EmailSender:
    """
    A client for sending emails via SMTP.
    
    Attributes:
        server (str): SMTP server hostname
        email (str): Sender's email address
        password (str): Sender's email password
        port (int): SMTP server port
        use_tls (bool): Whether to use TLS connection
    """
    
    def __init__(
        self,
        server: str,
        email: str,
        password: str,
        port: int = 587,
        use_tls: bool = True
    ):
        """
        Initialize the SMTP email client.
        
        Args:
            server: SMTP server hostname
            email: Sender's email address
            password: Sender's email password
            port: SMTP server port (default 587)
            use_tls: Whether to use TLS connection (default True)
            
        Raises:
            ValueError: If any required parameters are missing or invalid
        """
        if not all([server, email, password]):
            raise ValueError("Server, email, and password must be provided")
        
        self.server = server
        self.email = email
        self.password = password
        self.port = port
        self.use_tls = use_tls
        
        # Configure logging
        self.logger = logging.getLogger(__name__)
    
    async def send_email(
        self,
        to: str,
        subject: str,
        content: str,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        reply_to: Optional[str] = None,
        html_content: Optional[str] = None
    ) -> bool:
        """
        Send an email via SMTP.
        
        Args:
            to: Recipient email address
            subject: Email subject
            content: Plain text email content
            cc: Optional list of CC recipients
            bcc: Optional list of BCC recipients
            reply_to: Optional reply-to email address
            html_content: Optional HTML content (if not provided, content will be used)
            
        Returns:
            bool: True if email was sent successfully, False otherwise
            
        Raises:
            EmailSendingError: If email sending fails
        """
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = formataddr(("Beacon", self.email))
            msg['To'] = to
            
            msg['Cc'] = ', '.join(cc) if cc else None
            msg['Reply-To'] = reply_to if reply_to else None
                
            # Add plain text and HTML parts
            msg.attach(MIMEText(content, 'plain'))
            msg.attach(MIMEText(html_content or content, 'html'))
            
            # Get all recipients
            recipients = [to] + (cc or []) + (bcc or [])
            
            # Send email using asyncio to avoid blocking
            return await self._send_message(msg, recipients)
        
        except Exception as e:
            error_msg = f"Failed to send email: {str(e)}"
            self.logger.error(error_msg)
            raise EmailSendingError(error_msg)
    
    async def _send_message(self, msg, recipients):
        """
        Send the email message via SMTP.
        
        Args:
            msg: The email message to send
            recipients: List of recipient email addresses
            
        Returns:
            bool: True if email was sent successfully
            
        Raises:
            EmailSendingError: If email sending fails
        """
        try:
            # Use asyncio to run blocking SMTP operations
            return await asyncio.to_thread(self._send_sync, msg, recipients)
        except Exception as e:
            error_msg = f"SMTP sending failed: {str(e)}"
            self.logger.error(error_msg)
            raise EmailSendingError(error_msg)
    
    def _send_sync(self, msg, recipients):
        """
        Synchronous method to send email via SMTP.
        
        Args:
            msg: The email message to send
            recipients: List of recipient email addresses
            
        Returns:
            bool: True if email was sent successfully
        """
        try:
            with smtplib.SMTP(self.server, self.port) as server:
                if self.use_tls:
                    server.starttls()
                server.login(self.email, self.password)
                server.sendmail(self.email, recipients, msg.as_string())
                self.logger.info(f"Email sent successfully to {', '.join(recipients)}")
                return True
        except Exception as e:
            self.logger.error(f"SMTP error: {str(e)}")
            raise 