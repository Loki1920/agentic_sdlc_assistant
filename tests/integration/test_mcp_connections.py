"""
Integration test: verify that both MCP servers can start and list tools.

Requires:
- Valid .env with JIRA_URL, JIRA_USERNAME, JIRA_API_TOKEN, GITHUB_PERSONAL_ACCESS_TOKEN
- Node.js + npx available
- uv + uvx available

Run with: pytest tests/integration/test_mcp_connections.py -v
"""

from __future__ import annotations

import os

import pytest

# Skip entire module if credentials are not set
pytestmark = pytest.mark.skipif(
    not os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN") or not os.getenv("JIRA_API_TOKEN"),
    reason="MCP credentials not set in environment",
)


@pytest.mark.asyncio
async def test_github_mcp_tools_available():
    from mcp_client.client_factory import get_mcp_client, filter_github_tools

    async with get_mcp_client() as client:
        all_tools = await client.get_tools()
        github_tools = filter_github_tools(all_tools)

    assert len(github_tools) > 0, "Expected at least 1 GitHub tool from MCP server"
    tool_names = [t.name for t in github_tools]
    # At minimum we need contents and PR creation
    assert any("content" in n.lower() or "file" in n.lower() for n in tool_names), \
        f"No file/content tool found. Available: {tool_names}"


@pytest.mark.asyncio
async def test_jira_mcp_tools_available():
    from mcp_client.client_factory import get_mcp_client, filter_jira_tools

    async with get_mcp_client() as client:
        all_tools = await client.get_tools()
        jira_tools = filter_jira_tools(all_tools)

    assert len(jira_tools) > 0, "Expected at least 1 Jira tool from MCP server"
    tool_names = [t.name for t in jira_tools]
    assert any("search" in n.lower() or "issue" in n.lower() for n in tool_names), \
        f"No search/issue tool found. Available: {tool_names}"


@pytest.mark.asyncio
async def test_both_servers_start_simultaneously():
    from mcp_client.client_factory import get_mcp_client

    async with get_mcp_client() as client:
        all_tools = await client.get_tools()

    assert len(all_tools) > 0, "No tools returned from any MCP server"
