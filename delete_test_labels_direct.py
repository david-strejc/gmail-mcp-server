#!/usr/bin/env python3
import sys
import os
import re

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from email_client.config import EMAIL_CONFIG
import imaplib
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

def delete_test_labels():
    """Delete all Gmail labels containing 'test' (case insensitive)."""
    # Connect to Gmail
    mail = imaplib.IMAP4_SSL(EMAIL_CONFIG["imap_server"], 993)  # Default IMAP SSL port
    log.info(f"Connecting to {EMAIL_CONFIG['imap_server']} with {EMAIL_CONFIG['email']}")
    mail.login(EMAIL_CONFIG["email"], EMAIL_CONFIG["password"])
    log.info("Login successful")
    
    try:
        # List all labels
        log.info("Listing labels...")
        typ, data = mail.list()
        if typ != 'OK':
            log.error(f"Failed to list labels: {typ}")
            return
        
        # Extract label names
        labels = []
        for item in data:
            if isinstance(item, bytes):
                decoded = item.decode('utf-8')
                log.debug(f"Raw label data: {decoded}")
                # Extract the label name from the response
                # Format is typically: '(\\HasNoChildren) "/" "LabelName"'
                match = re.search(r'"([^"]+)"$', decoded)
                if match:
                    label_name = match.group(1)
                    labels.append(label_name)
        
        log.info(f"Found {len(labels)} total labels")
        
        # Filter for test labels
        test_pattern = re.compile(r'test', re.IGNORECASE)
        test_labels = [label for label in labels if test_pattern.search(label)]
        
        if not test_labels:
            log.info("No test labels found.")
            return
        
        log.info(f"Found {len(test_labels)} test labels to delete: {test_labels}")
        
        # Delete each test label using direct IMAP command
        for label in test_labels:
            try:
                log.info(f"Deleting label: {label}")
                # Try with different encodings and formats
                try:
                    # Try direct deletion
                    status, response = mail.delete(label)
                    log.info(f"Delete response: {status}, {response}")
                    if status == 'OK':
                        log.info(f"Successfully deleted label: {label}")
                        continue
                except Exception as e:
                    log.warning(f"First attempt failed: {str(e)}")
                
                try:
                    # Try with quotes
                    status, response = mail.delete(f'"{label}"')
                    log.info(f"Delete response (quoted): {status}, {response}")
                    if status == 'OK':
                        log.info(f"Successfully deleted label with quotes: {label}")
                        continue
                except Exception as e:
                    log.warning(f"Second attempt failed: {str(e)}")
                
                try:
                    # Try with UTF-7 encoding
                    encoded_label = label.encode('utf-7')
                    status, response = mail.delete(encoded_label)
                    log.info(f"Delete response (utf-7): {status}, {response}")
                    if status == 'OK':
                        log.info(f"Successfully deleted label with utf-7: {label}")
                        continue
                except Exception as e:
                    log.warning(f"Third attempt failed: {str(e)}")
                
                log.error(f"All attempts to delete label '{label}' failed")
            except Exception as e:
                log.error(f"Error deleting label '{label}': {str(e)}")
    
    finally:
        # Logout
        mail.logout()
        log.info("Logged out")

if __name__ == "__main__":
    delete_test_labels()
