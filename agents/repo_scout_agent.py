from __future__ import annotations

import asyncio
from typing import Optional

from agents.base_agent import BaseAgent
from config.settings import settings
from app_logging.activity_logger import ActivityLogger
from mcp_client.client_factory import filter_github_tools, get_mcp_client
from prompts.repo_scout_prompt import REPO_SCOUT_HUMAN_TEMPLATE, REPO_SCOUT_SYSTEM
from schemas.repo import FileAnalysis, RepoContext
from schemas.workflow_state import WorkflowPhase, WorkflowState
from utils.mcp_helpers import find_tool
from utils.retry import ainvoke_with_retry
from utils.text_helpers import extract_keywords as _extract_keywords

logger = ActivityLogger("repo_scout_agent")


async def _get_repo_tree(tools: list, owner: str, repo: str) -> str:
    """Fetch top-level directory structure."""
    get_contents = find_tool(tools, "get_file_contents") or find_tool(tools, "contents")
    if get_contents is None:
        return "(directory listing unavailable)"

    try:
        result = await ainvoke_with_retry(get_contents, {"owner": owner, "repo": repo, "path": ""})
        if isinstance(result, list):
            entries = [
                f"{'📁' if item.get('type') == 'dir' else '📄'} {item.get('name', '')}"
                for item in result
            ]
            return "\n".join(entries)
        return str(result)
    except Exception as exc:
        return f"(error fetching tree: {exc})"


async def _get_file_content(tools: list, owner: str, repo: str, path: str) -> str:
    """Fetch contents of a specific file."""
    get_contents = find_tool(tools, "get_file_contents") or find_tool(tools, "contents")
    if get_contents is None:
        return ""
    try:
        result = await ainvoke_with_retry(get_contents, {"owner": owner, "repo": repo, "path": path})
        if isinstance(result, dict):
            import base64
            content = result.get("content", "")
            if result.get("encoding") == "base64":
                content = base64.b64decode(content).decode("utf-8", errors="replace")
            return content[:3000]  # Limit per file to avoid context overflow
        return str(result)[:3000]
    except Exception as exc:
        logger.warning("file_fetch_failed", path=path, error=str(exc))
        return ""


async def _search_code(tools: list, owner: str, repo: str, query: str) -> list[str]:
    """Search for relevant files using keyword search."""
    search_tool = find_tool(tools, "search_code") or find_tool(tools, "search")
    if search_tool is None:
        return []
    try:
        result = await ainvoke_with_retry(search_tool, {"q": f"{query} repo:{owner}/{repo}"})
        items = result.get("items", []) if isinstance(result, dict) else []
        return [item.get("path", "") for item in items[:10]]
    except Exception as exc:
        logger.warning("code_search_failed", query=query, error=str(exc))
        return []


async def _get_dependency_files(tools: list, owner: str, repo: str) -> str:
    """Try to read common dependency files."""
    dep_files = [
        "requirements.txt", "pyproject.toml", "package.json",
        "go.mod", "pom.xml", "build.gradle", "Gemfile",
    ]
    parts = []
    for fname in dep_files:
        content = await _get_file_content(tools, owner, repo, fname)
        if content:
            parts.append(f"### {fname}\n{content[:800]}")
    return "\n\n".join(parts) or "(no dependency files found)"


