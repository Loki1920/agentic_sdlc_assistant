"""Unit tests for the ticket fetcher agent and its helpers."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from schemas.ticket import TicketContext
from schemas.workflow_state import WorkflowPhase


# ── Helpers for _parse_jira_response ─────────────────────────────────────────

def test_parse_jira_response_flat_fields():
    from agents.ticket_fetcher import _parse_jira_response

    data = {
        "fields": {
            "summary": "Add login page",
            "description": "Users need a login page.",
            "status": {"name": "Ready for Dev"},
            "priority": {"name": "High"},
            "assignee": {"displayName": "Alice"},
            "reporter": {"displayName": "Bob"},
            "labels": ["auth", "frontend"],
            "components": [{"name": "web"}],
            "issuelinks": [],
        }
    }
    result = _parse_jira_response(data, "PROJ-1")

    assert isinstance(result, TicketContext)
    assert result.ticket_id == "PROJ-1"
    assert result.title == "Add login page"
    assert result.description == "Users need a login page."
    assert result.status == "Ready for Dev"
    assert result.priority == "High"
    assert result.assignee == "Alice"
    assert result.reporter == "Bob"
    assert result.labels == ["auth", "frontend"]
    assert result.components == ["web"]


def test_parse_jira_response_missing_optional_fields():
    from agents.ticket_fetcher import _parse_jira_response

    data = {"fields": {"summary": "Minimal ticket"}}
    result = _parse_jira_response(data, "PROJ-2")

    assert result.title == "Minimal ticket"
    assert result.description == ""
    assert result.acceptance_criteria is None
    assert result.labels == []


def test_parse_jira_response_adf_description():
    from agents.ticket_fetcher import _parse_jira_response

    adf = {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": "Hello"}, {"type": "text", "text": " world"}],
            }
        ],
    }
    data = {"fields": {"summary": "ADF test", "description": adf}}
    result = _parse_jira_response(data, "PROJ-3")

    assert "Hello" in result.description
    assert "world" in result.description


def test_parse_jira_response_pii_redacted():
    """PII in description and acceptance criteria should be redacted."""
    from agents.ticket_fetcher import _parse_jira_response

    data = {
        "fields": {
            "summary": "Contact form",
            "description": "Send emails to user@example.com for notifications.",
            "acceptance_criteria": "Call support at 800-555-1234.",
        }
    }
    result = _parse_jira_response(data, "PROJ-4")

    assert "user@example.com" not in result.description
    assert "[EMAIL REDACTED]" in result.description
    assert "800-555-1234" not in (result.acceptance_criteria or "")


# ── _flatten_adf ──────────────────────────────────────────────────────────────

def test_flatten_adf_plain_string():
    from agents.ticket_fetcher import _flatten_adf

    assert _flatten_adf("plain text") == "plain text"


def test_flatten_adf_nested():
    from agents.ticket_fetcher import _flatten_adf

    adf = {
        "type": "doc",
        "content": [
            {"type": "text", "text": "foo"},
            {"type": "text", "text": "bar"},
        ],
    }
    result = _flatten_adf(adf)
    assert "foo" in result
    assert "bar" in result


# ── TicketFetcherAgent ────────────────────────────────────────────────────────

def _make_state(ticket_id: str = "PROJ-1") -> dict:
    return {
        "run_id": "test-run-id",
        "ticket_id": ticket_id,
        "started_at": "2025-01-01T00:00:00+00:00",
        "ticket_context": None,
        "current_phase": WorkflowPhase.FETCHING_TICKET,
        "errors": [],
        "llm_call_ids": [],
        "mcp_tool_calls": [],
        "total_llm_calls": 0,
        "total_tokens_used": 0,
        "should_stop": False,
    }


@patch("agents.ticket_fetcher.TicketFetcherAgent.run_async")
def test_ticket_fetcher_happy_path(mock_run_async):
    from agents.ticket_fetcher import fetch_ticket_node

    mock_run_async.return_value = {
        "fields": {
            "summary": "Add login page",
            "description": "Users need a login form.",
            "status": {"name": "Ready for Dev"},
        }
    }

    state = _make_state()
    result = fetch_ticket_node(state)

    assert "ticket_context" in result
    assert isinstance(result["ticket_context"], TicketContext)
    assert result["ticket_context"].title == "Add login page"
    assert result["current_phase"] == WorkflowPhase.CHECKING_COMPLETENESS


@patch("agents.ticket_fetcher.TicketFetcherAgent.run_async")
def test_ticket_fetcher_mcp_exception(mock_run_async):
    from agents.ticket_fetcher import fetch_ticket_node

    mock_run_async.side_effect = RuntimeError("Jira MCP timeout")

    state = _make_state()
    result = fetch_ticket_node(state)

    assert result["current_phase"] == WorkflowPhase.FAILED
    assert result["should_stop"] is True
    assert any("Jira MCP timeout" in e for e in result["errors"])
