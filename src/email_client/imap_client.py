import asyncio
import imaplib
import logging
import re
from typing import Optional, List, Dict

# Assuming utils.py is in the same directory
from .utils import format_email_summary, format_email_content

# Configure logging (or import logger from a central logging config)
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__) # Use module-specific logger if configured elsewhere

async def search_emails_async(mail: imaplib.IMAP4_SSL, limit: int, search_criteria: Optional[str] = None, raw_query: Optional[str] = None) -> list[dict]:
    """
    Asynchronously search emails with timeout and limit.
    Asynchronously search emails with timeout and limit.
    Uses raw_query (Gmail specific) if provided, otherwise uses standard search_criteria.
    """
    loop = asyncio.get_event_loop()
    try:
        if raw_query:
            # Use Gmail's X-GM-RAW extension
            search_args = ('X-GM-RAW', raw_query.encode('utf-8')) # Ensure raw_query is bytes
            log.debug(f"Executing IMAP X-GM-RAW search: {raw_query}")
            status, messages = await loop.run_in_executor(None, lambda: mail.search(None, *search_args))
            log.debug(f"IMAP X-GM-RAW search status: {status}, messages: {messages}")
            criteria_log_msg = f"raw query '{raw_query}'"
        elif search_criteria:
            # Use standard IMAP search
            log.debug(f"Executing standard IMAP search: {search_criteria}")
            status, messages = await loop.run_in_executor(None, lambda: mail.search(None, search_criteria))
            log.debug(f"IMAP standard search status: {status}, messages: {messages}")
            criteria_log_msg = f"criteria '{search_criteria}'"
        else:
            log.error("Search requires either search_criteria or raw_query.")
            raise ValueError("Search requires either search_criteria or raw_query.")

        if status != 'OK' or not messages or not messages[0]:
            log.info(f"No emails found matching {criteria_log_msg}.")
            return []

        email_list = []
        # Process messages in reverse order (newest first)
        message_ids = messages[0].split()
        message_ids.reverse()

        # Apply limit to the number of emails fetched
        message_ids_to_fetch = message_ids[:limit]
        log.info(f"Found {len(message_ids)} matching emails, fetching summaries for {len(message_ids_to_fetch)} (limit: {limit}).")

        for num in message_ids_to_fetch:
            log.debug(f"Fetching summary for email ID: {num.decode()}")
            status, msg_data = await loop.run_in_executor(None, lambda n=num: mail.fetch(n, '(RFC822)'))
            if status == 'OK':
                email_list.append(format_email_summary(msg_data))
            else:
                log.warning(f"Failed to fetch summary for email ID {num.decode()}: Status {status}")


        return email_list
    except Exception as e:
        log.error(f"Error searching emails: {str(e)}", exc_info=True)
        raise Exception(f"Error searching emails: {str(e)}")

async def get_email_content_async(mail: imaplib.IMAP4_SSL, email_id: str) -> dict:
    """Asynchronously get full content of a specific email."""
    loop = asyncio.get_event_loop()
    try:
        log.debug(f"Fetching content for email ID: {email_id}")
        status, msg_data = await loop.run_in_executor(None, lambda: mail.fetch(email_id, '(RFC822)'))
        log.debug(f"IMAP fetch content status: {status}")
        if status != 'OK':
             raise Exception(f"Failed to fetch email content for ID {email_id}. Status: {status}")
        return format_email_content(msg_data)
    except Exception as e:
        log.error(f"Error fetching email content for ID {email_id}: {str(e)}", exc_info=True)
        raise Exception(f"Error fetching email content: {str(e)}")

async def count_emails_async(mail: imaplib.IMAP4_SSL, search_criteria: str) -> int:
    """Asynchronously count emails matching the search criteria."""
    loop = asyncio.get_event_loop()
    try:
        log.debug(f"Executing IMAP count search: {search_criteria}")
        status, messages = await loop.run_in_executor(None, lambda: mail.search(None, search_criteria))
        log.debug(f"IMAP count search status: {status}, messages: {messages}")
        if status != 'OK':
             raise Exception(f"Failed to count emails. Status: {status}")
        count = len(messages[0].split()) if messages[0] else 0
        log.info(f"Found {count} emails matching criteria: {search_criteria}")
        return count
    except Exception as e:
        log.error(f"Error counting emails: {str(e)}", exc_info=True)
        raise Exception(f"Error counting emails: {str(e)}")

