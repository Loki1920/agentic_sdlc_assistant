"""Unit tests for the repo scout agent and its helpers."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from schemas.repo import FileAnalysis, RepoContext
from schemas.ticket import TicketContext
from schemas.workflow_state import WorkflowPhase


# ── _extract_keywords ─────────────────────────────────────────────────────────

def test_extract_keywords_basic():
    from agents.repo_scout_agent import _extract_keywords

    ticket = MagicMock()
    ticket.title = "Add authentication login"
    ticket.description = "Users should be able to authenticate with password"

    keywords = _extract_keywords(ticket)

    assert "authentication" in keywords or "login" in keywords
    assert len(keywords) <= 5


def test_extract_keywords_filters_stopwords():
    from agents.repo_scout_agent import _extract_keywords

    ticket = MagicMock()
    ticket.title = "Users should have login"
    ticket.description = "This feature will need testing"

    keywords = _extract_keywords(ticket)

    # stopwords should not appear
    assert "should" not in keywords
    assert "have" not in keywords
    assert "will" not in keywords
    assert "need" not in keywords


def test_extract_keywords_deduplication():
    from agents.repo_scout_agent import _extract_keywords

    ticket = MagicMock()
    ticket.title = "login login login authentication"
    ticket.description = ""

    keywords = _extract_keywords(ticket)

    assert keywords.count("login") == 1


# ── RepoScoutAgent ────────────────────────────────────────────────────────────

def _make_state(**overrides) -> dict:
    base = {
        "run_id": "test-run-id",
        "ticket_id": "PROJ-1",
        "started_at": "2025-01-01T00:00:00+00:00",
        "ticket_context": TicketContext(
            ticket_id="PROJ-1",
            title="Add authentication",
            description="Implement JWT authentication.",
        ),
        "current_phase": WorkflowPhase.SCOUTING_REPO,
        "errors": [],
        "llm_call_ids": [],
        "mcp_tool_calls": [],
        "total_llm_calls": 0,
        "total_tokens_used": 0,
        "should_stop": False,
    }
    base.update(overrides)
    return base


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


@patch("agents.repo_scout_agent.RepoScoutAgent.invoke_llm_structured")
@patch("agents.repo_scout_agent.RepoScoutAgent.run_async")
def test_repo_scout_happy_path(mock_run_async, mock_invoke):
    from agents.repo_scout_agent import repo_scout_node

    mock_run_async.return_value = (
        "📁 app\n📄 README.md",  # dir_summary
        "### requirements.txt\nrequests>=2.0",  # dep_content
        "### app/auth.py\n```python\ndef login(): pass\n```",  # file_listing
        ["app/auth.py"],  # relevant_paths
    )
    mock_invoke.return_value = (_make_repo_context(), "call-id-1")

    result = repo_scout_node(_make_state())

    assert "repo_context" in result
    assert result["repo_context"].primary_language == "Python"
    assert result["current_phase"] == WorkflowPhase.PLANNING
    assert result["total_llm_calls"] == 1


def test_repo_scout_missing_ticket_context():
    from agents.repo_scout_agent import repo_scout_node

    result = repo_scout_node(_make_state(ticket_context=None))

    assert result["current_phase"] == WorkflowPhase.FAILED
    assert result["should_stop"] is True
    assert any("repo_scout" in e for e in result["errors"])


@patch("agents.repo_scout_agent.RepoScoutAgent.run_async")
def test_repo_scout_mcp_exception(mock_run_async):
    from agents.repo_scout_agent import repo_scout_node

    mock_run_async.side_effect = RuntimeError("GitHub MCP subprocess died")

    result = repo_scout_node(_make_state())

    assert result["current_phase"] == WorkflowPhase.FAILED
    assert any("GitHub MCP subprocess died" in e for e in result["errors"])


# ── Inner helpers log warnings ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_file_content_logs_warning_on_failure():
    """_get_file_content should warn and return '' on exception."""
    from agents.repo_scout_agent import _get_file_content

    failing_tool = MagicMock()
    failing_tool.name = "get_file_contents"
    failing_tool.ainvoke = AsyncMock(side_effect=ConnectionError("network error"))

    with patch("agents.repo_scout_agent.logger") as mock_logger:
        result = await _get_file_content([failing_tool], "org", "repo", "app/auth.py")

    assert result == ""
    mock_logger.warning.assert_called_once()
    call_kwargs = mock_logger.warning.call_args
    assert "file_fetch_failed" in call_kwargs[0]


@pytest.mark.asyncio
async def test_search_code_logs_warning_on_failure():
    """_search_code should warn and return [] on exception."""
    from agents.repo_scout_agent import _search_code

    failing_tool = MagicMock()
    failing_tool.name = "search_code"
    failing_tool.ainvoke = AsyncMock(side_effect=ConnectionError("network error"))

    with patch("agents.repo_scout_agent.logger") as mock_logger:
        result = await _search_code([failing_tool], "org", "repo", "authentication")

    assert result == []
    mock_logger.warning.assert_called_once()
    call_kwargs = mock_logger.warning.call_args
    assert "code_search_failed" in call_kwargs[0]
