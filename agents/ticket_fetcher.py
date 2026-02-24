from __future__ import annotations

import asyncio
import json
from typing import Any

from agents.base_agent import BaseAgent
from app_logging.activity_logger import ActivityLogger
from mcp_client.client_factory import filter_jira_tools, get_mcp_client
from schemas.ticket import TicketContext
from schemas.workflow_state import WorkflowPhase, WorkflowState

logger = ActivityLogger("ticket_fetcher")


def _unwrap_tool_result(result: Any) -> dict:
    """Extract a parsed dict from a LangChain MCP tool ainvoke result.

    Tools with response_format='content_and_artifact' return a list of
    content blocks: [{"type": "text", "text": "<json string>"}, ...].
    This helper collapses them into a single parsed dict.
    """
    # Unpack (content, artifact) tuple if present
    if isinstance(result, tuple):
        result = result[0]

    if isinstance(result, dict):
        return result

    if isinstance(result, list):
        text_parts = []
        for block in result:
            if isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(block.get("text", ""))
            elif hasattr(block, "text"):
                text_parts.append(block.text)
        text = "\n".join(text_parts)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"description": text}

    if isinstance(result, str):
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return {"description": result}

    return result


async def _fetch_ticket_via_mcp(ticket_id: str) -> dict:
    """Use the Jira MCP to fetch a single issue."""
    async with get_mcp_client() as client:
        all_tools = await client.get_tools()
        jira_tools = filter_jira_tools(all_tools)

        # Find the get_issue or get_jira_issue tool
        get_issue_tool = next(
            (t for t in jira_tools if "get_issue" in t.name.lower() or "get_jira" in t.name.lower()),
            None,
        )
        if get_issue_tool is None:
            # Fallback: try any search tool with exact issue key
            search_tool = next(
                (t for t in jira_tools if "search" in t.name.lower()),
                None,
            )
            if search_tool is None:
                raise RuntimeError(
                    f"No suitable Jira MCP tool found. Available: {[t.name for t in jira_tools]}"
                )
            result = await search_tool.ainvoke({"jql": f'issue = "{ticket_id}"', "max_results": 1})
            issues = _unwrap_tool_result(result).get("issues", [])
            if not issues:
                raise ValueError(f"Ticket {ticket_id} not found via JQL search")
            return issues[0]

        result = await get_issue_tool.ainvoke({"issue_key": ticket_id})
        return _unwrap_tool_result(result)


def _parse_jira_response(data: dict, ticket_id: str) -> TicketContext:
    """Convert raw Jira MCP response dict to TicketContext."""
    fields = data.get("fields", data)  # mcp-atlassian may return fields directly

    description = fields.get("description", "") or ""
    # Jira description can be Atlassian Document Format (ADF) or plain text
    if isinstance(description, dict):
        description = _flatten_adf(description)

    # Acceptance criteria may be stored in a custom field or extracted from description
    ac = fields.get("acceptance_criteria") or fields.get("customfield_10016") or ""
    if isinstance(ac, dict):
        ac = _flatten_adf(ac)

    labels = fields.get("labels", []) or []
    components = [c.get("name", "") for c in (fields.get("components") or [])]
    linked = [
        link.get("inwardIssue", {}).get("key", "") or link.get("outwardIssue", {}).get("key", "")
        for link in (fields.get("issuelinks") or [])
    ]

    priority_obj = fields.get("priority") or {}
    assignee_obj = fields.get("assignee") or {}
    reporter_obj = fields.get("reporter") or {}

    return TicketContext(
        ticket_id=ticket_id,
        title=fields.get("summary", ""),
        description=description,
        acceptance_criteria=ac or None,
        labels=labels,
        priority=priority_obj.get("name") if isinstance(priority_obj, dict) else str(priority_obj),
        story_points=fields.get("story_points") or fields.get("customfield_10028"),
        reporter=reporter_obj.get("displayName") if isinstance(reporter_obj, dict) else None,
        assignee=assignee_obj.get("displayName") if isinstance(assignee_obj, dict) else None,
        status=str(fields.get("status", {}).get("name", "")) if isinstance(fields.get("status"), dict) else "",
        components=components,
        linked_issues=[k for k in linked if k],
        raw_jira_data=data,
    )


def _flatten_adf(adf: Any) -> str:
    """Recursively extract plain text from Atlassian Document Format."""
    if isinstance(adf, str):
        return adf
    if isinstance(adf, dict):
        texts = []
        if adf.get("type") == "text":
            texts.append(adf.get("text", ""))
        for child in adf.get("content", []):
            texts.append(_flatten_adf(child))
        return " ".join(t for t in texts if t).strip()
    if isinstance(adf, list):
        return " ".join(_flatten_adf(item) for item in adf)
    return str(adf)


class TicketFetcherAgent(BaseAgent):
    def run(self, state: WorkflowState) -> dict:
        ticket_id = state["ticket_id"]
        run_id = state["run_id"]

        self.logger.info(
            "agent_node_entered",
            ticket_id=ticket_id,
            run_id=run_id,
            phase=WorkflowPhase.FETCHING_TICKET,
        )

        try:
            raw_data = self.run_async(_fetch_ticket_via_mcp(ticket_id))
            ticket_context = _parse_jira_response(raw_data, ticket_id)

            self.logger.info(
                "jira_ticket_fetched",
                ticket_id=ticket_id,
                run_id=run_id,
                title=ticket_context.title,
            )

            return {
                "ticket_context": ticket_context,
                "current_phase": WorkflowPhase.CHECKING_COMPLETENESS,
                "mcp_tool_calls": [{"tool": "jira_get_issue", "ticket_id": ticket_id}],
            }

        except Exception as exc:
            self.logger.error("agent_node_failed", exc=exc, ticket_id=ticket_id, run_id=run_id)
            return {
                "current_phase": WorkflowPhase.FAILED,
                "errors": [f"ticket_fetcher: {exc}"],
                "should_stop": True,
            }


# ── LangGraph node function ────────────────────────────────────────────────────

_agent = TicketFetcherAgent()


def fetch_ticket_node(state: WorkflowState) -> dict:
    return _agent.run(state)
