import asyncio
import logging
import os

# Import ServerCapabilities from mcp.types
from mcp.server import Server, NotificationOptions # Keep these
from mcp.server.models import InitializationOptions # Keep this
import mcp.types as types # Import the types module
from mcp.types import ServerCapabilities # Import ServerCapabilities specifically
import mcp.server.stdio

# Import handlers and tool definitions from new modules
import sys
import os

# Add the parent directory to sys.path to allow absolute imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Use absolute imports
from src.email_client.handlers import handle_list_tools, handle_call_tool
from src.email_client.tool_definitions import get_tools # Although handle_list_tools uses this, server needs it for capabilities

# Configure logging (central configuration)
log_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'email_client.log')
logging.basicConfig(
    level=logging.INFO, # Set desired log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename=log_file_path,
    filemode='a' # Append to the log file
)
# Optional: Add a handler to also print logs to console
# console_handler = logging.StreamHandler()
# console_handler.setLevel(logging.DEBUG) # Set level for console output
# console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# console_handler.setFormatter(console_formatter)
# logging.getLogger('').addHandler(console_handler) # Add handler to root logger

log = logging.getLogger(__name__)

# Initialize the MCP Server instance
# The name "email" should match the server_name used in MCP client configuration
server = Server("email")

# Register the handlers using decorators on the server instance
# (Alternatively, could pass them during server.run if preferred)
server.list_tools()(handle_list_tools)
server.call_tool()(handle_call_tool)

async def main():
    """Main function to run the MCP server."""
    log.info("Starting email client MCP server...")
    # Run the server using stdin/stdout streams
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        log.debug("stdio_server context entered.")
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="email", # Consistent server name
                server_version="0.2.0", # Updated version after refactor
                # Construct capabilities using types.ServerCapabilities
                capabilities=ServerCapabilities(
                    # Define capabilities based on available handlers/tools
                    # Assuming only tools are implemented for now:
                    tools=types.ToolsCapability(listChanged=False), # Use ToolsCapability from types
                    # Set others to None or appropriate Capability object if implemented
                    prompts=None,
                    resources=None,
                    logging=None,
                    experimental={},
                ),
            ),
        )
    log.info("Email client MCP server stopped.")

if __name__ == "__main__":
    # Ensure the event loop policy is set correctly for Windows if needed
    # if os.name == 'nt':
    #     asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Server stopped by user (KeyboardInterrupt).")
    except Exception as e:
        log.critical(f"Server encountered critical error: {e}", exc_info=True)