async def list_labels_async(mail: imaplib.IMAP4_SSL) -> list[dict]:
    """List all available Gmail labels."""
    try:
        loop = asyncio.get_event_loop()
        log.debug("Executing IMAP list labels command.")
        status, response = await loop.run_in_executor(None, lambda: mail.list())
        log.debug(f"IMAP list labels status: {status}")

        if status != 'OK':
            raise Exception(f"Failed to list labels: {status}")

        labels = []
        for item in response:
            # Parse the LIST response
            if isinstance(item, bytes):
                try:
                    item_str = item.decode('utf-7') # Gmail often uses modified UTF-7 for labels
                except UnicodeDecodeError:
                    try:
                        item_str = item.decode('utf-8', errors='ignore') # Fallback
                    except Exception as decode_err:
                        log.warning(f"Could not decode label item: {item}, Error: {decode_err}")
                        continue

                # Extract label name and attributes
                parts = item_str.split(' "', 1)
                if len(parts) == 2:
                    attributes = parts[0].strip()
                    name = parts[1].strip('"')

                    # Skip the [Gmail] parent folder which is not selectable
                    if '\\Noselect' in attributes and '[Gmail]' in name:
                        continue

                    labels.append({
                        "name": name,
                        "attributes": attributes,
                        "is_system": '[Gmail]' in name or name == 'INBOX'
                    })
        log.info(f"Found {len(labels)} labels.")
        return labels
    except Exception as e:
        log.error(f"Error in list_labels_async: {str(e)}", exc_info=True)
        raise Exception(f"Error listing labels: {str(e)}")


async def get_email_uid_async(mail: imaplib.IMAP4_SSL, email_id: str) -> Optional[str]:
    """Fetch the UID for a given email ID."""
    loop = asyncio.get_event_loop()
    try:
        # Ensure email_id is bytes
        email_id_bytes = email_id.encode('utf-8') if isinstance(email_id, str) else email_id
        log.debug(f"Fetching UID for email ID: {email_id_bytes.decode()}")

        status, response = await loop.run_in_executor(None, lambda: mail.fetch(email_id_bytes, '(UID)'))
        log.debug(f"IMAP fetch UID status: {status}, response: {response}")

        if status != 'OK' or not response or not isinstance(response[0], (bytes, tuple)):
            log.error(f"Failed to get UID for email {email_id}. Status: {status}, Response: {response}")
            return None

        # Handle tuple response (e.g., (b'FLAGS (\\Seen)', b' UID 1234'))
        if isinstance(response[0], tuple):
            response_str = b' '.join(filter(None, response[0])).decode('utf-8', errors='ignore')
        # Handle bytes response
        elif isinstance(response[0], bytes):
             response_str = response[0].decode('utf-8', errors='ignore')
        else:
             log.error(f"Unexpected response format for email ID {email_id}: {response}")
             return None

        log.debug(f"UID response string for email {email_id}: {response_str}")

        # Use regex to reliably extract UID
        uid_match = re.search(r'UID\s+(\d+)', response_str)
        if uid_match:
            uid = uid_match.group(1)
            log.info(f"Extracted UID {uid} for email ID {email_id}")
            return uid
        else:
            log.error(f"Could not parse UID from response for email {email_id}: {response_str}")
            return None

    except (imaplib.IMAP4.error, UnicodeDecodeError, IndexError, AttributeError) as e:
        log.error(f"Error fetching or parsing UID for email {email_id}: {str(e)}", exc_info=True)
        return None
    except Exception as e:
        log.error(f"Unexpected error fetching UID for email {email_id}: {str(e)}", exc_info=True)
        return None


