"""Unit tests for the PR composer agent."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from schemas.pr import PRCompositionResult, PRStatus
from schemas.ticket import TicketContext
from schemas.workflow_state import WorkflowPhase


def _make_state(**overrides) -> dict:
    base = {
        "run_id": "test-run-id",
        "ticket_id": "PROJ-1",
        "started_at": "2025-01-01T00:00:00+00:00",
        "ticket_context": TicketContext(
            ticket_id="PROJ-1",
            title="Add login page",
            description="Login form",
        ),
        "implementation_plan": None,
        "code_proposal": None,
        "test_suggestions": None,
        "confluence_context": None,
        "current_phase": WorkflowPhase.COMPOSING_PR,
        "errors": [],
        "llm_call_ids": [],
        "mcp_tool_calls": [],
        "total_llm_calls": 0,
        "total_tokens_used": 0,
        "should_stop": False,
    }
    base.update(overrides)
    return base


@patch("agents.pr_composer_agent.settings")
def test_pr_composer_dry_run_skips_mcp(mock_settings):
    """dry_run=True must return SKIPPED without touching GitHub MCP."""
    mock_settings.dry_run = True
    mock_settings.jira_url = "https://jira.example.com"

    from agents.pr_composer_agent import pr_composer_node

    result = pr_composer_node(_make_state())

    assert result["pr_result"].status == PRStatus.SKIPPED
    assert result["current_phase"] == WorkflowPhase.COMPLETED
    assert "[DRY RUN]" in result["pr_result"].pr_title


@patch("agents.pr_composer_agent.PRComposerAgent.run_async")
def test_pr_composer_happy_path(mock_run_async, monkeypatch):
    """run_async(_do_create_pr) returns a successful PRCompositionResult."""
    monkeypatch.setenv("DRY_RUN", "false")

    pr_result = PRCompositionResult(
        ticket_id="PROJ-1",
        status=PRStatus.CREATED,
        pr_url="https://github.com/org/repo/pull/42",
        pr_number=42,
        branch_name="ai/proj-1",
        base_branch="main",
        pr_title="feat(PROJ-1): Add login page [AI]",
        pr_body="## Summary",
        draft=True,
    )
    mock_run_async.return_value = pr_result

    from agents.pr_composer_agent import pr_composer_node

    result = pr_composer_node(_make_state())

    assert result["pr_result"].status == PRStatus.CREATED
    assert result["pr_result"].pr_number == 42
    assert result["current_phase"] == WorkflowPhase.COMPLETED


@patch("agents.pr_composer_agent.PRComposerAgent.run_async")
def test_pr_composer_mcp_exception(mock_run_async, monkeypatch):
    """MCP failure returns FAILED phase with error message."""
    monkeypatch.setenv("DRY_RUN", "false")
    mock_run_async.side_effect = RuntimeError("GitHub API 503")

    from agents.pr_composer_agent import pr_composer_node

    result = pr_composer_node(_make_state())

    assert result["current_phase"] == WorkflowPhase.FAILED
    assert result["pr_result"].status == PRStatus.FAILED
    assert any("GitHub API 503" in e for e in result["errors"])
