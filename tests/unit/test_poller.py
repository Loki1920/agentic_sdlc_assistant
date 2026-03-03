"""Unit tests for the Jira poller scheduler."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── _fetch_ready_ticket_ids ───────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("scheduler.poller._repo")
@patch("scheduler.poller.get_mcp_client")
async def test_fetch_ticket_ids_happy_path(mock_get_client, mock_repo):
    from scheduler.poller import _fetch_ready_ticket_ids

    # Build mock tool that returns issues
    mock_tool = MagicMock()
    mock_tool.name = "jira_search_issues"
    mock_tool.ainvoke = AsyncMock(return_value={
        "issues": [{"key": "PROJ-1"}, {"key": "PROJ-2"}]
    })

    mock_client = AsyncMock()
    mock_client.get_tools = AsyncMock(return_value=[mock_tool])
    mock_get_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_get_client.return_value.__aexit__ = AsyncMock(return_value=False)

    # Neither ticket has been processed
    mock_repo.is_ticket_processed.return_value = False

    result = await _fetch_ready_ticket_ids()

    assert "PROJ-1" in result
    assert "PROJ-2" in result


@pytest.mark.asyncio
@patch("scheduler.poller._repo")
@patch("scheduler.poller.get_mcp_client")
async def test_fetch_ticket_ids_deduplication(mock_get_client, mock_repo):
    """Tickets already processed should be filtered out."""
    from scheduler.poller import _fetch_ready_ticket_ids

    mock_tool = MagicMock()
    mock_tool.name = "jira_search_issues"
    mock_tool.ainvoke = AsyncMock(return_value={
        "issues": [{"key": "PROJ-1"}, {"key": "PROJ-2"}]
    })

    mock_client = AsyncMock()
    mock_client.get_tools = AsyncMock(return_value=[mock_tool])
    mock_get_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_get_client.return_value.__aexit__ = AsyncMock(return_value=False)

    # PROJ-1 already processed, PROJ-2 is new
    mock_repo.is_ticket_processed.side_effect = lambda tid: tid == "PROJ-1"

    result = await _fetch_ready_ticket_ids()

    assert "PROJ-1" not in result
    assert "PROJ-2" in result


@pytest.mark.asyncio
@patch("scheduler.poller.get_mcp_client")
async def test_fetch_ticket_ids_no_search_tool(mock_get_client):
    """If no search tool is found, return empty list."""
    from scheduler.poller import _fetch_ready_ticket_ids

    # Tool with unrecognised name — not matched by "search" keyword
    mock_tool = MagicMock()
    mock_tool.name = "confluence_page_get"

    mock_client = AsyncMock()
    mock_client.get_tools = AsyncMock(return_value=[mock_tool])
    mock_get_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_get_client.return_value.__aexit__ = AsyncMock(return_value=False)

    result = await _fetch_ready_ticket_ids()

    assert result == []
