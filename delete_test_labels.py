#!/usr/bin/env python3
import asyncio
import sys
import os
import re

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from email_client.imap_client import delete_label_async
from email_client.config import EMAIL_CONFIG
import imaplib
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

async def delete_test_labels():
    """Delete all Gmail labels containing 'test' (case insensitive)."""
    # Connect to Gmail
    mail = imaplib.IMAP4_SSL(EMAIL_CONFIG["imap_server"], 993)  # Default IMAP SSL port
    mail.login(EMAIL_CONFIG["email"], EMAIL_CONFIG["password"])

    try:
        # List all labels
        typ, data = mail.list()
        if typ != 'OK':
            log.error(f"Failed to list labels: {typ}")
            return

        # Extract label names
        labels = []
        for item in data:
            if isinstance(item, bytes):
                decoded = item.decode('utf-8')
                # Extract the label name from the response
                # Format is typically: '(\\HasNoChildren) "/" "LabelName"'
                match = re.search(r'"([^"]+)"$', decoded)
                if match:
                    label_name = match.group(1)
                    labels.append(label_name)

        # Filter for test labels
        test_pattern = re.compile(r'test', re.IGNORECASE)
        test_labels = [label for label in labels if test_pattern.search(label)]

        if not test_labels:
            log.info("No test labels found.")
            return

        log.info(f"Found {len(test_labels)} test labels to delete: {test_labels}")

        # Delete each test label
        for label in test_labels:
            log.info(f"Deleting label: {label}")
            deleted = await delete_label_async(mail, label)
            if deleted:
                log.info(f"Successfully deleted label: {label}")
            else:
                log.warning(f"Failed to delete label: {label}")

    finally:
        # Logout
        mail.logout()

if __name__ == "__main__":
    asyncio.run(delete_test_labels())
