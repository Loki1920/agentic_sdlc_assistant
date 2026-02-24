from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal

from langgraph.graph import END, START, StateGraph

from agents.completeness_agent import completeness_check_node, post_clarification_node
from agents.code_proposal_agent import code_proposal_node
from agents.confluence_agent import confluence_agent_node
from agents.planner_agent import planner_node
from agents.pr_composer_agent import pr_composer_node
from agents.repo_scout_agent import repo_scout_node
from agents.test_agent import test_suggestion_node
from agents.ticket_fetcher import fetch_ticket_node
from app_logging.activity_logger import ActivityLogger
from persistence.database import init_db
from persistence.repository import TicketRepository
from schemas.workflow_state import WorkflowPhase, WorkflowState

logger = ActivityLogger("supervisor")
_repo = TicketRepository()


# ── Routing ────────────────────────────────────────────────────────────────────

def route_after_completeness(
    state: WorkflowState,
) -> Literal["post_clarification", "repo_scout"]:
    """
    Conditional edge after completeness check:
    - Incomplete ticket → post clarification comment, stop
    - Complete ticket → proceed to repo scout
    """
    if state.get("should_stop"):
        return "post_clarification"  # Also routes here for failed fetches
    if state.get("is_complete_ticket"):
        return "repo_scout"
    return "post_clarification"


# ── Terminal node ──────────────────────────────────────────────────────────────

def end_workflow_node(state: WorkflowState) -> dict:
    """Final node: record completion timestamp."""
    return {
        "current_phase": WorkflowPhase.COMPLETED,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }


# ── Graph construction ─────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    """
    Construct and compile the LangGraph StateGraph.

    Topology:
        START → fetch_ticket → completeness_check
          ├─ (incomplete/error) → post_clarification → end_workflow
          └─ (complete)        → repo_scout → confluence_docs → planner → code_proposal
                                  → test_suggestion → pr_composer → end_workflow
    """
    graph = StateGraph(WorkflowState)

    # Register nodes
    graph.add_node("fetch_ticket", fetch_ticket_node)
    graph.add_node("completeness_check", completeness_check_node)
    graph.add_node("post_clarification", post_clarification_node)
    graph.add_node("repo_scout", repo_scout_node)
    graph.add_node("confluence_docs", confluence_agent_node)
    graph.add_node("planner", planner_node)
    graph.add_node("code_proposal", code_proposal_node)
    graph.add_node("test_suggestion", test_suggestion_node)
    graph.add_node("pr_composer", pr_composer_node)
    graph.add_node("end_workflow", end_workflow_node)

    # Entry
    graph.add_edge(START, "fetch_ticket")
    graph.add_edge("fetch_ticket", "completeness_check")

    # Conditional branch
    graph.add_conditional_edges(
        "completeness_check",
        route_after_completeness,
        {
            "post_clarification": "post_clarification",
            "repo_scout": "repo_scout",
        },
    )

    # Incomplete → terminate
    graph.add_edge("post_clarification", "end_workflow")

    # Complete → sequential pipeline
    graph.add_edge("repo_scout", "confluence_docs")
    graph.add_edge("confluence_docs", "planner")
    graph.add_edge("planner", "code_proposal")
    graph.add_edge("code_proposal", "test_suggestion")
    graph.add_edge("test_suggestion", "pr_composer")
    graph.add_edge("pr_composer", "end_workflow")

    graph.add_edge("end_workflow", END)

    return graph.compile()


# Compiled graph (singleton)
_graph = None


def _get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


# ── Public entry point ─────────────────────────────────────────────────────────

def run_workflow(ticket_id: str) -> WorkflowState:
    """
    Main entry point called by the scheduler and CLI.
    Initialises state, runs the LangGraph, persists result.
    Returns the final WorkflowState.
    """
    run_id = str(uuid.uuid4())

    # Ensure DB exists
    init_db()

    # Create DB record
    _repo.create_run(run_id, ticket_id)
    _repo.mark_ticket_queued(ticket_id, run_id)

    initial_state: WorkflowState = {
        "run_id": run_id,
        "ticket_id": ticket_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "current_phase": WorkflowPhase.FETCHING_TICKET,
        "is_complete_ticket": None,
        "should_stop": False,
        "errors": [],
        "llm_call_ids": [],
        "mcp_tool_calls": [],
        "total_llm_calls": 0,
        "total_tokens_used": 0,
    }

    logger.info(
        "workflow_started",
        ticket_id=ticket_id,
        run_id=run_id,
    )

    try:
        final_state = _get_graph().invoke(initial_state)
    except Exception as exc:
        logger.error("workflow_failed", exc=exc, ticket_id=ticket_id, run_id=run_id)
        final_state = {
            **initial_state,
            "current_phase": WorkflowPhase.FAILED,
            "errors": [str(exc)],
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }

    # Persist final result
    try:
        _repo.finalize_run(run_id, final_state)
    except Exception as exc:
        logger.error("workflow_finalize_failed", exc=exc, run_id=run_id)

    phase = final_state.get("current_phase", WorkflowPhase.FAILED)
    errors = final_state.get("errors", [])

    logger.info(
        "workflow_completed",
        ticket_id=ticket_id,
        run_id=run_id,
        phase=str(phase),
        errors=errors,
        pr_url=(final_state.get("pr_result") or {}).get("pr_url") if isinstance(final_state.get("pr_result"), dict) else (
            final_state.get("pr_result").pr_url if final_state.get("pr_result") else None
        ),
    )

    return final_state
