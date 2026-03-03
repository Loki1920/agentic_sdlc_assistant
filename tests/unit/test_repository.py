"""Unit tests for the persistence repository."""
from __future__ import annotations

import pytest
from datetime import datetime, timezone

from persistence.models import PROutcome, RunStatus

# fresh_db fixture is provided by conftest.py
pytestmark = pytest.mark.usefixtures("fresh_db")


# ── is_ticket_processed ───────────────────────────────────────────────────────

def test_is_ticket_processed_new_ticket():
    from persistence.repository import TicketRepository

    repo = TicketRepository()
    assert repo.is_ticket_processed("PROJ-99") is False


def test_is_ticket_processed_after_queued():
    from persistence.repository import TicketRepository

    repo = TicketRepository()
    repo.mark_ticket_queued("PROJ-1", "run-1")
    assert repo.is_ticket_processed("PROJ-1") is True


def test_is_ticket_processed_reprocess_requested():
    """When reprocess_requested=True, ticket should be treated as unprocessed."""
    from persistence.repository import TicketRepository

    repo = TicketRepository()
    repo.mark_ticket_queued("PROJ-1", "run-1")
    repo.request_reprocess("PROJ-1")
    assert repo.is_ticket_processed("PROJ-1") is False


# ── create_run / update_run ───────────────────────────────────────────────────

def test_create_run_stores_record():
    from persistence.database import get_db_session
    from persistence.models import TicketRun
    from persistence.repository import TicketRepository

    repo = TicketRepository()
    repo.create_run("run-abc", "PROJ-1")

    with get_db_session() as session:
        run = session.get(TicketRun, "run-abc")
        assert run is not None
        assert run.ticket_id == "PROJ-1"
        assert run.status == RunStatus.RUNNING


# ── finalize_run ──────────────────────────────────────────────────────────────

def _minimal_final_state(ticket_id: str = "PROJ-1") -> dict:
    """Build the minimum state dict accepted by finalize_run()."""
    return {
        "ticket_id": ticket_id,
        "current_phase": "COMPLETED",
        "errors": [],
        "is_complete_ticket": True,
        "completeness_result": None,
        "implementation_plan": None,
        "code_proposal": None,
        "test_suggestions": None,
        "pr_result": None,
        "total_llm_calls": 2,
        "total_tokens_used": 500,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "llm_call_ids": [],
        "mcp_tool_calls": [],
    }


def test_finalize_run_complete_pipeline():
    from persistence.database import get_db_session
    from persistence.models import TicketRun
    from persistence.repository import TicketRepository

    repo = TicketRepository()
    repo.create_run("run-fin", "PROJ-2")
    repo.finalize_run("run-fin", _minimal_final_state("PROJ-2"))

    with get_db_session() as session:
        run = session.get(TicketRun, "run-fin")
        assert run is not None
        assert run.status == RunStatus.COMPLETED_COMPLETE
        assert run.total_llm_calls == 2
        assert run.error_occurred is False


def test_finalize_run_with_errors():
    from persistence.database import get_db_session
    from persistence.models import TicketRun
    from persistence.repository import TicketRepository

    repo = TicketRepository()
    repo.create_run("run-err", "PROJ-3")

    state = _minimal_final_state("PROJ-3")
    state["errors"] = ["repo_scout: connection refused"]
    state["current_phase"] = "FAILED"

    repo.finalize_run("run-err", state)

    with get_db_session() as session:
        run = session.get(TicketRun, "run-err")
        assert run.status == RunStatus.FAILED
        assert run.error_occurred is True


# ── set_pr_outcome ────────────────────────────────────────────────────────────

def test_set_pr_outcome_updates_correctly():
    from persistence.database import get_db_session
    from persistence.models import TicketRun
    from persistence.repository import TicketRepository

    repo = TicketRepository()
    repo.create_run("run-pr", "PROJ-4")
    repo.set_pr_outcome("run-pr", PROutcome.APPROVED)

    with get_db_session() as session:
        run = session.get(TicketRun, "run-pr")
        assert run.pr_outcome == PROutcome.APPROVED
