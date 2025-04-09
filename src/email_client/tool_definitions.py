import mcp.types as types
from .config import DEFAULT_MAX_EMAILS # Import constant if needed

# Define the list of tools provided by the server
TOOLS_LIST = [
    types.Tool(
        name="search-emails",
        description="Search emails within a date range and/or with specific keywords",
        inputSchema={
            "type": "object",
            "properties": {
                "start_date": {
                    "type": "string",
                    "description": "Start date in YYYY-MM-DD format (optional)",
                },
                "end_date": {
                    "type": "string",
                    "description": "End date in YYYY-MM-DD format (optional)",
                },
                "keyword": {
                    "type": "string",
                    "description": "Keyword to search in email subject and body (optional). Ignored if raw_query is provided.",
                },
                "raw_query": {
                    "type": "string",
                    "description": "Gmail advanced search query string (e.g., 'has:attachment from:boss'). If provided, other search parameters (dates, keyword) are ignored.",
                },
                "folder": {
                    "type": "string",
                    "description": "Folder to search in ('inbox' or 'sent', defaults to 'inbox')",
                    "enum": ["inbox", "sent"],
                    "default": "inbox", # Explicitly set default
                },
                "limit": {
                    "type": "integer",
                    "description": f"Maximum number of emails to return (default: {DEFAULT_MAX_EMAILS})",
                    "default": DEFAULT_MAX_EMAILS, # Explicitly set default
                },
            },
        },
    ),
    types.Tool(
        name="get-email-content",
        description="Get the full content of a specific email by its ID",
        inputSchema={
            "type": "object",
            "properties": {
                "email_id": {
                    "type": "string",
                    "description": "The ID of the email to retrieve",
                },
            },
            "required": ["email_id"],
        },
    ),
    types.Tool(
        name="count-daily-emails",
        description="Count emails received for each day in a date range",
        inputSchema={
            "type": "object",
            "properties": {
                "start_date": {
                    "type": "string",
                    "description": "Start date in YYYY-MM-DD format",
                },
                "end_date": {
                    "type": "string",
                    "description": "End date in YYYY-MM-DD format",
                },
            },
            "required": ["start_date", "end_date"],
        },
    ),
    types.Tool(
        name="forward-email",
        description="Forward an email with its attachments to new recipients. Required fields: email_id and recipients (to). Optional: subject_prefix, additional_message, and CC recipients.",
        inputSchema={
            "type": "object",
            "properties": {
                "email_id": {
                    "type": "string",
                    "description": "The ID of the email to forward",
                },
                "to": {
                    "type": "array",
                    "items": {"type": "string", "format": "email"}, # Added format validation
                    "description": "List of recipient email addresses",
                    "minItems": 1, # Must have at least one recipient
                },
                "subject_prefix": {
                    "type": "string",
                    "description": "Prefix to add to the original subject (default: 'Fwd: ')",
                    "default": "Fwd: ",
                },
                "additional_message": {
                    "type": "string",
                    "description": "Optional message to add before the forwarded content",
                    "default": "",
                },
                "cc": {
                    "type": "array",
                    "items": {"type": "string", "format": "email"}, # Added format validation
                    "description": "List of CC recipient email addresses (optional)",
                    "default": [],
                },
            },
            "required": ["email_id", "to"],
        },
    ),
    types.Tool(
        name="send-email",
        description="CONFIRMATION STEP: Actually send the email after user confirms the details. Before calling this, first show the email details to the user for confirmation. Required fields: recipients (to), subject, and content. Optional: CC recipients.",
        inputSchema={
            "type": "object",
            "properties": {
                "to": {
                    "type": "array",
                    "items": {"type": "string", "format": "email"}, # Added format validation
                    "description": "List of recipient email addresses (confirmed)",
                     "minItems": 1,
                },
                "subject": {
                    "type": "string",
                    "description": "Confirmed email subject",
                },
                "content": {
                    "type": "string",
                    "description": "Confirmed email content",
                },
                "cc": {
                    "type": "array",
                    "items": {"type": "string", "format": "email"}, # Added format validation
                    "description": "List of CC recipient email addresses (optional, confirmed)",
                    "default": [],
                },
            },
            "required": ["to", "subject", "content"],
        },
    ),
    types.Tool(
        name="list-labels",
        description="List all available Gmail labels/folders",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    types.Tool(
        name="create-label",
        description="Create a new Gmail label/folder",
        inputSchema={
            "type": "object",
            "properties": {
                "label_name": {
                    "type": "string",
                    "description": "Name of the label to create",
                },
            },
            "required": ["label_name"],
        },
    ),
    types.Tool(
        name="apply-label",
        description="Apply a label to an email",
        inputSchema={
            "type": "object",
            "properties": {
                "email_id": {
                    "type": "string",
                    "description": "The ID of the email to label",
                },
                "label_name": {
                    "type": "string",
                    "description": "Name of the label to apply",
                },
            },
            "required": ["email_id", "label_name"],
        },
    ),
    types.Tool(
        name="remove-label",
        description="Remove a label from an email",
        inputSchema={
            "type": "object",
            "properties": {
                "email_id": {
                    "type": "string",
                    "description": "The ID of the email to remove the label from",
                },
                "label_name": {
                    "type": "string",
                    "description": "Name of the label to remove",
                },
            },
            "required": ["email_id", "label_name"],
        },
    ),
    types.Tool(
        name="move-email",
        description="Move an email to a specific folder/label",
        inputSchema={
            "type": "object",
            "properties": {
                "email_id": {
                    "type": "string",
                    "description": "The ID of the email to move",
                },
                "destination_label": {
                    "type": "string",
                    "description": "Name of the destination folder/label",
                },
            },
            "required": ["email_id", "destination_label"],
        },
    ),
    types.Tool(
        name="delete-label",
        description="Delete a Gmail label/folder entirely. Cannot delete system labels.",
        inputSchema={
            "type": "object",
            "properties": {
                "label_name": {
                    "type": "string",
                    "description": "Name of the label/folder to delete",
                },
            },
            "required": ["label_name"],
        },
    ),
    types.Tool(
        name="rename-label",
        description="Rename an existing Gmail label/folder. Cannot rename system labels.",
        inputSchema={
            "type": "object",
            "properties": {
                "old_label_name": {
                    "type": "string",
                    "description": "Current name of the label/folder to rename",
                },
                "new_label_name": {
                    "type": "string",
                    "description": "New name for the label/folder",
                },
            },
            "required": ["old_label_name", "new_label_name"],
        },
    ),
    types.Tool(
        name="apply-label-batch",
        description="Apply a label to multiple emails using their sequence IDs (from search results)",
        inputSchema={
            "type": "object",
            "properties": {
                "email_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of email sequence IDs to label",
                    "minItems": 1,
                },
                "label_name": {
                    "type": "string",
                    "description": "Name of the label to apply",
                },
            },
            "required": ["email_ids", "label_name"],
        },
    ),
    types.Tool(
        name="remove-label-batch",
        description="Remove a label from multiple emails using their sequence IDs (from search results)",
        inputSchema={
            "type": "object",
            "properties": {
                "email_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of email sequence IDs to remove the label from",
                    "minItems": 1,
                },
                "label_name": {
                    "type": "string",
                    "description": "Name of the label to remove",
                },
            },
            "required": ["email_ids", "label_name"],
        },
    ),
    types.Tool(
        name="move-email-batch",
        description="Move multiple emails to a specific folder/label using their sequence IDs (from search results)",
        inputSchema={
            "type": "object",
            "properties": {
                "email_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of email sequence IDs to move",
                    "minItems": 1,
                },
                "destination_label": {
                    "type": "string",
                    "description": "Name of the destination folder/label",
                },
            },
            "required": ["email_ids", "destination_label"],
        },
    ),
]

# Function to easily get the tools list
def get_tools() -> list[types.Tool]:
    return TOOLS_LIST
