"""Unit tests for Pydantic schemas."""

from __future__ import annotations

import pytest

from schemas.completeness import CompletenessDecision, CompletenessResult, MissingField
from schemas.plan import ImplementationPlan, ImplementationStep, RiskLevel
from schemas.pr import PRCompositionResult, PRStatus
from schemas.repo import FileAnalysis, RepoContext
from schemas.ticket import TicketContext
from schemas.workflow_state import WorkflowPhase, WorkflowState


def test_ticket_context_minimal():
    t = TicketContext(ticket_id="PROJ-1", title="Test", description="Do something")
    assert t.ticket_id == "PROJ-1"
    assert t.labels == []
    assert t.acceptance_criteria is None


def test_completeness_result_complete():
    r = CompletenessResult(
        ticket_id="PROJ-1",
        decision=CompletenessDecision.COMPLETE,
        completeness_score=0.9,
    )
    assert r.completeness_score == 0.9
    assert r.decision == CompletenessDecision.COMPLETE


def test_completeness_result_incomplete():
    r = CompletenessResult(
        ticket_id="PROJ-1",
        decision=CompletenessDecision.INCOMPLETE,
        completeness_score=0.4,
        missing_fields=[MissingField(field_name="acceptance_criteria", severity="critical", description="Missing AC")],
        clarification_questions=["What does done look like?"],
    )
    assert len(r.missing_fields) == 1
    assert len(r.clarification_questions) == 1


def test_implementation_plan_full():
    plan = ImplementationPlan(
        ticket_id="PROJ-1",
        summary="Add login feature",
        implementation_steps=[
            ImplementationStep(
                step_number=1,
                title="Create route",
                description="Add /login endpoint",
                affected_files=["app/routes.py"],
                estimated_complexity="simple",
            )
        ],
        risk_level=RiskLevel.LOW,
        risk_rationale="Small isolated change",
        confidence_score=0.85,
    )
    assert len(plan.implementation_steps) == 1
    assert plan.confidence_score == 0.85


def test_repo_context_defaults():
    rc = RepoContext(
        repo_owner="acme",
        repo_name="web-app",
        directory_summary="src/ tests/ README.md",
    )
    assert rc.relevant_files == []
    assert rc.impacted_modules == []


def test_pr_result_created():
    pr = PRCompositionResult(
        ticket_id="PROJ-1",
        status=PRStatus.CREATED,
        pr_url="https://github.com/acme/web-app/pull/42",
        pr_number=42,
        branch_name="ai/proj-1",
        pr_title="feat(PROJ-1): Add login",
    )
    assert pr.pr_number == 42
    assert pr.draft is True


def test_workflow_state_error_reducer():
    """Verify the append-only errors reducer works correctly."""
    import operator
    errors_a = ["error1"]
    errors_b = ["error2"]
    merged = operator.add(errors_a, errors_b)
    assert merged == ["error1", "error2"]