async def create_label_async(mail: imaplib.IMAP4_SSL, label_name: str) -> bool:
    """Create a new Gmail label."""
    try:
        # Check if the label already exists
        log.debug(f"Checking if label '{label_name}' exists.")
        labels = await list_labels_async(mail)
        if any(label["name"] == label_name for label in labels):
            log.info(f"Label '{label_name}' already exists.")
            return False  # Label already exists

        # Create the label - Use modified UTF-7 encoding for label names
        try:
            encoded_label_name = label_name.encode('utf-7')
        except UnicodeEncodeError:
             log.error(f"Could not encode label name '{label_name}' to UTF-7.")
             # Fallback or raise error? For now, try utf-8 quoted
             encoded_label_name = f'"{label_name}"'.encode('utf-8')


        loop = asyncio.get_event_loop()
        log.info(f"Creating label: {label_name} (encoded: {encoded_label_name})")
        # The CREATE command expects the mailbox name to be encoded.
        # Standard requires modified UTF-7. Quotes might be needed depending on server.
        # Let's try encoding the name itself, not the quotes.
        status, response = await loop.run_in_executor(None, lambda: mail.create(encoded_label_name))
        log.debug(f"IMAP create label status: {status}, response: {response}")

        if status != 'OK':
             # Try with quotes if unquoted failed
             log.warning(f"Failed to create label '{label_name}' unquoted. Trying with quotes.")
             quoted_encoded_label = f'"{label_name}"'.encode('utf-7') # Assuming utf-7 is needed
             status, response = await loop.run_in_executor(None, lambda: mail.create(quoted_encoded_label))
             log.debug(f"IMAP create label (quoted) status: {status}, response: {response}")


        if status == 'OK':
            log.info(f"Label '{label_name}' created successfully.")
            return True
        else:
            log.error(f"Failed to create label '{label_name}': Status {status}, Response {response}")
            return False

    except Exception as e:
        log.error(f"Error in create_label_async for '{label_name}': {str(e)}", exc_info=True)
        # Don't re-raise, return False for failure
        return False


async def rename_label_async(mail: imaplib.IMAP4_SSL, old_label_name: str, new_label_name: str) -> bool:
    """Rename a Gmail label/folder."""
    try:
        # Check if the old label exists
        log.debug(f"Checking if old label '{old_label_name}' exists before renaming.")
        labels = await list_labels_async(mail)
        if not any(label["name"] == old_label_name for label in labels):
            log.warning(f"Old label '{old_label_name}' does not exist, cannot rename.")
            return False

        # Check if the new label name already exists
        if any(label["name"] == new_label_name for label in labels):
            log.warning(f"New label name '{new_label_name}' already exists, cannot rename.")
            return False

        # System labels cannot be renamed
        if '[Gmail]' in old_label_name or '[GoogleMail]' in old_label_name or old_label_name == 'INBOX':
             log.warning(f"Cannot rename system label '{old_label_name}'.")
             return False

        # Encode both old and new names using modified UTF-7
        try:
            encoded_old_name = old_label_name.encode('utf-7')
            encoded_new_name = new_label_name.encode('utf-7')
        except UnicodeEncodeError as e:
             log.error(f"Could not encode label names to UTF-7 for renaming: {e}")
             # Attempt with UTF-8 quoted as fallback? Less standard.
             # For now, let's return False if standard encoding fails.
             return False

        loop = asyncio.get_event_loop()
        log.info(f"Renaming label '{old_label_name}' to '{new_label_name}'")
        # The RENAME command expects encoded mailbox names.
        status, response = await loop.run_in_executor(None, lambda: mail.rename(encoded_old_name, encoded_new_name))
        log.debug(f"IMAP rename label status: {status}, response: {response}")

        # Note: Some servers might require quoting, but standard is unquoted encoded names.
        # If the above fails, could try quoted versions like mail.rename(f'"{old_label_name}"'.encode('utf-7'), f'"{new_label_name}"'.encode('utf-7'))

        if status == 'OK':
            log.info(f"Label '{old_label_name}' renamed to '{new_label_name}' successfully.")
            return True
        else:
            log.error(f"Failed to rename label '{old_label_name}' to '{new_label_name}': Status {status}, Response {response}")
            return False

    except Exception as e:
        log.error(f"Error in rename_label_async for '{old_label_name}' -> '{new_label_name}': {str(e)}", exc_info=True)
        return False


