"""Unit tests for the planner agent (LLM mocked)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from schemas.plan import ImplementationPlan, ImplementationStep, RiskLevel
from schemas.repo import FileAnalysis, RepoContext
from schemas.ticket import TicketContext
from schemas.workflow_state import WorkflowPhase


def _make_ticket() -> TicketContext:
    return TicketContext(
        ticket_id="PROJ-1",
        title="Add user authentication",
        description="Users should be able to log in with email and password.",
        acceptance_criteria="Given valid credentials, redirect to /dashboard.",
    )


def _make_repo_context() -> RepoContext:
    return RepoContext(
        repo_owner="org",
        repo_name="repo",
        directory_summary="📁 app\n📄 README.md",
        primary_language="Python",
        relevant_files=[
            FileAnalysis(
                file_path="app/auth.py",
                relevance_score=0.9,
                relevance_reason="Auth module",
            )
        ],
    )


def _make_plan() -> ImplementationPlan:
    return ImplementationPlan(
        ticket_id="PROJ-1",
        summary="Implement JWT-based authentication",
        implementation_steps=[
            ImplementationStep(
                step_number=1,
                title="Create auth module",
                description="Add login endpoint",
                affected_files=["app/auth.py"],
                estimated_complexity="simple",
            )
        ],
        risk_level=RiskLevel.LOW,
        risk_rationale="Low risk — isolated auth module",
        confidence_score=0.85,
    )


def _make_state(**overrides) -> dict:
    base = {
        "run_id": "test-run-id",
        "ticket_id": "PROJ-1",
        "started_at": "2025-01-01T00:00:00+00:00",
        "ticket_context": _make_ticket(),
        "repo_context": _make_repo_context(),
        "confluence_context": None,
        "current_phase": WorkflowPhase.PLANNING,
        "errors": [],
        "llm_call_ids": [],
        "mcp_tool_calls": [],
        "total_llm_calls": 0,
        "total_tokens_used": 0,
        "should_stop": False,
    }
    base.update(overrides)
    return base


@patch("agents.planner_agent.PlannerAgent.invoke_llm_structured")
def test_planner_happy_path(mock_invoke):
    from agents.planner_agent import planner_node

    mock_invoke.return_value = (_make_plan(), "call-id-1")

    result = planner_node(_make_state())

    assert "implementation_plan" in result
    assert result["implementation_plan"].summary == "Implement JWT-based authentication"
    assert result["current_phase"] == WorkflowPhase.PROPOSING_CODE
    assert "call-id-1" in result["llm_call_ids"]
    assert result["total_llm_calls"] == 1


def test_planner_missing_ticket_context():
    from agents.planner_agent import planner_node

    result = planner_node(_make_state(ticket_context=None))

    assert result["current_phase"] == WorkflowPhase.FAILED
    assert result["should_stop"] is True
    assert any("planner" in e for e in result["errors"])


def test_planner_missing_repo_context():
    from agents.planner_agent import planner_node

    result = planner_node(_make_state(repo_context=None))

    assert result["current_phase"] == WorkflowPhase.FAILED
    assert result["should_stop"] is True


@patch("agents.planner_agent.PlannerAgent.invoke_llm_structured")
def test_planner_llm_exception(mock_invoke):
    from agents.planner_agent import planner_node

    mock_invoke.side_effect = RuntimeError("Bedrock throttled")

    result = planner_node(_make_state())

    assert result["current_phase"] == WorkflowPhase.FAILED
    assert any("Bedrock throttled" in e for e in result["errors"])
