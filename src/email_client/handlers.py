import asyncio
import imaplib
import logging
from datetime import datetime, timedelta

import mcp.types as types

# Import from our new modules
from .config import EMAIL_CONFIG, SEARCH_TIMEOUT, DEFAULT_MAX_EMAILS
from .utils import build_date_criteria
from .imap_client import (
    search_emails_async,
    get_email_content_async,
    count_emails_async,
    list_labels_async,
    create_label_async,
    get_email_uid_async,
    apply_label_async,
    remove_label_async,
    move_email_async,
    delete_label_async,
    rename_label_async,
    apply_labels_batch_async,
    remove_labels_batch_async,
    move_emails_batch_async # Import batch move
)
from .smtp_client import send_email_async, forward_email_async
from .tool_definitions import get_tools # Import the function to get tools

log = logging.getLogger(__name__)

# This function replaces the @server.list_tools decorator content
async def handle_list_tools() -> list[types.Tool]:
    """List available tools."""
    return get_tools()

# This function replaces the @server.call_tool decorator content
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle tool execution requests."""
    if not arguments:
        arguments = {}

    log.info(f"Handling tool call: {name} with arguments: {arguments}")

    # --- Non-IMAP/SMTP tools first ---
    if name == "send-email":
        # This tool doesn't need an active IMAP connection initially
        to_addresses = arguments.get("to", [])
        subject = arguments.get("subject", "")
        content = arguments.get("content", "")
        cc_addresses = arguments.get("cc", [])

        if not to_addresses:
            return [types.TextContent(type="text", text="At least one recipient email address is required.")]

        try:
            log.info("Attempting to send email")
            async with asyncio.timeout(SEARCH_TIMEOUT):
                await send_email_async(to_addresses, subject, content, cc_addresses)
            return [types.TextContent(type="text", text="Email sent successfully! Check email_client.log for detailed logs.")]
        except asyncio.TimeoutError:
            log.error("Operation timed out while sending email")
            return [types.TextContent(type="text", text="Operation timed out while sending email.")]
        except Exception as e:
            error_msg = str(e)
            log.error(f"Failed to send email: {error_msg}", exc_info=True)
            return [types.TextContent(
                type="text",
                text=f"Failed to send email: {error_msg}\n\nPlease check:\n1. Email and password are correct in .env\n2. SMTP settings are correct\n3. Less secure app access is enabled (for Gmail)\n4. Using App Password if 2FA is enabled"
            )]

    # --- Tools requiring IMAP connection ---
    mail = None
    try:
        # Connect to IMAP server for tools that need it
        log.debug(f"Connecting to IMAP server {EMAIL_CONFIG['imap_server']} for tool {name}")
        mail = imaplib.IMAP4_SSL(EMAIL_CONFIG["imap_server"])
        mail.login(EMAIL_CONFIG["email"], EMAIL_CONFIG["password"])
        log.info(f"Successfully connected to IMAP server for tool {name}")

        # Select folder - necessary for most IMAP operations
        # Default to inbox, but allow specific tools to override if needed (e.g., search)
        folder_to_select = "inbox"
        if name == "search-emails":
             folder_arg = arguments.get("folder", "inbox")
             folder_to_select = '"[Gmail]/Sent Mail"' if folder_arg == "sent" else "inbox"
        elif name in ["apply-label", "remove-label", "move-email", "get-email-content", "forward-email"]:
             # These might operate on emails in inbox or sent, default to inbox for now
             # Could add a 'folder' argument to these tools if needed
             pass # Keep default "inbox"

        try:
            log.debug(f"Selecting IMAP folder: {folder_to_select}")
            status, _ = mail.select(folder_to_select)
            if status != 'OK':
                 # Try selecting the other common folder if the first fails
                 fallback_folder = '"[Gmail]/Sent Mail"' if folder_to_select == "inbox" else "inbox"
                 log.warning(f"Failed to select '{folder_to_select}', trying '{fallback_folder}'")
                 status, _ = mail.select(fallback_folder)
                 if status != 'OK':
                      raise Exception(f"Failed to select folder '{folder_to_select}' or fallback '{fallback_folder}'")
            log.info(f"Successfully selected IMAP folder: {folder_to_select} (or fallback)")
        except Exception as e:
            log.error(f"Failed during folder selection: {str(e)}", exc_info=True)
            raise # Raise to outer exception handler

        # --- Inner try/except for the specific tool operation ---
        try:
            if name == "search-emails":
                start_date = arguments.get("start_date")
                end_date = arguments.get("end_date")
                keyword = arguments.get("keyword")
                raw_query = arguments.get("raw_query") # Get the new raw_query param
                limit = arguments.get("limit", DEFAULT_MAX_EMAILS)
                # folder_arg is handled during folder selection above

                # Ensure limit is valid
                try:
                    limit = int(limit)
                    if limit <= 0: limit = DEFAULT_MAX_EMAILS
                except (ValueError, TypeError):
                    limit = DEFAULT_MAX_EMAILS

                search_criteria_final = None # Initialize
                raw_query_final = raw_query # Start with user-provided raw_query

                if not raw_query_final: # If user didn't provide a raw query, build criteria based on folder
                    try:
                        if folder_to_select == "inbox":
                            # Build X-GM-RAW query for primary inbox
                            if keyword:
                                # If keyword is present, use it directly in X-GM-RAW (omit category:primary for simplicity)
                                raw_query_final = keyword
                                log.info(f"Using keyword-only X-GM-RAW query for inbox: {raw_query_final}, limit: {limit}")
                            else:
                                # If no keyword, default to category:primary
                                raw_query_final = "category:primary"
                                log.info(f"Using default category X-GM-RAW query for inbox: {raw_query_final}, limit: {limit}")
                            search_criteria_final = None # Ensure standard criteria is None
                        else:
                            # Build standard criteria for other folders (e.g., Sent)
                            criteria_parts = []
                            date_criteria = build_date_criteria(start_date, end_date)
                            if date_criteria:
                                criteria_parts.append(date_criteria)
                            if keyword:
                                keyword_criteria = f'(OR SUBJECT "{keyword}" BODY "{keyword}")'
                                # If we have date criteria, wrap it in parentheses before adding keyword
                                if date_criteria:
                                     criteria_parts[0] = f"({date_criteria})"
                                criteria_parts.append(keyword_criteria)

                            search_criteria_final = " ".join(criteria_parts) if criteria_parts else "ALL"
                            raw_query_final = None # Explicitly set the other to None
                            log.info(f"Using standard search criteria for folder '{folder_to_select}': {search_criteria_final}, limit: {limit}")

                    except ValueError as e: # Catch potential errors from build_date_criteria
                        return [types.TextContent(type="text", text=str(e))]
                else:
                    # User provided raw_query, use it directly
                    log.info(f"Using user-provided raw Gmail search query: {raw_query_final}, limit: {limit}")

                # Ensure only one search method is passed
                if raw_query_final and search_criteria_final:
                     log.warning("Both raw_query and search_criteria were generated, prioritizing raw_query.")
                     search_criteria_final = None

                if not raw_query_final and not search_criteria_final:
                     # Handle case where no criteria could be built (e.g., only folder specified)
                     # Default to searching primary inbox if folder is inbox
                     if folder_to_select == "inbox":
                         raw_query_final = "category:primary"
                         log.info(f"No specific criteria, defaulting to X-GM-RAW query: {raw_query_final}, limit: {limit}")
                     else: # For other folders, search all might be too broad, maybe require criteria?
                          # For now, let's allow searching all in 'Sent' if no criteria given
                          if folder_to_select == '"[Gmail]/Sent Mail"':
                               search_criteria_final = "ALL"
                               log.info(f"No specific criteria for Sent folder, using standard search: {search_criteria_final}, limit: {limit}")
                          else:
                               return [types.TextContent(type="text", text="Search criteria or raw query required.")]


                async with asyncio.timeout(SEARCH_TIMEOUT):
                    email_list = await search_emails_async(
                        mail=mail,
                        limit=limit,
                        search_criteria=search_criteria_final, # Pass final standard criteria (might be None)
                        raw_query=raw_query_final           # Pass final raw query (might be None)
                    )

                if not email_list:
                    search_type = "raw query" if raw_query_final else "criteria"
                    details = raw_query_final if raw_query_final else search_criteria_final
                    return [types.TextContent(type="text", text=f"No emails found matching the {search_type}: {details}")]

                result_text = f"Found {len(email_list)} emails (limit: {limit}):\n\n"
                result_text += "ID | From | Date | Subject\n" + "-" * 80 + "\n"
                for email_item in email_list:
                    result_text += f"{email_item['id']} | {email_item['from']} | {email_item['date']} | {email_item['subject']}\n"
                result_text += "\nUse get-email-content with an email ID to view the full content."
                return [types.TextContent(type="text", text=result_text)]

            elif name == "get-email-content":
                email_id = arguments.get("email_id")
                if not email_id: return [types.TextContent(type="text", text="Email ID is required.")]

                async with asyncio.timeout(SEARCH_TIMEOUT):
                    email_content = await get_email_content_async(mail, email_id)

                result_text = f"From: {email_content['from']}\nTo: {email_content['to']}\n"
                if email_content.get('cc'): result_text += f"CC: {email_content['cc']}\n"
                result_text += f"Date: {email_content['date']}\nSubject: {email_content['subject']}\n"
                if email_content.get('attachments'): result_text += f"\nAttachments: {', '.join(email_content['attachments'])}\n"
                result_text += f"\nContent:\n{email_content['content']}"
                return [types.TextContent(type="text", text=result_text)]

            elif name == "count-daily-emails":
                start_date = arguments.get("start_date")
                end_date = arguments.get("end_date")
                if not start_date or not end_date: return [types.TextContent(type="text", text="Both start_date and end_date required (YYYY-MM-DD).")]

                try:
                    start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
                    end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
                except ValueError:
                    return [types.TextContent(type="text", text="Invalid date format. Use YYYY-MM-DD.")]

                date_diff = (end_date_obj - start_date_obj).days
                if date_diff > 31: return [types.TextContent(type="text", text="Date range too large (max 31 days).")]
                if date_diff < 0: return [types.TextContent(type="text", text="End date must be after start date.")]

                result_text = "Daily email counts:\n\nDate | Count\n" + "-" * 30 + "\n"
                current_date = start_date_obj
                while current_date <= end_date_obj:
                    date_str = current_date.strftime("%d-%b-%Y")
                    search_criteria = f'ON "{date_str}"'
                    try:
                        async with asyncio.timeout(SEARCH_TIMEOUT):
                            count = await count_emails_async(mail, search_criteria)
                        result_text += f"{current_date.strftime('%Y-%m-%d')} | {count}\n"
                    except asyncio.TimeoutError:
                        result_text += f"{current_date.strftime('%Y-%m-%d')} | Timeout\n"
                    current_date += timedelta(days=1)
                return [types.TextContent(type="text", text=result_text)]

            elif name == "forward-email":
                # Note: forward_email_async needs the IMAP connection too
                email_id = arguments.get("email_id")
                to_addresses = arguments.get("to", [])
                subject_prefix = arguments.get("subject_prefix", "Fwd: ")
                additional_message = arguments.get("additional_message", "")
                cc_addresses = arguments.get("cc", [])

                if not email_id: return [types.TextContent(type="text", text="Email ID is required.")]
                if not to_addresses: return [types.TextContent(type="text", text="At least one recipient is required.")]

                async with asyncio.timeout(SEARCH_TIMEOUT * 2): # Allow more time for fetch + send
                    await forward_email_async(mail, email_id, to_addresses, subject_prefix, additional_message, cc_addresses)
                return [types.TextContent(type="text", text="Email forwarded successfully!")]

            elif name == "list-labels":
                async with asyncio.timeout(SEARCH_TIMEOUT):
                    labels = await list_labels_async(mail)
                result = "Available Gmail labels:\n\n"
                for label in labels:
                    label_type = "System" if label["is_system"] else "Custom"
                    result += f"- {label['name']} ({label_type})\n"
                return [types.TextContent(type="text", text=result)]

            elif name == "create-label":
                label_name_arg = arguments.get("label_name")
                if not label_name_arg: return [types.TextContent(type="text", text="Label name is required.")]
                label_name = str(label_name_arg) # Ensure it's a string

                async with asyncio.timeout(SEARCH_TIMEOUT):
                    created = await create_label_async(mail, label_name)
                if created:
                    return [types.TextContent(type="text", text=f"Label '{label_name}' created successfully!")]
                else:
                    # Check if it failed because it exists
                    labels = await list_labels_async(mail) # Re-check labels
                    if any(l['name'] == label_name for l in labels):
                         return [types.TextContent(type="text", text=f"Label '{label_name}' already exists.")]
                    else:
                         return [types.TextContent(type="text", text=f"Failed to create label '{label_name}'. Check logs.")]


            elif name == "apply-label":
                email_id = arguments.get("email_id")
                label_name_arg = arguments.get("label_name")
                if not email_id: return [types.TextContent(type="text", text="Email ID is required.")]
                if not label_name_arg: return [types.TextContent(type="text", text="Label name is required.")]
                label_name = str(label_name_arg) # Ensure it's a string

                uid = await get_email_uid_async(mail, email_id)
                if not uid: return [types.TextContent(type="text", text=f"Failed to find UID for email ID {email_id}.")]

                async with asyncio.timeout(SEARCH_TIMEOUT):
                    applied = await apply_label_async(mail, uid, label_name)
                if applied:
                    return [types.TextContent(type="text", text=f"Label '{label_name}' applied to email {email_id} successfully!")]
                else:
                    # Add check if label exists?
                    labels = await list_labels_async(mail)
                    if not any(l['name'] == label_name for l in labels):
                         return [types.TextContent(type="text", text=f"Failed to apply label. Label '{label_name}' does not exist.")]
                    return [types.TextContent(type="text", text=f"Failed to apply label '{label_name}' to email {email_id}. Check logs.")]

            elif name == "remove-label":
                email_id = arguments.get("email_id")
                label_name_arg = arguments.get("label_name")
                if not email_id: return [types.TextContent(type="text", text="Email ID is required.")]
                if not label_name_arg: return [types.TextContent(type="text", text="Label name is required.")]
                label_name = str(label_name_arg) # Ensure it's a string

                uid = await get_email_uid_async(mail, email_id)
                if not uid: return [types.TextContent(type="text", text=f"Failed to find UID for email ID {email_id}.")]

                async with asyncio.timeout(SEARCH_TIMEOUT):
                    removed = await remove_label_async(mail, uid, label_name)
                if removed:
                    return [types.TextContent(type="text", text=f"Label '{label_name}' removed from email {email_id} successfully!")]
                else:
                    # Add check if label exists?
                    return [types.TextContent(type="text", text=f"Failed to remove label '{label_name}' from email {email_id}. Check logs.")]


            elif name == "move-email":
                email_id = arguments.get("email_id")
                destination_label_arg = arguments.get("destination_label")
                if not email_id: return [types.TextContent(type="text", text="Email ID is required.")]
                if not destination_label_arg: return [types.TextContent(type="text", text="Destination label is required.")]
                destination_label = str(destination_label_arg) # Ensure it's a string

                uid = await get_email_uid_async(mail, email_id)
                if not uid: return [types.TextContent(type="text", text=f"Failed to find UID for email ID {email_id}.")]

                async with asyncio.timeout(SEARCH_TIMEOUT):
                    moved = await move_email_async(mail, uid, destination_label)
                if moved:
                    return [types.TextContent(type="text", text=f"Email {email_id} moved to '{destination_label}' successfully!")]
                else:
                     # Add check if label exists?
                    labels = await list_labels_async(mail)
                    if not any(l['name'] == destination_label for l in labels):
                         return [types.TextContent(type="text", text=f"Failed to move email. Destination label '{destination_label}' does not exist.")]
                    return [types.TextContent(type="text", text=f"Failed to move email {email_id} to '{destination_label}'. Check logs.")]

            elif name == "delete-label":
                label_name_arg = arguments.get("label_name")
                if not label_name_arg: return [types.TextContent(type="text", text="Label name is required.")]
                label_name = str(label_name_arg) # Ensure it's a string

                # Note: Deleting labels doesn't require selecting a specific folder first,
                # but we need the active IMAP connection.

                async with asyncio.timeout(SEARCH_TIMEOUT):
                    deleted = await delete_label_async(mail, label_name)

                if deleted:
                    return [types.TextContent(type="text", text=f"Label '{label_name}' deleted successfully!")]
                else:
                    # Check common reasons for failure
                    if '[Gmail]' in label_name or '[GoogleMail]' in label_name or label_name == 'INBOX':
                         return [types.TextContent(type="text", text=f"Failed to delete label: Cannot delete system label '{label_name}'.")]
                    # Re-check if it exists (might have been deleted by another client)
                    labels = await list_labels_async(mail)
                    if not any(l['name'] == label_name for l in labels):
                          return [types.TextContent(type="text", text=f"Failed to delete label: Label '{label_name}' does not exist (or was already deleted).")]
                    return [types.TextContent(type="text", text=f"Failed to delete label '{label_name}'. Check logs.")]

            elif name == "rename-label":
                old_label_name_arg = arguments.get("old_label_name")
                new_label_name_arg = arguments.get("new_label_name")
                if not old_label_name_arg: return [types.TextContent(type="text", text="Old label name is required.")]
                if not new_label_name_arg: return [types.TextContent(type="text", text="New label name is required.")]
                old_label_name = str(old_label_name_arg) # Ensure string
                new_label_name = str(new_label_name_arg) # Ensure string

                # Note: Renaming labels doesn't require selecting a specific folder first,
                # but we need the active IMAP connection.

                async with asyncio.timeout(SEARCH_TIMEOUT):
                    renamed = await rename_label_async(mail, old_label_name, new_label_name)

                if renamed:
                    return [types.TextContent(type="text", text=f"Label '{old_label_name}' renamed to '{new_label_name}' successfully!")]
                else:
                    # Check common reasons for failure
                    if '[Gmail]' in old_label_name or '[GoogleMail]' in old_label_name or old_label_name == 'INBOX':
                         return [types.TextContent(type="text", text=f"Failed to rename label: Cannot rename system label '{old_label_name}'.")]
                    # Re-check if old exists and new doesn't
                    labels = await list_labels_async(mail)
                    old_exists = any(l['name'] == old_label_name for l in labels)
                    new_exists = any(l['name'] == new_label_name for l in labels)
                    if not old_exists:
                          return [types.TextContent(type="text", text=f"Failed to rename label: Old label '{old_label_name}' does not exist.")]
                    if new_exists:
                         return [types.TextContent(type="text", text=f"Failed to rename label: New label name '{new_label_name}' already exists.")]
                    return [types.TextContent(type="text", text=f"Failed to rename label '{old_label_name}'. Check logs.")]

            elif name == "apply-label-batch":
                email_ids = arguments.get("email_ids", [])
                label_name_arg = arguments.get("label_name")
                if not email_ids: return [types.TextContent(type="text", text="List of email IDs is required.")]
                if not label_name_arg: return [types.TextContent(type="text", text="Label name is required.")]
                label_name = str(label_name_arg) # Ensure string

                # Note: Batch operations use sequence numbers, which are folder-specific.
                # Ensure the correct folder (where the search was performed) is selected.
                # The current folder_to_select logic might need refinement if searches
                # return IDs from different folders, but for now assume IDs are from the selected folder.

                async with asyncio.timeout(SEARCH_TIMEOUT):
                    applied = await apply_labels_batch_async(mail, email_ids, label_name)

                if applied:
                    return [types.TextContent(type="text", text=f"Label '{label_name}' applied to {len(email_ids)} emails successfully!")]
                else:
                    # Add check if label exists?
                    labels = await list_labels_async(mail)
                    if not any(l['name'] == label_name for l in labels):
                         return [types.TextContent(type="text", text=f"Failed to apply label batch: Label '{label_name}' does not exist.")]
                    return [types.TextContent(type="text", text=f"Failed to apply label '{label_name}' to batch. Check logs.")]

            elif name == "remove-label-batch":
                email_ids = arguments.get("email_ids", [])
                label_name_arg = arguments.get("label_name")
                if not email_ids: return [types.TextContent(type="text", text="List of email IDs is required.")]
                if not label_name_arg: return [types.TextContent(type="text", text="Label name is required.")]
                label_name = str(label_name_arg) # Ensure string

                async with asyncio.timeout(SEARCH_TIMEOUT):
                    removed = await remove_labels_batch_async(mail, email_ids, label_name)

                if removed:
                    return [types.TextContent(type="text", text=f"Label '{label_name}' removed from {len(email_ids)} emails successfully!")]
                else:
                    # Basic error check
                    return [types.TextContent(type="text", text=f"Failed to remove label '{label_name}' from batch. Check logs.")]

            elif name == "move-email-batch":
                email_ids = arguments.get("email_ids", [])
                destination_label_arg = arguments.get("destination_label")
                if not email_ids: return [types.TextContent(type="text", text="List of email IDs is required.")]
                if not destination_label_arg: return [types.TextContent(type="text", text="Destination label is required.")]
                destination_label = str(destination_label_arg) # Ensure string

                # Similar note as batch label: assumes IDs are from the currently selected folder.

                async with asyncio.timeout(SEARCH_TIMEOUT): # May need longer timeout for many emails
                    moved = await move_emails_batch_async(mail, email_ids, destination_label)

                if moved:
                    return [types.TextContent(type="text", text=f"{len(email_ids)} emails moved to '{destination_label}' successfully!")]
                else:
                    # Add check if label exists?
                    labels = await list_labels_async(mail)
                    if not any(l['name'] == destination_label for l in labels):
                         return [types.TextContent(type="text", text=f"Failed to move email batch: Destination label '{destination_label}' does not exist.")]
                    return [types.TextContent(type="text", text=f"Failed to move emails to '{destination_label}'. Check logs.")]


            else:
                raise ValueError(f"Unknown tool: {name}")

        # --- Inner Exception Handling ---
        except asyncio.TimeoutError:
            log.error(f"Operation timed out during tool call: {name}")
            return [types.TextContent(type="text", text=f"Operation timed out while executing {name}.")]
        except Exception as e:
            error_msg = str(e)
            log.error(f"Error during {name} operation: {error_msg}", exc_info=True)
            return [types.TextContent(type="text", text=f"Error executing {name}: {error_msg}")]

    # --- Outer Exception Handling (Connection/Setup) ---
    except Exception as e:
        error_msg = str(e)
        log.error(f"Error during {name} connection/setup: {error_msg}", exc_info=True)
        if "authentication failed" in error_msg.lower():
             return [types.TextContent(type="text", text="Failed to connect to IMAP server: Authentication failed. Please check email/password.")]
        return [types.TextContent(type="text", text=f"Failed to execute {name}: {error_msg}")]

    # --- Outer Finally (Connection Closing) ---
    finally:
        if mail:
            try:
                log.debug(f"Closing IMAP connection for tool {name}")
                if mail.state == 'SELECTED':
                    mail.close()
                mail.logout()
                log.info(f"Successfully closed IMAP connection for tool {name}")
            except Exception as close_err:
                 log.error(f"Error closing IMAP connection after tool {name}: {close_err}", exc_info=True)