async def delete_label_async(mail: imaplib.IMAP4_SSL, label_name: str) -> bool:
    """Delete a Gmail label/folder."""
    try:
        # Check if the label exists first
        log.debug(f"Checking if label '{label_name}' exists before deletion.")
        labels = await list_labels_async(mail)
        if not any(label["name"] == label_name for label in labels):
            log.warning(f"Label '{label_name}' does not exist, cannot delete.")
            return False # Label doesn't exist

        # System labels cannot be deleted
        if '[Gmail]' in label_name or '[GoogleMail]' in label_name or label_name == 'INBOX':
             log.warning(f"Cannot delete system label '{label_name}'.")
             return False

        # Delete the label - Use modified UTF-7 encoding
        try:
            encoded_label_name = label_name.encode('utf-7')
        except UnicodeEncodeError:
             log.error(f"Could not encode label name '{label_name}' to UTF-7 for deletion.")
             # Fallback or raise error? Try utf-8 quoted
             encoded_label_name = f'"{label_name}"'.encode('utf-8')

        loop = asyncio.get_event_loop()
        log.info(f"Deleting label: {label_name} (encoded: {encoded_label_name})")
        # The DELETE command expects the mailbox name encoded.
        status, response = await loop.run_in_executor(None, lambda: mail.delete(encoded_label_name))
        log.debug(f"IMAP delete label status: {status}, response: {response}")

        if status != 'OK':
             # Try with quotes if unquoted failed
             log.warning(f"Failed to delete label '{label_name}' unquoted. Trying with quotes.")
             quoted_encoded_label = f'"{label_name}"'.encode('utf-7') # Assuming utf-7 is needed
             status, response = await loop.run_in_executor(None, lambda: mail.delete(quoted_encoded_label))
             log.debug(f"IMAP delete label (quoted) status: {status}, response: {response}")

        if status == 'OK':
            log.info(f"Label '{label_name}' deleted successfully.")
            return True
        else:
            log.error(f"Failed to delete label '{label_name}': Status {status}, Response {response}")
            return False

    except Exception as e:
        log.error(f"Error in delete_label_async for '{label_name}': {str(e)}", exc_info=True)
        return False


async def apply_label_async(mail: imaplib.IMAP4_SSL, uid: str, label_name: str) -> bool:
    """Apply a label to an email using its UID."""
    loop = asyncio.get_event_loop()
    try:
        # Gmail expects labels without quotes for STORE command with X-GM-LABELS
        # The label name itself might need encoding if it contains non-ASCII chars,
        # but the command argument format is `(label1 label2)` without quotes.
        # Let's assume label_name is already correctly representable or ASCII for now.
        # If issues arise, encoding might be needed here.
        formatted_label = f'({label_name})' # Parentheses seem required based on test script
        uid_bytes = uid.encode('utf-8') # UID must be bytes for uid command

        log.info(f"Applying label '{label_name}' to UID {uid}")
        status, response = await loop.run_in_executor(
            None,
            # Pass label name as a quoted string literal for X-GM-LABELS
            lambda: mail.uid('STORE', uid_bytes, '+X-GM-LABELS', f'"{label_name}"')
        )
        log.info(f"Apply label response for UID {uid}: Status={status}, Response={response}")
        # Removed fallback logic

        return status == 'OK'
    except Exception as e:
        log.error(f"Error applying label '{label_name}' to UID {uid}: {str(e)}", exc_info=True)
        return False


async def apply_labels_batch_async(mail: imaplib.IMAP4_SSL, email_ids: List[str], label_name: str) -> bool:
    """Apply a label to a batch of emails using their sequence numbers."""
    if not email_ids:
        return False
    loop = asyncio.get_event_loop()
    try:
        # Format sequence numbers as comma-separated string (e.g., "1,3,5")
        id_set = ",".join(email_ids)
        id_set_bytes = id_set.encode('utf-8')

        # Use STORE without UID prefix to operate on sequence numbers
        log.info(f"Applying label '{label_name}' to sequence numbers: {id_set}")
        status, response = await loop.run_in_executor(
            None,
            # Pass label name as a quoted string literal for X-GM-LABELS
            lambda: mail.store(id_set_bytes, '+X-GM-LABELS', f'"{label_name}"')
        )
        log.info(f"Batch apply label response for IDs {id_set}: Status={status}, Response={response}")
        # Removed fallback logic

        return status == 'OK'
    except Exception as e:
        log.error(f"Error batch applying label '{label_name}' to IDs {id_set}: {str(e)}", exc_info=True)
        return False


