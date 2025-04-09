import email
from datetime import datetime, timedelta
from typing import Optional

def format_email_summary(msg_data: tuple) -> dict:
    """Format an email message into a summary dict with basic information."""
    # Ensure msg_data is not empty and has the expected structure
    if not msg_data or not msg_data[0] or len(msg_data[0]) < 2:
        return {
            "id": "N/A",
            "from": "Unknown",
            "date": "Unknown",
            "subject": "Error: Invalid message data",
        }

    try:
        email_body = email.message_from_bytes(msg_data[0][1])
        email_id_bytes = msg_data[0][0].split()[0]
        email_id = email_id_bytes.decode()
    except (IndexError, AttributeError, UnicodeDecodeError) as e:
         return {
            "id": "N/A",
            "from": "Unknown",
            "date": "Unknown",
            "subject": f"Error parsing basic info: {e}",
        }


    # Parse the date to a consistent format if possible
    date_str = email_body.get("Date", "Unknown")
    try:
        # Try to parse various date formats
        for date_format in [
            "%a, %d %b %Y %H:%M:%S %z",
            "%a, %d %b %Y %H:%M:%S %Z",
            "%d %b %Y %H:%M:%S %z",
            "%a, %d %b %Y %H:%M:%S",
            "%d %b %Y %H:%M:%S"
        ]:
            try:
                # Handle timezone offsets like +0000 (UTC) or -0700
                if date_str.endswith(' (UTC)') or date_str.endswith(' (GMT)'):
                    date_str = date_str[:-6].strip() # Remove timezone name for strptime

                # Remove potential extra timezone info if strptime fails with %z
                if '%z' in date_format:
                    try:
                        parsed_date = datetime.strptime(date_str, date_format)
                    except ValueError:
                         # Try removing timezone if parsing with %z failed
                         date_parts = date_str.split()
                         if len(date_parts) > 5 and (date_parts[-1].startswith('+') or date_parts[-1].startswith('-')):
                              date_str_no_tz = " ".join(date_parts[:-1])
                              # Try parsing again without timezone
                              date_format_no_tz = date_format.replace(" %z", "")
                              parsed_date = datetime.strptime(date_str_no_tz, date_format_no_tz)
                         else:
                              raise # Re-raise if not a timezone issue
                else:
                     parsed_date = datetime.strptime(date_str, date_format)

                date_str = parsed_date.strftime("%Y-%m-%d %H:%M:%S")
                break
            except ValueError:
                continue
        else: # If loop completes without break
             # Keep original if all formats fail
             pass
    except Exception:
        # Keep original if any other parsing error occurs
        pass

    return {
        "id": email_id,
        "from": email_body.get("From", "Unknown"),
        "date": date_str,
        "subject": email_body.get("Subject", "No Subject"),
    }

def format_email_content(msg_data: tuple) -> dict:
    """Format an email message into a dict with full content."""
     # Ensure msg_data is not empty and has the expected structure
    if not msg_data or not msg_data[0] or len(msg_data[0]) < 2:
        return {
            "id": "N/A",
            "from": "Unknown",
            "to": "Unknown",
            "cc": "",
            "date": "Unknown",
            "subject": "Error: Invalid message data",
            "content": "",
            "attachments": []
        }
    try:
        email_body = email.message_from_bytes(msg_data[0][1])
        email_id_bytes = msg_data[0][0].split()[0]
        email_id = email_id_bytes.decode()
    except (IndexError, AttributeError, UnicodeDecodeError) as e:
         return {
            "id": "N/A",
            "from": "Unknown",
            "to": "Unknown",
            "cc": "",
            "date": "Unknown",
            "subject": f"Error parsing basic info: {e}",
            "content": "",
            "attachments": []
        }

    # Extract body content
    body = ""
    attachments = []

    if email_body.is_multipart():
        # Handle multipart messages
        for part in email_body.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))

            # Extract attachments info
            if "attachment" in content_disposition:
                filename = part.get_filename()
                if filename:
                    attachments.append(filename)
                continue # Skip attachment parts for body content

            # Get payload, preferring plain text
            if part.get_content_charset() is not None:
                charset = part.get_content_charset()
            else:
                # Guess charset if not specified
                charset = 'utf-8' # Default guess

            if content_type == "text/plain" and "attachment" not in content_disposition:
                try:
                    payload = part.get_payload(decode=True)
                    body = payload.decode(charset, errors='replace')
                    # If we found plain text, prioritize it and stop searching
                    break
                except (LookupError, UnicodeDecodeError):
                     body = "Could not decode plain text part"

            elif content_type == "text/html" and "attachment" not in content_disposition:
                 # If no plain text found yet, store HTML as fallback
                 if not body:
                    try:
                        payload = part.get_payload(decode=True)
                        body = payload.decode(charset, errors='replace') # Store HTML
                    except (LookupError, UnicodeDecodeError):
                         body = "Could not decode HTML part"

    else:
        # Handle non-multipart messages
        charset = email_body.get_content_charset() or 'utf-8'
        try:
            payload = email_body.get_payload(decode=True)
            body = payload.decode(charset, errors='replace')
        except (LookupError, UnicodeDecodeError):
            body = "Could not decode email content"

    return {
        "id": email_id,
        "from": email_body.get("From", "Unknown"),
        "to": email_body.get("To", "Unknown"),
        "cc": email_body.get("Cc", ""),
        "date": email_body.get("Date", "Unknown"),
        "subject": email_body.get("Subject", "No Subject"),
        "content": body,
        "attachments": attachments
    }


def build_date_criteria(start_date: Optional[str], end_date: Optional[str]) -> str:
    """Build IMAP search criteria for date range."""

    # Handle start date
    if start_date:
        try:
            start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
            start_date_str = start_date_obj.strftime("%d-%b-%Y")
        except ValueError:
            raise ValueError("Invalid start_date format. Use YYYY-MM-DD.")
    else:
        # Default to 7 days ago if not provided
        start_date_obj = datetime.now() - timedelta(days=7)
        start_date_str = start_date_obj.strftime("%d-%b-%Y")

    # Handle end date
    if end_date:
        try:
            end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
            # Add one day to include the end date in the search
            next_day_obj = end_date_obj + timedelta(days=1)
            end_date_str = next_day_obj.strftime("%d-%b-%Y")
        except ValueError:
            raise ValueError("Invalid end_date format. Use YYYY-MM-DD.")
    else:
        # Default to tomorrow if not provided (to include today)
        next_day_obj = datetime.now() + timedelta(days=1)
        end_date_str = next_day_obj.strftime("%d-%b-%Y")

    # Build criteria
    return f'SINCE "{start_date_str}" BEFORE "{end_date_str}"'
