from __future__ import annotations

import asyncio
import re
from typing import Optional

from agents.base_agent import BaseAgent
from app_logging.activity_logger import ActivityLogger
from config.settings import settings
from mcp_client.client_factory import filter_confluence_tools, get_mcp_client
from prompts.confluence_prompt import CONFLUENCE_HUMAN_TEMPLATE, CONFLUENCE_SYSTEM
from schemas.confluence import ConfluenceContext, ConfluencePage
from schemas.workflow_state import WorkflowPhase, WorkflowState

logger = ActivityLogger("confluence_agent")


# ── MCP helper functions ──────────────────────────────────────────────────────


async def _search_confluence(tools: list, space_keys: list[str], query: str) -> list[dict]:
    """Search Confluence for pages matching the query."""
    search_tool = next(
        (t for t in tools if "confluence_search" in t.name.lower() or "search" in t.name.lower()),
        None,
    )
    if search_tool is None:
        return []

    try:
        params: dict = {"query": query, "limit": 10}
        if space_keys:
            params["space_key"] = space_keys[0]
        result = await search_tool.ainvoke(params)
        if isinstance(result, dict):
            return result.get("results", [])
        if isinstance(result, list):
            return result
        return []
    except Exception as exc:
        logger.warning("confluence_search_failed", query=query, error=str(exc))
        return []


async def _get_page_content(tools: list, page_id: str) -> str:
    """Fetch the full content of a Confluence page by ID."""
    get_tool = next(
        (
            t
            for t in tools
            if "confluence_get_page" in t.name.lower()
            or ("get_page" in t.name.lower() and "confluence" in t.name.lower())
            or ("page" in t.name.lower() and "get" in t.name.lower())
        ),
        None,
    )
    if get_tool is None:
        return ""

    try:
        result = await get_tool.ainvoke({"page_id": page_id})
        if isinstance(result, dict):
            # mcp-atlassian returns body.storage.value for Confluence pages
            body = result.get("body", {})
            if isinstance(body, dict):
                storage = body.get("storage", {})
                if isinstance(storage, dict):
                    return storage.get("value", "")[:2000]
            # Fallback: try direct content field
            return str(result.get("content", result.get("body", "")))[:2000]
        return str(result)[:2000]
    except Exception as exc:
        logger.warning("confluence_get_page_failed", page_id=page_id, error=str(exc))
        return ""


def _extract_keywords(ticket_context) -> list[str]:
    """Extract search keywords from ticket title and description."""
    text = f"{ticket_context.title} {ticket_context.description or ''}"
    words = re.findall(r"\b[a-zA-Z][a-zA-Z_]{3,}\b", text)
    stopwords = {
        "should", "will", "need", "must", "want", "have", "been", "with",
        "from", "that", "this", "when", "user", "users", "able", "into",
        "also", "some", "more", "than", "then", "they", "them", "their",
    }
    keywords: list[str] = []
    seen: set[str] = set()
    for word in words:
        lower = word.lower()
        if lower not in stopwords and lower not in seen:
            seen.add(lower)
            keywords.append(lower)
        if len(keywords) >= 5:
            break
    return keywords


def _page_url(page: dict) -> str:
    """Extract the page URL from an mcp-atlassian search result."""
    links = page.get("_links", {})
    if links.get("webui"):
        base = settings.confluence_url.rstrip("/")
        return f"{base}{links['webui']}"
    return page.get("url", page.get("self", ""))


async def _gather_confluence_data(
    ticket_context,
    space_keys: list[str],
    max_pages: int,
) -> tuple[list[dict], list[str], int]:
    """
    Search Confluence and retrieve page content.

    Returns:
        pages_with_content: list of dicts with page metadata + content
        queries_used: list of search query strings
        total_searched: total number of raw search hits examined
    """
    if not settings.confluence_url:
        return [], [], 0

    keywords = _extract_keywords(ticket_context)
    queries = keywords[:3]

    async with get_mcp_client() as client:
        all_tools = await client.get_tools()
        cf_tools = filter_confluence_tools(all_tools)

        if not cf_tools:
            logger.warning("no_confluence_tools_available")
            return [], queries, 0

        # Run searches in parallel
        search_tasks = [
            asyncio.create_task(_search_confluence(cf_tools, space_keys, q))
            for q in queries
        ]
        search_results: list[dict] = []
        for task in search_tasks:
            search_results.extend(await task)

        total_searched = len(search_results)

        # De-duplicate by page ID and limit
        seen_ids: set[str] = set()
        unique_pages: list[dict] = []
        for page in search_results:
            pid = str(page.get("id", page.get("page_id", "")))
            if pid and pid not in seen_ids:
                seen_ids.add(pid)
                unique_pages.append(page)
            if len(unique_pages) >= max_pages:
                break

        # Fetch full content for each unique page
        content_tasks = [
            asyncio.create_task(
                _get_page_content(
                    cf_tools,
                    str(page.get("id", page.get("page_id", ""))),
                )
            )
            for page in unique_pages
        ]
        pages_with_content = []
        for page, content_task in zip(unique_pages, content_tasks):
            content = await content_task
            pages_with_content.append({**page, "_fetched_content": content})

    return pages_with_content, queries, total_searched


