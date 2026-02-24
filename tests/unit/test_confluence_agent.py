"""
Unit tests for the ConfluenceAgent.

All MCP calls and LLM invocations are mocked — no credentials required.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.confluence_agent import (
    ConfluenceAgent,
    _extract_keywords,
    _format_pages_for_prompt,
    _page_url,
)
from schemas.confluence import ConfluenceContext, ConfluencePage
from schemas.workflow_state import WorkflowPhase


# ── _extract_keywords ────────────────────────────────────────────────────────


def test_extract_keywords_basic():
    ticket = MagicMock()
    ticket.title = "Add payment gateway integration"
    ticket.description = "Users should be able to pay with credit cards"
    keywords = _extract_keywords(ticket)
    assert "payment" in keywords
    assert "gateway" in keywords
    assert len(keywords) <= 5


def test_extract_keywords_filters_stopwords():
    ticket = MagicMock()
    ticket.title = "Users should will need with from that this"
    ticket.description = ""
    keywords = _extract_keywords(ticket)
    assert "should" not in keywords
    assert "will" not in keywords
    assert "need" not in keywords


def test_extract_keywords_deduplicates():
    ticket = MagicMock()
    ticket.title = "payment payment payment"
    ticket.description = "payment again"
    keywords = _extract_keywords(ticket)
    assert keywords.count("payment") == 1


# ── _page_url ────────────────────────────────────────────────────────────────


def test_page_url_with_webui_link():
    page = {"_links": {"webui": "/spaces/ENG/pages/12345"}}
    with patch("agents.confluence_agent.settings") as mock_settings:
        mock_settings.confluence_url = "https://myorg.atlassian.net/wiki"
        url = _page_url(page)
    assert url == "https://myorg.atlassian.net/wiki/spaces/ENG/pages/12345"


def test_page_url_fallback_to_url_field():
    page = {"url": "https://myorg.atlassian.net/wiki/page/42"}
    with patch("agents.confluence_agent.settings") as mock_settings:
        mock_settings.confluence_url = "https://myorg.atlassian.net/wiki"
        url = _page_url(page)
    assert url == "https://myorg.atlassian.net/wiki/page/42"


def test_page_url_empty_when_no_links():
    page = {}
    with patch("agents.confluence_agent.settings") as mock_settings:
        mock_settings.confluence_url = "https://myorg.atlassian.net/wiki"
        url = _page_url(page)
    assert url == ""


# ── _format_pages_for_prompt ─────────────────────────────────────────────────


def test_format_pages_for_prompt_empty():
    result = _format_pages_for_prompt([])
    assert "(no Confluence pages retrieved)" in result


def test_format_pages_for_prompt_with_pages():
    pages = [
        {
            "title": "API Architecture",
            "space": {"key": "ENG"},
            "_links": {},
            "_fetched_content": "This page describes the REST API design.",
        }
    ]
    with patch("agents.confluence_agent.settings") as mock_settings:
        mock_settings.confluence_url = "https://org.atlassian.net/wiki"
        result = _format_pages_for_prompt(pages)
    assert "API Architecture" in result
    assert "REST API design" in result


# ── ConfluenceAgent.run ──────────────────────────────────────────────────────


def _make_state(ticket_context=None, confluence_url="https://org.atlassian.net/wiki"):
    return {
        "run_id": "test-run-id",
        "ticket_id": "PROJ-42",
        "ticket_context": ticket_context,
        "total_llm_calls": 0,
    }


def _make_ticket():
    ticket = MagicMock()
    ticket.title = "Add OAuth2 login support"
    ticket.description = "Users need to authenticate via OAuth2 provider"
    return ticket


def test_confluence_agent_skips_when_not_configured():
    """Agent returns empty context and advances to PLANNING when CONFLUENCE_URL is blank."""
    agent = ConfluenceAgent()
    state = _make_state(ticket_context=_make_ticket())

    with patch("agents.confluence_agent.settings") as mock_settings:
        mock_settings.confluence_url = ""
        mock_settings.confluence_space_keys_list = []
        mock_settings.confluence_max_pages = 10

        result = agent.run(state)

    assert result["current_phase"] == WorkflowPhase.PLANNING
    ctx = result["confluence_context"]
    assert isinstance(ctx, ConfluenceContext)
    assert "not configured" in ctx.summary.lower()


def test_confluence_agent_fails_when_no_ticket_context():
    """Agent returns FAILED when ticket_context is absent."""
    agent = ConfluenceAgent()
    state = _make_state(ticket_context=None)

    with patch("agents.confluence_agent.settings") as mock_settings:
        mock_settings.confluence_url = "https://org.atlassian.net/wiki"

        result = agent.run(state)

    assert result["current_phase"] == WorkflowPhase.FAILED
    assert result["should_stop"] is True
    assert any("ticket_context is None" in e for e in result["errors"])


def test_confluence_agent_happy_path():
    """Agent retrieves pages, calls LLM, and returns populated ConfluenceContext."""
    agent = ConfluenceAgent()
    state = _make_state(ticket_context=_make_ticket())

    expected_context = ConfluenceContext(
        pages_found=[
            ConfluencePage(
                page_id="111",
                title="OAuth2 Setup Guide",
                url="https://org.atlassian.net/wiki/pages/111",
                space_key="ENG",
                content_excerpt="OAuth2 flows are described here.",
                relevance_reason="Directly covers OAuth2 integration",
            )
        ],
        summary="The engineering space has an OAuth2 Setup Guide.",
        doc_update_suggestions=["OAuth2 Setup Guide — add new provider details"],
    )

    mock_pages = [
        {
            "id": "111",
            "title": "OAuth2 Setup Guide",
            "space": {"key": "ENG"},
            "_links": {"webui": "/pages/111"},
            "_fetched_content": "OAuth2 flows are described here.",
        }
    ]

    with (
        patch("agents.confluence_agent.settings") as mock_settings,
        patch(
            "agents.confluence_agent._gather_confluence_data",
            return_value=(mock_pages, ["oauth2", "login"], 5),
        ),
        patch.object(agent, "invoke_llm_structured", return_value=(expected_context, "call-1")),
    ):
        mock_settings.confluence_url = "https://org.atlassian.net/wiki"
        mock_settings.confluence_space_keys_list = ["ENG"]
        mock_settings.confluence_max_pages = 10

        result = agent.run(state)

    assert result["current_phase"] == WorkflowPhase.PLANNING
    ctx = result["confluence_context"]
    assert isinstance(ctx, ConfluenceContext)
    assert len(ctx.pages_found) == 1
    assert ctx.pages_found[0].title == "OAuth2 Setup Guide"
    assert result["total_llm_calls"] == 1
    assert "call-1" in result["llm_call_ids"]


def test_confluence_agent_handles_llm_exception():
    """Agent returns FAILED state when LLM raises an exception."""
    agent = ConfluenceAgent()
    state = _make_state(ticket_context=_make_ticket())

    with (
        patch("agents.confluence_agent.settings") as mock_settings,
        patch(
            "agents.confluence_agent._gather_confluence_data",
            return_value=([], ["oauth2"], 0),
        ),
        patch.object(
            agent, "invoke_llm_structured", side_effect=RuntimeError("LLM timeout")
        ),
    ):
        mock_settings.confluence_url = "https://org.atlassian.net/wiki"
        mock_settings.confluence_space_keys_list = ["ENG"]
        mock_settings.confluence_max_pages = 10

        result = agent.run(state)

    assert result["current_phase"] == WorkflowPhase.FAILED
    assert result["should_stop"] is True
    assert any("LLM timeout" in e for e in result["errors"])
