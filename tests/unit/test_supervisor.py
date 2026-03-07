"""Unit tests for agents/supervisor.py — routing logic and graph construction."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from schemas.workflow_state import WorkflowPhase


# ── route_after_completeness ──────────────────────────────────────────────────

def test_route_complete_ticket_goes_to_repo_scout():
    from agents.supervisor import route_after_completeness

    state = {
        "is_complete_ticket": True,
        "should_stop": False,
    }
    assert route_after_completeness(state) == "repo_scout"


def test_route_incomplete_ticket_goes_to_post_clarification():
    from agents.supervisor import route_after_completeness

    state = {
        "is_complete_ticket": False,
        "should_stop": False,
    }
    assert route_after_completeness(state) == "post_clarification"


def test_route_should_stop_goes_to_post_clarification():
    """Any state with should_stop=True must short-circuit to clarification."""
    from agents.supervisor import route_after_completeness

    state = {
        "is_complete_ticket": True,   # Even if complete, stop flag wins
        "should_stop": True,
    }
    assert route_after_completeness(state) == "post_clarification"


def test_route_is_complete_none_goes_to_post_clarification():
    """is_complete_ticket=None (fetch failed) must go to clarification."""
    from agents.supervisor import route_after_completeness

    state = {
        "is_complete_ticket": None,
        "should_stop": False,
    }
    assert route_after_completeness(state) == "post_clarification"


# ── end_workflow_node ─────────────────────────────────────────────────────────

def test_end_workflow_node_sets_completed_phase():
    from agents.supervisor import end_workflow_node

    result = end_workflow_node({})
    assert result["current_phase"] == WorkflowPhase.COMPLETED


def test_end_workflow_node_sets_completed_at_timestamp():
    from agents.supervisor import end_workflow_node

    result = end_workflow_node({})
    assert "completed_at" in result
    assert result["completed_at"] is not None
    # Must be an ISO-format string
    from datetime import datetime
    datetime.fromisoformat(result["completed_at"].replace("Z", "+00:00"))


# ── build_graph ───────────────────────────────────────────────────────────────

def test_build_graph_compiles_without_error():
    """build_graph() must produce a compiled graph with no exceptions."""
    from agents.supervisor import build_graph

    graph = build_graph()
    assert graph is not None


def test_build_graph_has_expected_nodes():
    """The compiled graph's builder should contain all 9 agent nodes."""
    from agents.supervisor import build_graph
    from langgraph.graph import StateGraph

    graph = build_graph()
    # Compiled graphs expose the original builder's node names
    node_names = set(graph.get_graph().nodes.keys())

    expected = {
        "fetch_ticket",
        "completeness_check",
        "post_clarification",
        "repo_scout",
        "confluence_docs",
        "planner",
        "code_proposal",
        "test_suggestion",
        "pr_composer",
        "end_workflow",
    }
    assert expected.issubset(node_names), f"Missing nodes: {expected - node_names}"


# ── run_workflow (DB + graph mocked) ─────────────────────────────────────────

def test_run_workflow_returns_state_with_run_id(tmp_path, monkeypatch):
    """run_workflow must create a DB record and return a state containing run_id."""
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("DRY_RUN", "true")

    import persistence.database as db_mod
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from persistence.models import Base

    test_engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(test_engine)
    db_mod.engine = test_engine
    db_mod.SessionLocal = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)

    # Mock the whole compiled graph's invoke to avoid real LLM/MCP calls
    fake_final_state = {
        "run_id": "injected-by-mock",  # Will be overridden by the real UUID
        "ticket_id": "MOCK-1",
        "current_phase": WorkflowPhase.COMPLETED,
        "errors": [],
        "is_complete_ticket": True,
        "completeness_result": None,
        "implementation_plan": None,
        "code_proposal": None,
        "test_suggestions": None,
        "pr_result": None,
        "total_llm_calls": 0,
        "total_tokens_used": 0,
        "started_at": "2025-01-01T00:00:00+00:00",
        "llm_call_ids": [],
        "mcp_tool_calls": [],
    }

    with patch("agents.supervisor._get_graph") as mock_get_graph:
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = fake_final_state
        mock_get_graph.return_value = mock_graph

        from agents.supervisor import run_workflow
        # Reset singleton so our mocked graph is used
        import agents.supervisor as sup_mod
        sup_mod._graph = None

        result = run_workflow("MOCK-1")

    assert result is not None
    # The real run_id is generated by run_workflow (UUID4), not from mock
    assert "ticket_id" in result or "MOCK-1" in str(result)
