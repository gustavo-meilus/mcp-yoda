from mcp.server.fastmcp import FastMCP

from tools.quote_play import quote_play


def register_all_tools(mcp_server: FastMCP) -> None:
    """
    Register all tools with the MCP server.

    Args:
        mcp_server: The FastMCP server instance to register tools with
    """

    # Add more tools here as you create them
    mcp_server.tool()(quote_play)