async def remove_label_async(mail: imaplib.IMAP4_SSL, uid: str, label_name: str) -> bool:
    """Remove a label from an email using its UID."""
    loop = asyncio.get_event_loop()
    try:
        # Similar logic to apply_label regarding encoding and formatting
        formatted_label = f'({label_name})'
        uid_bytes = uid.encode('utf-8')

        log.info(f"Removing label '{label_name}' from UID {uid}")
        status, response = await loop.run_in_executor(
            None,
            # Pass label name as a quoted string literal for X-GM-LABELS
            lambda: mail.uid('STORE', uid_bytes, '-X-GM-LABELS', f'"{label_name}"')
        )
        log.info(f"Remove label response for UID {uid}: Status={status}, Response={response}")
        # Removed fallback logic

        return status == 'OK'
    except Exception as e:
        log.error(f"Error removing label '{label_name}' from UID {uid}: {str(e)}", exc_info=True)
        return False


async def remove_labels_batch_async(mail: imaplib.IMAP4_SSL, email_ids: List[str], label_name: str) -> bool:
    """Remove a label from a batch of emails using their sequence numbers."""
    if not email_ids:
        return False
    loop = asyncio.get_event_loop()
    try:
        id_set = ",".join(email_ids)
        id_set_bytes = id_set.encode('utf-8')

        log.info(f"Removing label '{label_name}' from sequence numbers: {id_set}")
        status, response = await loop.run_in_executor(
            None,
            # Pass label name as a quoted string literal for X-GM-LABELS
            lambda: mail.store(id_set_bytes, '-X-GM-LABELS', f'"{label_name}"')
        )
        log.info(f"Batch remove label response for IDs {id_set}: Status={status}, Response={response}")
        # Removed fallback logic

        return status == 'OK'
    except Exception as e:
        log.error(f"Error batch removing label '{label_name}' from IDs {id_set}: {str(e)}", exc_info=True)
        return False


async def move_emails_batch_async(mail: imaplib.IMAP4_SSL, email_ids: List[str], destination_label: str) -> bool:
    """Move a batch of emails to a specific folder/label using their sequence numbers."""
    if not email_ids:
        return False
    loop = asyncio.get_event_loop()
    try:
        # Format sequence numbers as comma-separated string
        id_set = ",".join(email_ids)
        id_set_bytes = id_set.encode('utf-8')

        # Destination label for COPY needs quoting and potentially encoding (modified UTF-7)
        try:
            encoded_destination = f'"{destination_label}"'.encode('utf-7')
        except UnicodeEncodeError:
            log.warning(f"Could not encode destination '{destination_label}' to UTF-7 for batch move. Using UTF-8.")
            encoded_destination = f'"{destination_label}"'.encode('utf-8')

        # 1. Copy the emails to the destination label using sequence numbers
        log.info(f"Batch copying emails {id_set} to label '{destination_label}' (encoded: {encoded_destination})")
        status_copy, response_copy = await loop.run_in_executor(
            None,
            lambda: mail.copy(id_set_bytes, encoded_destination) # Use copy, not uid('COPY')
        )
        log.info(f"Batch copy response for IDs {id_set}: Status={status_copy}, Response={response_copy}")

        if status_copy != 'OK':
            error_detail = ""
            if response_copy and isinstance(response_copy[0], bytes):
                try: error_detail = response_copy[0].decode('utf-8', errors='ignore')
                except: pass
            log.error(f"Failed to batch copy emails {id_set} to '{destination_label}': Status {status_copy}, Detail: {error_detail}")
            if "TRYCREATE" in error_detail or "NONEXISTENT" in error_detail:
                 log.error(f"Destination label '{destination_label}' might not exist.")
            return False

        # 2. Add the \Deleted flag to the original emails using sequence numbers
        log.info(f"Marking original emails {id_set} as deleted")
        status_delete, response_delete = await loop.run_in_executor(
            None,
            lambda: mail.store(id_set_bytes, '+FLAGS', '\\Deleted') # Use store, not uid('STORE')
        )
        log.info(f"Batch mark deleted response for IDs {id_set}: Status={status_delete}, Response={response_delete}")

        if status_delete != 'OK':
            error_detail = ""
            if response_delete and isinstance(response_delete[0], bytes):
                 try: error_detail = response_delete[0].decode('utf-8', errors='ignore')
                 except: pass
            log.warning(f"Failed to mark emails {id_set} as deleted after copying: Status {status_delete}, Detail: {error_detail}")
            # Proceed even if marking fails, as copy succeeded

        # 3. Expunge (Optional - currently disabled, might be better done separately)
        # log.info(f"Expunging mailbox containing IDs {id_set}")
        # status_expunge, response_expunge = await loop.run_in_executor(None, mail.expunge)
        # log.info(f"Expunge response: Status={status_expunge}, Response={response_expunge}")
        # if status_expunge != 'OK':
        #     log.warning(f"Failed to expunge mailbox after deleting IDs {id_set}")

        return True # Return True if copy succeeded

    except Exception as e:
        log.error(f"Error batch moving emails {id_set} to '{destination_label}': {str(e)}", exc_info=True)
        return False


