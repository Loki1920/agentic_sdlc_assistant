"""Unit tests for the test suggestion agent (LLM mocked)."""
from __future__ import annotations

from unittest.mock import patch

from schemas.code_proposal import CodeProposal, FileDiff, ChangeType
from schemas.plan import ImplementationPlan, ImplementationStep, RiskLevel
from schemas.repo import RepoContext
from schemas.test_suggestion import TestCase, TestSuggestions
from schemas.ticket import TicketContext
from schemas.workflow_state import WorkflowPhase


def _make_state(**overrides) -> dict:
    ticket = TicketContext(
        ticket_id="PROJ-1",
        title="Add login page",
        description="Create a login form.",
        acceptance_criteria="User can log in.",
    )
    plan = ImplementationPlan(
        ticket_id="PROJ-1",
        summary="Add login route",
        implementation_steps=[
            ImplementationStep(
                step_number=1,
                title="Add route",
                description="POST /login",
                affected_files=["app/routes.py"],
                estimated_complexity="simple",
            )
        ],
        risk_level=RiskLevel.LOW,
        risk_rationale="Simple route addition",
        confidence_score=0.8,
    )
    proposal = CodeProposal(
        ticket_id="PROJ-1",
        summary="Login route",
        file_changes=[
            FileDiff(
                file_path="app/routes.py",
                change_type=ChangeType.MODIFY,
                rationale="Add handler",
                proposed_content="def login(): pass",
            )
        ],
        confidence_score=0.75,
    )
    base = {
        "run_id": "test-run-id",
        "ticket_id": "PROJ-1",
        "started_at": "2025-01-01T00:00:00+00:00",
        "ticket_context": ticket,
        "implementation_plan": plan,
        "code_proposal": proposal,
        "repo_context": RepoContext(repo_owner="org", repo_name="repo", directory_summary="📁 app"),
        "current_phase": WorkflowPhase.SUGGESTING_TESTS,
        "errors": [],
        "llm_call_ids": [],
        "mcp_tool_calls": [],
        "total_llm_calls": 0,
        "total_tokens_used": 0,
        "should_stop": False,
    }
    base.update(overrides)
    return base


def _make_suggestions() -> TestSuggestions:
    return TestSuggestions(
        ticket_id="PROJ-1",
        framework="pytest",
        test_cases=[
            TestCase(
                test_name="test_login_success",
                description="Valid credentials return 200",
                test_type="unit",
                target_function_or_class="login",
                arrange="Set up valid credentials",
                act="Call POST /login with valid credentials",
                assert_description="Response status code is 200",
                edge_case=False,
            )
        ],
        confidence_score=0.8,
    )


@patch("agents.test_agent.TestAgent.invoke_llm_structured")
def test_test_agent_happy_path(mock_invoke):
    from agents.test_agent import test_suggestion_node

    mock_invoke.return_value = (_make_suggestions(), "call-id-1")

    result = test_suggestion_node(_make_state())

    assert "test_suggestions" in result
    assert len(result["test_suggestions"].test_cases) == 1
    assert result["current_phase"] == WorkflowPhase.COMPOSING_PR
    assert result["total_llm_calls"] == 1


def test_test_agent_missing_ticket_context():
    from agents.test_agent import test_suggestion_node

    result = test_suggestion_node(_make_state(ticket_context=None))

    assert result["current_phase"] == WorkflowPhase.FAILED
    assert result["should_stop"] is True
    assert any("test_agent" in e for e in result["errors"])


def test_test_agent_missing_plan():
    from agents.test_agent import test_suggestion_node

    result = test_suggestion_node(_make_state(implementation_plan=None))

    assert result["current_phase"] == WorkflowPhase.FAILED
    assert result["should_stop"] is True


@patch("agents.test_agent.TestAgent.invoke_llm_structured")
def test_test_agent_llm_exception(mock_invoke):
    from agents.test_agent import test_suggestion_node

    mock_invoke.side_effect = RuntimeError("Token limit exceeded")

    result = test_suggestion_node(_make_state())

    assert result["current_phase"] == WorkflowPhase.FAILED
    assert any("Token limit exceeded" in e for e in result["errors"])
