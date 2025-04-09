import asyncio
import smtplib
import email.encoders
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
import logging
import imaplib
from typing import List, Optional, Tuple

# Assuming config.py and imap_client.py are in the same directory
from .config import EMAIL_CONFIG
from .imap_client import get_email_content_async # Needed for forwarding

log = logging.getLogger(__name__)

async def send_email_async(
    to_addresses: list[str],
    subject: str,
    content: str,
    cc_addresses: list[str] | None = None,
    attachments: list[tuple] | None = None
) -> None:
    """Asynchronously send an email with optional attachments.

    Args:
        to_addresses: List of recipient email addresses
        subject: Email subject
        content: Email body content
        cc_addresses: Optional list of CC recipients
        attachments: Optional list of attachments as tuples (filename, content_type, binary_data)
    """
    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = EMAIL_CONFIG["email"]
        msg['To'] = ', '.join(to_addresses)
        if cc_addresses:
            msg['Cc'] = ', '.join(cc_addresses)
        msg['Subject'] = subject

        # Add body
        msg.attach(MIMEText(content, 'plain', 'utf-8'))

        # Add attachments if provided
        if attachments:
            for attachment in attachments:
                filename, content_type, binary_data = attachment
                maintype, subtype = content_type.split('/', 1) if '/' in content_type else (content_type, '')

                # Create attachment part
                part = MIMEBase(maintype, subtype)
                part.set_payload(binary_data)
                email.encoders.encode_base64(part)

                # Add header
                part.add_header('Content-Disposition', 'attachment', filename=filename)
                msg.attach(part)

        # Connect to SMTP server and send email
        def send_sync():
            # Use context manager for SMTP connection
            with smtplib.SMTP(EMAIL_CONFIG["smtp_server"], EMAIL_CONFIG["smtp_port"]) as smtp_server:
                smtp_server.set_debuglevel(0) # 0 for no debug output, 1 for basic
                log.debug(f"Connecting to {EMAIL_CONFIG['smtp_server']}:{EMAIL_CONFIG['smtp_port']}")

                # Start TLS
                log.debug("Starting TLS")
                smtp_server.starttls()

                # Login
                log.debug(f"Logging in as {EMAIL_CONFIG['email']}")
                smtp_server.login(EMAIL_CONFIG["email"], EMAIL_CONFIG["password"])

                # Send email
                all_recipients = to_addresses + (cc_addresses or [])
                log.info(f"Sending email to: {all_recipients} Subject: {subject}")
                result = smtp_server.send_message(msg, EMAIL_CONFIG["email"], all_recipients)

                if result:
                    # send_message returns a dict of failed recipients
                    log.error(f"Failed to send to some recipients: {result}")
                    raise Exception(f"Failed to send to some recipients: {result}")

                log.info("Email sent successfully")

        # Run the synchronous send function in the executor
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, send_sync)

    except Exception as e:
        log.error(f"Error in send_email_async: {str(e)}", exc_info=True)
        raise # Re-raise the exception to be caught by the caller

async def forward_email_async(
    mail: imaplib.IMAP4_SSL, # Pass IMAP connection for fetching
    email_id: str,
    to_addresses: list[str],
    subject_prefix: str = "Fwd: ",
    additional_message: str = "",
    cc_addresses: list[str] | None = None
) -> None:
    """Forward an email with its attachments to new recipients.

    Args:
        mail: Active IMAP connection object (needed to fetch original email)
        email_id: ID of the email to forward
        to_addresses: List of recipient email addresses
        subject_prefix: Prefix to add to the original subject (default: "Fwd: ")
        additional_message: Optional message to add before the forwarded content
        cc_addresses: Optional list of CC recipients
    """
    try:
        # Get the original email content using the passed IMAP connection
        log.info(f"Fetching original email content for ID {email_id} to forward.")
        email_content = await get_email_content_async(mail, email_id)

        # Extract original email details
        original_from = email_content.get("from", "Unknown")
        original_date = email_content.get("date", "Unknown")
        original_subject = email_content.get("subject", "No Subject")
        original_content = email_content.get("content", "")

        # Create the forwarded subject
        if not original_subject.startswith(subject_prefix):
            forwarded_subject = f"{subject_prefix}{original_subject}"
        else:
            forwarded_subject = original_subject

        # Create the forwarded content with headers
        forwarded_body = additional_message
        if additional_message:
            forwarded_body += "\n\n"

        forwarded_body += f"""---------- Forwarded message ---------
"""
        forwarded_body += f"From: {original_from}\n"
        forwarded_body += f"Date: {original_date}\n"
        forwarded_body += f"Subject: {original_subject}\n"
        forwarded_body += f"To: {email_content.get('to', 'Unknown')}\n"

        if email_content.get('cc'):
            forwarded_body += f"Cc: {email_content.get('cc')}\n"

        forwarded_body += "\n"
        forwarded_body += original_content

        # Get attachments from the original email (requires fetching raw message again)
        attachments = []
        log.info(f"Fetching raw email {email_id} again for attachments.")
        loop = asyncio.get_event_loop()
        # We need the raw RFC822 data to parse attachments correctly
        status, msg_data = await loop.run_in_executor(None, lambda: mail.fetch(email_id, '(RFC822)'))
        if status != 'OK':
             raise Exception(f"Failed to fetch raw email {email_id} for attachments. Status: {status}")

        email_body_raw = email.message_from_bytes(msg_data[0][1])

        if email_body_raw.is_multipart():
            for part in email_body_raw.walk():
                content_disposition = str(part.get("Content-Disposition"))

                # Check if this part is an attachment
                if "attachment" in content_disposition:
                    filename = part.get_filename()
                    if filename:
                        content_type = part.get_content_type()
                        binary_data = part.get_payload(decode=True)
                        if binary_data:
                            log.debug(f"Found attachment: {filename}, Type: {content_type}")
                            attachments.append((filename, content_type, binary_data))
                        else:
                            log.warning(f"Attachment '{filename}' has no binary data.")
                    else:
                         log.warning(f"Part disposition is attachment, but no filename found.")


        # Send the forwarded email with attachments using send_email_async
        log.info(f"Sending forwarded email to {to_addresses} with subject '{forwarded_subject}'")
        await send_email_async(
            to_addresses=to_addresses,
            subject=forwarded_subject,
            content=forwarded_body,
            cc_addresses=cc_addresses,
            attachments=attachments
        )
        log.info(f"Email ID {email_id} forwarded successfully.")

    except Exception as e:
        log.error(f"Error in forward_email_async for ID {email_id}: {str(e)}", exc_info=True)
        raise # Re-raise the exception
