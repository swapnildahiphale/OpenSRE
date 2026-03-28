"""
Tool Metadata API

Provides metadata about tools including their integration dependencies.
This helps users understand which tools require which integrations.

This endpoint now uses the unified tools catalog from tools_catalog.py
as the single source of truth for all tool metadata.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from src.core.tools_catalog import (
    BUILT_IN_TOOLS_METADATA,
    get_built_in_tools,
    get_tools_by_integration,
)


class ToolMetadataResponse(BaseModel):
    """Tool metadata including integration dependencies."""

    id: str
    name: str
    description: str
    category: str
    required_integrations: List[str]  # List of integration IDs this tool requires
    optional_integrations: List[str] = (
        []
    )  # Optional integrations that enhance functionality (future use)


class ToolMetadataListResponse(BaseModel):
    """List of tool metadata."""

    tools: List[ToolMetadataResponse]
    total: int


router = APIRouter(prefix="/api/v1/tools", tags=["tools"])


@router.get("/metadata", response_model=ToolMetadataListResponse)
async def list_tool_metadata(
    category: Optional[str] = Query(None, description="Filter by category"),
    integration_id: Optional[str] = Query(
        None, description="Filter by required integration"
    ),
):
    """
    Get metadata about available tools including their integration dependencies.

    This endpoint helps users understand:
    1. Which tools require which integrations
    2. What functionality becomes available when an integration is configured
    3. How tools and integrations work together

    Data source: Unified tools catalog (tools_catalog.py) - single source of truth
    """
    # Get tools from unified catalog
    if integration_id:
        # Filter by integration requirement
        tools = get_tools_by_integration(integration_id)
    else:
        # Get all tools
        tools = get_built_in_tools()

    # Apply category filter if specified
    if category:
        tools = [t for t in tools if t.get("category") == category]

    return ToolMetadataListResponse(
        tools=[ToolMetadataResponse(**t) for t in tools], total=len(tools)
    )


@router.get("/metadata/{tool_id}", response_model=ToolMetadataResponse)
async def get_tool_metadata(tool_id: str):
    """
    Get metadata for a specific tool.

    Returns tool details including which integrations it requires.
    """
    tool = next((t for t in BUILT_IN_TOOLS_METADATA if t["id"] == tool_id), None)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    return ToolMetadataResponse(**{**tool, "source": "built-in"})


@router.get("/by-integration/{integration_id}", response_model=ToolMetadataListResponse)
async def get_tools_by_integration_endpoint(integration_id: str):
    """
    Get all tools that require a specific integration.

    This is useful for showing users "what they get" when they configure an integration.

    Example: GET /api/v1/tools/by-integration/grafana
    Returns: All tools that need Grafana integration
    """
    tools = get_tools_by_integration(integration_id)

    return ToolMetadataListResponse(
        tools=[ToolMetadataResponse(**t) for t in tools], total=len(tools)
    )