def _format_pages_for_prompt(pages_with_content: list[dict]) -> str:
    """Format pages into a readable block for the LLM prompt."""
    if not pages_with_content:
        return "(no Confluence pages retrieved)"

    parts = []
    for i, page in enumerate(pages_with_content, start=1):
        title = page.get("title", "Untitled")
        space = page.get("space", {})
        space_key = space.get("key", "") if isinstance(space, dict) else str(space)
        url = _page_url(page)
        content = page.get("_fetched_content", "")
        parts.append(
            f"### Page {i}: {title}\n"
            f"Space: {space_key} | URL: {url}\n\n"
            f"{content or '(content unavailable)'}"
        )
    return "\n\n---\n\n".join(parts)


# ── Agent class ───────────────────────────────────────────────────────────────


class ConfluenceAgent(BaseAgent):
    def run(self, state: WorkflowState) -> dict:
        ticket_context = state.get("ticket_context")
        run_id = state["run_id"]
        ticket_id = state["ticket_id"]

        self.logger.info(
            "agent_node_entered",
            ticket_id=ticket_id,
            run_id=run_id,
            phase=WorkflowPhase.FETCHING_CONFLUENCE_DOCS,
        )

        if ticket_context is None:
            return {
                "current_phase": WorkflowPhase.FAILED,
                "errors": ["confluence_agent: ticket_context is None"],
                "should_stop": True,
            }

        # If Confluence is not configured, return an empty context and continue
        if not settings.confluence_url:
            self.logger.info(
                "confluence_skipped_not_configured",
                ticket_id=ticket_id,
                run_id=run_id,
            )
            return {
                "confluence_context": ConfluenceContext(
                    summary="Confluence not configured — no documentation context retrieved.",
                ),
                "current_phase": WorkflowPhase.PLANNING,
            }

        try:
            space_keys = settings.confluence_space_keys_list
            max_pages = settings.confluence_max_pages

            pages_with_content, queries_used, total_searched = self.run_async(
                _gather_confluence_data(ticket_context, space_keys, max_pages)
            )

            pages_content_text = _format_pages_for_prompt(pages_with_content)

            human_prompt = CONFLUENCE_HUMAN_TEMPLATE.format(
                ticket_id=ticket_id,
                title=ticket_context.title,
                description=ticket_context.description or "(empty)",
                space_keys=", ".join(space_keys) or "(all spaces)",
                total_pages=total_searched,
                pages_content=pages_content_text,
            )

            result, call_id = self.invoke_llm_structured(
                system_prompt=CONFLUENCE_SYSTEM,
                human_prompt=human_prompt,
                output_schema=ConfluenceContext,
                run_id=run_id,
                ticket_id=ticket_id,
                prompt_template_name="confluence_context_analysis",
            )

            if result is None:
                raise ValueError("LLM returned None for ConfluenceContext")

            # Backfill metadata the LLM cannot know
            result.total_pages_searched = total_searched
            result.search_queries_used = queries_used

            self.logger.info(
                "confluence_docs_retrieved",
                ticket_id=ticket_id,
                run_id=run_id,
                pages_found=len(result.pages_found),
                total_searched=total_searched,
                doc_update_suggestions=len(result.doc_update_suggestions),
            )

            return {
                "confluence_context": result,
                "current_phase": WorkflowPhase.PLANNING,
                "llm_call_ids": [call_id],
                "total_llm_calls": state.get("total_llm_calls", 0) + 1,
                "mcp_tool_calls": [
                    {
                        "tool": "confluence_search",
                        "queries": queries_used,
                        "pages_retrieved": len(pages_with_content),
                    }
                ],
            }

        except Exception as exc:
            self.logger.error(
                "agent_node_failed", exc=exc, ticket_id=ticket_id, run_id=run_id
            )
            return {
                "current_phase": WorkflowPhase.FAILED,
                "errors": [f"confluence_agent: {exc}"],
                "should_stop": True,
            }


_agent = ConfluenceAgent()


def confluence_agent_node(state: WorkflowState) -> dict:
    return _agent.run(state)
