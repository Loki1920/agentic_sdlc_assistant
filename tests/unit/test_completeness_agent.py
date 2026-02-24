"""Unit tests for the completeness agent (LLM mocked)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from schemas.completeness import CompletenessDecision, CompletenessResult
from schemas.ticket import TicketContext
from schemas.workflow_state import WorkflowPhase


def _make_state(ticket_id: str = "PROJ-1") -> dict:
    return {
        "run_id": "test-run-id",
        "ticket_id": ticket_id,
        "started_at": "2025-01-01T00:00:00+00:00",
        "ticket_context": TicketContext(
            ticket_id=ticket_id,
            title="Add user authentication",
            description="Users should be able to log in with email and password.",
            acceptance_criteria="Given valid credentials, the user is redirected to /dashboard.",
        ),
        "current_phase": WorkflowPhase.CHECKING_COMPLETENESS,
        "is_complete_ticket": None,
        "should_stop": False,
        "errors": [],
        "llm_call_ids": [],
        "mcp_tool_calls": [],
        "total_llm_calls": 0,
        "total_tokens_used": 0,
    }


@patch("agents.completeness_agent.CompletenessAgent.invoke_llm_structured")
def test_completeness_complete_ticket(mock_invoke):
    from agents.completeness_agent import completeness_check_node

    mock_invoke.return_value = (
        CompletenessResult(
            ticket_id="PROJ-1",
            decision=CompletenessDecision.COMPLETE,
            completeness_score=0.9,
        ),
        "call-id-1",
    )

    state = _make_state()
    result = completeness_check_node(state)

    assert result["is_complete_ticket"] is True
    assert result["completeness_result"].decision == CompletenessDecision.COMPLETE
    assert result["current_phase"] == WorkflowPhase.CHECKING_COMPLETENESS


@patch("agents.completeness_agent.CompletenessAgent.invoke_llm_structured")
def test_completeness_incomplete_ticket(mock_invoke):
    from agents.completeness_agent import completeness_check_node
    from schemas.completeness import MissingField

    mock_invoke.return_value = (
        CompletenessResult(
            ticket_id="PROJ-1",
            decision=CompletenessDecision.INCOMPLETE,
            completeness_score=0.3,
            missing_fields=[
                MissingField(field_name="acceptance_criteria", severity="critical", description="Missing AC")
            ],
            clarification_questions=["What are the acceptance criteria?"],
        ),
        "call-id-2",
    )

    state = _make_state()
    result = completeness_check_node(state)

    assert result["is_complete_ticket"] is False
    assert result["completeness_result"].decision == CompletenessDecision.INCOMPLETE


def test_completeness_missing_ticket_context():
    from agents.completeness_agent import completeness_check_node

    state = _make_state()
    state["ticket_context"] = None

    result = completeness_check_node(state)

    assert result["current_phase"] == WorkflowPhase.FAILED
    assert any("completeness_agent" in e for e in result["errors"])


@patch("agents.completeness_agent.CompletenessAgent.invoke_llm_structured")
def test_completeness_llm_error(mock_invoke):
    from agents.completeness_agent import completeness_check_node

    mock_invoke.side_effect = RuntimeError("Bedrock timeout")

    state = _make_state()
    result = completeness_check_node(state)

    assert result["current_phase"] == WorkflowPhase.FAILED
    assert any("Bedrock timeout" in e for e in result["errors"])
