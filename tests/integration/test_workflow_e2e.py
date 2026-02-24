"""
E2E integration test: runs the full workflow against a real Jira ticket and GitHub repo.

Requires a fully configured .env file.

Run with: pytest tests/integration/test_workflow_e2e.py -v -s
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN") or not os.getenv("JIRA_API_TOKEN"),
    reason="Integration credentials not set",
)


def test_workflow_single_ticket(tmp_path, monkeypatch):
    """Run a full workflow and verify basic invariants."""
    # Use tmp_path for DB and logs to avoid polluting real state
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("ACTIVITY_LOG_PATH", str(tmp_path / "activity.jsonl"))
    monkeypatch.setenv("LLM_LOG_PATH", str(tmp_path / "llm_calls.jsonl"))
    monkeypatch.setenv("DRY_RUN", "true")  # Don't create real PRs / Jira comments

    ticket_id = os.getenv("TEST_JIRA_TICKET_ID", "TEST-1")

    from persistence.database import init_db
    init_db()

    from agents.supervisor import run_workflow
    final_state = run_workflow(ticket_id)

    # Basic invariants
    assert final_state is not None
    assert final_state.get("ticket_id") == ticket_id
    assert final_state.get("run_id") is not None

    # Either ticket was fetched and completeness run, or it failed gracefully
    assert final_state.get("current_phase") is not None

    # Completeness agent must have run and logged an LLM call
    if final_state.get("ticket_context") is not None:
        assert final_state.get("completeness_result") is not None
        assert len(final_state.get("llm_call_ids", [])) >= 1

        # LLM log file must have at least one entry
        log_path = tmp_path / "llm_calls.jsonl"
        assert log_path.exists(), "LLM call log file not created"
        lines = log_path.read_text().strip().splitlines()
        assert len(lines) >= 1, "Expected at least 1 LLM call log entry"

    # Activity log must exist
    activity_log = tmp_path / "activity.jsonl"
    assert activity_log.exists(), "Activity log not created"

    # SQLite record must exist
    from persistence.repository import TicketRepository
    repo = TicketRepository()
    # Re-processing same ticket should be blocked
    assert repo.is_ticket_processed(ticket_id) is True
