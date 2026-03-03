"""Unit tests for the PR reconciler scheduler."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from persistence.models import PROutcome


# ── _check_pr_state ───────────────────────────────────────────────────────────

def _make_pr_tool(response: dict) -> MagicMock:
    tool = MagicMock()
    tool.name = "get_pull_request"
    tool.ainvoke = AsyncMock(return_value=response)
    return tool


@pytest.mark.asyncio
async def test_check_pr_state_merged():
    from scheduler.pr_reconciler import _check_pr_state

    tool = _make_pr_tool({"state": "closed", "merged": True})
    result = await _check_pr_state([tool], "org", "repo", 42)
    assert result == PROutcome.MERGED


@pytest.mark.asyncio
async def test_check_pr_state_closed_not_merged():
    from scheduler.pr_reconciler import _check_pr_state

    tool = _make_pr_tool({"state": "closed", "merged": False})
    result = await _check_pr_state([tool], "org", "repo", 42)
    assert result == PROutcome.REJECTED


@pytest.mark.asyncio
async def test_check_pr_state_approved():
    from scheduler.pr_reconciler import _check_pr_state

    tool = _make_pr_tool({
        "state": "open",
        "merged": False,
        "reviews": [{"state": "APPROVED"}],
    })
    result = await _check_pr_state([tool], "org", "repo", 42)
    assert result == PROutcome.APPROVED


@pytest.mark.asyncio
async def test_check_pr_state_still_pending():
    from scheduler.pr_reconciler import _check_pr_state

    tool = _make_pr_tool({"state": "open", "merged": False, "reviews": []})
    result = await _check_pr_state([tool], "org", "repo", 42)
    assert result == PROutcome.PENDING


@pytest.mark.asyncio
async def test_check_pr_state_exception_returns_pending():
    from scheduler.pr_reconciler import _check_pr_state

    tool = MagicMock()
    tool.name = "get_pull_request"
    tool.ainvoke = AsyncMock(side_effect=ConnectionError("GitHub unavailable"))

    result = await _check_pr_state([tool], "org", "repo", 42)
    assert result == PROutcome.PENDING


@pytest.mark.asyncio
async def test_check_pr_state_no_tool():
    from scheduler.pr_reconciler import _check_pr_state

    # No tools at all — should return PENDING
    result = await _check_pr_state([], "org", "repo", 42)
    assert result == PROutcome.PENDING
