"""Unit tests for the code proposal agent (LLM mocked)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from schemas.code_proposal import CodeProposal, FileDiff, ChangeType
from schemas.plan import ImplementationPlan, ImplementationStep, RiskLevel
from schemas.repo import FileAnalysis, RepoContext
from schemas.ticket import TicketContext
from schemas.workflow_state import WorkflowPhase


def _make_ticket() -> TicketContext:
    return TicketContext(
        ticket_id="PROJ-1",
        title="Add login endpoint",
        description="Create POST /login that validates credentials.",
    )


def _make_plan() -> ImplementationPlan:
    return ImplementationPlan(
        ticket_id="PROJ-1",
        summary="Implement login endpoint",
        implementation_steps=[
            ImplementationStep(
                step_number=1,
                title="Add route",
                description="Create POST /login",
                affected_files=["app/routes.py"],
                estimated_complexity="simple",
            )
        ],
        risk_level=RiskLevel.LOW,
        risk_rationale="Single new route",
        confidence_score=0.8,
    )


def _make_proposal() -> CodeProposal:
    return CodeProposal(
        ticket_id="PROJ-1",
        summary="Add login route",
        file_changes=[
            FileDiff(
                file_path="app/routes.py",
                change_type=ChangeType.MODIFY,
                rationale="Add POST /login handler",
                proposed_content="def login(): pass",
            )
        ],
        confidence_score=0.75,
    )


def _make_state(**overrides) -> dict:
    base = {
        "run_id": "test-run-id",
        "ticket_id": "PROJ-1",
        "started_at": "2025-01-01T00:00:00+00:00",
        "ticket_context": _make_ticket(),
        "repo_context": RepoContext(repo_owner="org", repo_name="repo", directory_summary="📁 app"),
        "implementation_plan": _make_plan(),
        "current_phase": WorkflowPhase.PROPOSING_CODE,
        "errors": [],
        "llm_call_ids": [],
        "mcp_tool_calls": [],
        "total_llm_calls": 0,
        "total_tokens_used": 0,
        "should_stop": False,
    }
    base.update(overrides)
    return base


@patch("agents.code_proposal_agent.CodeProposalAgent.invoke_llm_structured")
def test_code_proposal_happy_path(mock_invoke):
    from agents.code_proposal_agent import code_proposal_node

    mock_invoke.return_value = (_make_proposal(), "call-id-1")

    result = code_proposal_node(_make_state())

    assert "code_proposal" in result
    assert len(result["code_proposal"].file_changes) == 1
    assert result["current_phase"] == WorkflowPhase.SUGGESTING_TESTS
    assert result["total_llm_calls"] == 1


def test_code_proposal_missing_ticket_context():
    from agents.code_proposal_agent import code_proposal_node

    result = code_proposal_node(_make_state(ticket_context=None))

    assert result["current_phase"] == WorkflowPhase.FAILED
    assert result["should_stop"] is True
    assert any("code_proposal" in e for e in result["errors"])


def test_code_proposal_missing_plan():
    from agents.code_proposal_agent import code_proposal_node

    result = code_proposal_node(_make_state(implementation_plan=None))

    assert result["current_phase"] == WorkflowPhase.FAILED
    assert result["should_stop"] is True


@patch("agents.code_proposal_agent.CodeProposalAgent.invoke_llm_structured")
def test_code_proposal_llm_exception(mock_invoke):
    from agents.code_proposal_agent import code_proposal_node

    mock_invoke.side_effect = RuntimeError("LLM unavailable")

    result = code_proposal_node(_make_state())

    assert result["current_phase"] == WorkflowPhase.FAILED
    assert any("LLM unavailable" in e for e in result["errors"])