async def move_email_async(mail: imaplib.IMAP4_SSL, uid: str, destination_label: str) -> bool:
    """Move an email to a specific folder/label using its UID."""
    loop = asyncio.get_event_loop()
    try:
        # Destination label for COPY needs quoting and potentially encoding (modified UTF-7)
        try:
            encoded_destination = f'"{destination_label}"'.encode('utf-7')
        except UnicodeEncodeError:
            log.warning(f"Could not encode destination '{destination_label}' to UTF-7. Using UTF-8.")
            encoded_destination = f'"{destination_label}"'.encode('utf-8')

        uid_bytes = uid.encode('utf-8') # UID must be bytes

        # 1. Copy the email to the destination label
        log.info(f"Copying email UID {uid} to label '{destination_label}' (encoded: {encoded_destination})")
        status_copy, response_copy = await loop.run_in_executor(
            None,
            lambda: mail.uid('COPY', uid_bytes, encoded_destination)
        )
        log.info(f"Copy response for UID {uid}: Status={status_copy}, Response={response_copy}")

        if status_copy != 'OK':
            # Attempt to decode error response if possible
            error_detail = ""
            if response_copy and isinstance(response_copy[0], bytes):
                try:
                    error_detail = response_copy[0].decode('utf-8', errors='ignore')
                except: pass
            log.error(f"Failed to copy email UID {uid} to '{destination_label}': Status {status_copy}, Detail: {error_detail}")
            # Check common errors
            if "TRYCREATE" in error_detail or "NONEXISTENT" in error_detail:
                 log.error(f"Destination label '{destination_label}' might not exist.")
            return False

        # 2. Add the \Deleted flag to the original email
        log.info(f"Marking original email UID {uid} as deleted")
        status_delete, response_delete = await loop.run_in_executor(
            None,
            lambda: mail.uid('STORE', uid_bytes, '+FLAGS', '\\Deleted')
        )
        log.info(f"Mark deleted response for UID {uid}: Status={status_delete}, Response={response_delete}")

        if status_delete != 'OK':
            # Log warning but proceed as copy was successful
            error_detail = ""
            if response_delete and isinstance(response_delete[0], bytes):
                 try:
                     error_detail = response_delete[0].decode('utf-8', errors='ignore')
                 except: pass
            log.warning(f"Failed to mark email UID {uid} as deleted after copying: Status {status_delete}, Detail: {error_detail}")

        # 3. Expunge (Optional - currently disabled)
        # log.info(f"Expunging mailbox containing UID {uid}")
        # status_expunge, response_expunge = await loop.run_in_executor(None, mail.expunge)
        # log.info(f"Expunge response: Status={status_expunge}, Response={response_expunge}")
        # if status_expunge != 'OK':
        #     log.warning(f"Failed to expunge mailbox after deleting UID {uid}")

        return True # Return True if copy succeeded

    except Exception as e:
        log.error(f"Error moving email UID {uid} to '{destination_label}': {str(e)}", exc_info=True)
        return False
