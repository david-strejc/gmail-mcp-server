# Gmail MCP Server

This project implements a Model Context Protocol (MCP) server that allows interaction with Gmail accounts via IMAP and SMTP. It provides tools for searching emails, retrieving content, managing labels (creating, deleting, renaming, applying, removing), and sending/forwarding emails.

## Features

*   **Email Search:** Search emails by date range, keyword, or raw Gmail query string. Supports searching specific folders (inbox, sent) and limiting results. Uses Gmail's `X-GM-RAW` extension for efficient inbox searching (e.g., filtering by `category:primary`).
*   **Email Content Retrieval:** Fetch the full content (headers, body, attachments) of a specific email using its sequence ID.
*   **Label Management (CRUD):**
    *   List all available Gmail labels (folders).
    *   Create new custom labels.
    *   Rename existing custom labels.
    *   Delete existing custom labels (cannot delete system labels).
    *   Apply labels to individual emails.
    *   Remove labels from individual emails.
*   **Batch Operations:**
    *   Apply labels to multiple emails simultaneously using sequence IDs.
    *   Remove labels from multiple emails simultaneously.
    *   Move multiple emails to a specific label/folder.
*   **Email Sending:** Send new emails (requires SMTP configuration).
*   **Email Forwarding:** Forward existing emails, including attachments (requires SMTP configuration).
*   **Daily Email Count:** Count emails received per day within a specified date range.

## Project Structure

```
.
├── .gitignore         # Specifies intentionally untracked files that Git should ignore
├── .python-version    # Specifies Python version (used by pyenv)
├── LICENSE            # Project license file
├── pyproject.toml     # Python project configuration (dependencies, build system)
├── README.md          # This file
├── task_list.md       # Tracks development progress
├── uv.lock            # Lock file for uv package manager
├── src/
│   └── email_client/
│       ├── __init__.py
│       ├── config.py        # Handles loading configuration from environment variables (.env)
│       ├── handlers.py      # Implements the logic for handling MCP tool calls
│       ├── imap_client.py   # Contains functions for interacting with IMAP server
│       ├── server.py        # Main MCP server script using @modelcontextprotocol/sdk
│       ├── smtp_client.py   # Contains functions for interacting with SMTP server
│       ├── tool_definitions.py # Defines the available MCP tools and their schemas
│       └── utils.py         # Utility functions (e.g., email parsing, date formatting)
└── ... (other potential files like test scripts, helper scripts)
```

## Setup

1.  **Clone the repository (if applicable):**
    ```bash
    git clone https://github.com/david-strejc/gmail-mcp-server.git
    cd gmail-mcp-server
    ```

2.  **Install Dependencies:** This project uses `uv` for package management.
    ```bash
    # Ensure uv is installed (e.g., pip install uv)
    uv venv  # Create virtual environment (.venv)
    uv sync  # Install dependencies from pyproject.toml and uv.lock
    source .venv/bin/activate # Activate the virtual environment
    ```
    *(Alternatively, if not using `uv`, create a virtual environment and install using `pip install -r requirements.txt` if a `requirements.txt` is generated).*

3.  **Configure Environment Variables:** Create a `.env` file in the project root directory and add your Gmail credentials and server settings:
    ```dotenv
    # .env file
    GMAIL_EMAIL=your_email@gmail.com
    GMAIL_PASSWORD=your_app_password # Use an App Password if 2FA is enabled
    GMAIL_IMAP_SERVER=imap.gmail.com
    GMAIL_SMTP_SERVER=smtp.gmail.com
    GMAIL_SMTP_PORT=587 # Or 465 for SSL
    ```
    *   **Important:** For Gmail, if you have 2-Factor Authentication enabled, you **must** generate and use an "App Password". Standard passwords will not work. See [Google's documentation on App Passwords](https://support.google.com/accounts/answer/185833).
    *   Ensure "Less secure app access" is enabled if you are *not* using 2FA (this is generally discouraged).

## Running the MCP Server

Activate the virtual environment and run the server script:

```bash
source .venv/bin/activate
python src/email_client/server.py
```

The server will start and listen for MCP requests via standard input/output.

## Integrating with an MCP Client (e.g., Cline)

Add the server configuration to your MCP client's settings file (e.g., `cline_mcp_settings.json` or `claude_desktop_config.json`).

**Example `cline_mcp_settings.json` entry:**

```json
{
  "mcpServers": {
    "gmail": {
      "command": "/path/to/your/project/gmail-mcp-server/.venv/bin/python",
      "args": ["/path/to/your/project/gmail-mcp-server/src/email_client/server.py"],
      "env": {}, // Environment variables are loaded from .env by the script
      "enabled": true, // Set to true to enable
      "autoApprove": [] // Configure auto-approval if desired
    }
    // ... other servers
  }
}
```

*   Replace `/path/to/your/project/gmail-mcp-server` with the actual absolute path to this project directory.
*   Ensure the `command` points to the python executable within the project's virtual environment (`.venv/bin/python`).

Once configured and enabled, the client should connect to the server, and the defined tools will become available.

## Available Tools (Summary)

*   `search-emails`: Search emails.
*   `get-email-content`: Get full email details.
*   `count-daily-emails`: Count emails per day.
*   `list-labels`: List all labels/folders.
*   `create-label`: Create a new label.
*   `rename-label`: Rename an existing label.
*   `delete-label`: Delete a label.
*   `apply-label`: Apply a label to one email.
*   `remove-label`: Remove a label from one email.
*   `apply-label-batch`: Apply a label to multiple emails.
*   `remove-label-batch`: Remove a label from multiple emails.
*   `move-email`: Move a single email to a label.
*   `move-email-batch`: Move multiple emails to a label.
*   `send-email`: Send a new email.
*   `forward-email`: Forward an existing email.

Refer to `src/email_client/tool_definitions.py` for detailed input schemas for each tool.
