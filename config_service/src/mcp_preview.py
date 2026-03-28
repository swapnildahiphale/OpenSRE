"""
Standalone MCP Preview - no agent dependencies
"""

import asyncio
from contextlib import asynccontextmanager
from typing import Any, Dict, List

import structlog
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = structlog.get_logger()


@asynccontextmanager
async def get_mcp_client(command: str, args: List[str], env: Dict[str, str]):
    """
    Connect to an MCP server via stdio and return a client session.
    """
    server_params = StdioServerParameters(command=command, args=args, env=env or None)

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


async def preview_mcp_server(
    command: str, args: List[str], env_vars: Dict[str, str], timeout: int = 10
) -> Dict[str, Any]:
    """
    Preview an MCP server by connecting temporarily and discovering tools.

    Returns:
        dict with keys: success, tools, error, error_details
    """
    try:
        async with asyncio.timeout(timeout):
            async with get_mcp_client(command, args, env_vars) as session:
                # List available tools
                tools_result = await session.list_tools()

                tools = []
                for tool in tools_result.tools:
                    tools.append(
                        {
                            "name": tool.name,
                            "display_name": tool.name,  # Can add prefix later if needed
                            "description": tool.description or "",
                            "input_schema": (
                                tool.inputSchema
                                if hasattr(tool, "inputSchema")
                                else None
                            ),
                        }
                    )

                logger.info(
                    "mcp_preview_success", command=command, tool_count=len(tools)
                )

                return {"success": True, "tools": tools, "tool_count": len(tools)}

    except asyncio.TimeoutError:
        logger.error("mcp_preview_timeout", command=command, timeout=timeout)
        return {
            "success": False,
            "error": "Connection timeout",
            "error_details": f"MCP server did not respond within {timeout} seconds. Check if the command is correct and the server starts quickly.",
        }
    except FileNotFoundError as e:
        logger.error("mcp_preview_command_not_found", command=command, error=str(e))
        return {
            "success": False,
            "error": "Command not found",
            "error_details": f"The command '{command}' was not found. Make sure it's installed and in PATH.",
        }
    except Exception as e:
        logger.error(
            "mcp_preview_failed",
            command=command,
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )
        return {
            "success": False,
            "error": str(e),
            "error_details": f"Failed to connect: {type(e).__name__}: {str(e)}",
        }