async def _gather_repo_data(ticket_context, max_files: int) -> tuple[str, str, str, list[str]]:
    """Gather directory tree, dependency files, file listing, and raw mcp outputs."""
    owner = settings.github_repo_owner
    repo = settings.github_repo_name

    async with get_mcp_client() as client:
        all_tools = await client.get_tools()
        gh_tools = filter_github_tools(all_tools)

        # Parallel fetches
        tree_task = asyncio.create_task(_get_repo_tree(gh_tools, owner, repo))
        dep_task = asyncio.create_task(_get_dependency_files(gh_tools, owner, repo))

        # Search for relevant files based on ticket keywords
        keywords = _extract_keywords(ticket_context)
        search_tasks = [
            asyncio.create_task(_search_code(gh_tools, owner, repo, kw))
            for kw in keywords[:3]
        ]

        dir_summary = await tree_task
        dep_content = await dep_task
        search_results = []
        for t in search_tasks:
            search_results.extend(await t)

        # De-duplicate and limit
        relevant_paths = list(dict.fromkeys(p for p in search_results if p))[:max_files]

        # Fetch content for relevant files
        file_listing_parts = []
        for path in relevant_paths:
            content = await _get_file_content(gh_tools, owner, repo, path)
            if content:
                file_listing_parts.append(f"### {path}\n```\n{content}\n```")

        file_listing = "\n\n".join(file_listing_parts) or "(no matching files found)"
        return dir_summary, dep_content, file_listing, relevant_paths



class RepoScoutAgent(BaseAgent):
    def run(self, state: WorkflowState) -> dict:
        ticket_context = state.get("ticket_context")
        run_id = state["run_id"]
        ticket_id = state["ticket_id"]

        self.logger.info(
            "agent_node_entered",
            ticket_id=ticket_id,
            run_id=run_id,
            phase=WorkflowPhase.SCOUTING_REPO,
        )

        if ticket_context is None:
            return {
                "current_phase": WorkflowPhase.FAILED,
                "errors": ["repo_scout: ticket_context is None"],
                "should_stop": True,
            }

        try:
            max_files = settings.repo_scout_max_files
            dir_summary, dep_content, file_listing, relevant_paths = self.run_async(
                _gather_repo_data(ticket_context, max_files)
            )

            human_prompt = REPO_SCOUT_HUMAN_TEMPLATE.format(
                ticket_id=ticket_id,
                title=ticket_context.title,
                description=ticket_context.description or "(empty)",
                repo_owner=settings.github_repo_owner,
                repo_name=settings.github_repo_name,
                directory_summary=dir_summary,
                file_listing=file_listing,
                dependency_content=dep_content,
                max_files=max_files,
            )

            result, call_id = self.invoke_llm_structured(
                system_prompt=REPO_SCOUT_SYSTEM,
                human_prompt=human_prompt,
                output_schema=RepoContext,
                run_id=run_id,
                ticket_id=ticket_id,
                prompt_template_name="repo_scout_analysis",
            )

            if result is None:
                # Repo is likely empty or unrecognised — build a minimal context
                # so the pipeline can still produce a plan and code proposal.
                result = RepoContext(
                    repo_owner=settings.github_repo_owner,
                    repo_name=settings.github_repo_name,
                    directory_summary=dir_summary or "(repository appears empty)",
                    primary_language=None,
                )

            # Fill in metadata that LLM may not know
            result.repo_owner = settings.github_repo_owner
            result.repo_name = settings.github_repo_name
            result.directory_summary = dir_summary

            self.logger.info(
                "github_repo_analyzed",
                ticket_id=ticket_id,
                run_id=run_id,
                relevant_files=len(result.relevant_files),
                impacted_modules=result.impacted_modules,
            )

            return {
                "repo_context": result,
                "current_phase": WorkflowPhase.PLANNING,
                "llm_call_ids": [call_id],
                "total_llm_calls": state.get("total_llm_calls", 0) + 1,
                "mcp_tool_calls": [
                    {"tool": "github_get_contents", "paths": relevant_paths}
                ],
            }

        except Exception as exc:
            self.logger.error("agent_node_failed", exc=exc, ticket_id=ticket_id, run_id=run_id)
            return {
                "current_phase": WorkflowPhase.FAILED,
                "errors": [f"repo_scout: {exc}"],
                "should_stop": True,
            }


_agent = RepoScoutAgent()


def repo_scout_node(state: WorkflowState) -> dict:
    return _agent.run(state)
