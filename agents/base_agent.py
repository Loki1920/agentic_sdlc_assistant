from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from llm.bedrock_client import get_llm
from llm.llm_logger import LLMCallRecord, llm_logger
from app_logging.activity_logger import ActivityLogger
from schemas.workflow_state import WorkflowState


class BaseAgent(ABC):
    """
    Abstract base class for all SDLC workflow agents.

    Provides:
    - Standardised LLM invocation via invoke_llm_structured()
    - Full LLM call logging (every call captured via llm_logger)
    - Activity event logging
    - Async-to-sync bridge for MCP calls inside synchronous LangGraph nodes
    """

    def __init__(self) -> None:
        self.agent_name = self.__class__.__name__
        self.logger = ActivityLogger(self.agent_name)
        self._llm: Optional[BaseChatModel] = None

    # ── LLM ──────────────────────────────────────────────────────────────────

    @property
    def llm(self) -> BaseChatModel:
        if self._llm is None:
            self._llm = get_llm()
        return self._llm

    def invoke_llm_structured(
        self,
        system_prompt: str,
        human_prompt: str,
        output_schema: type,
        run_id: str,
        ticket_id: str,
        prompt_template_name: str,
    ) -> tuple[Any, str]:
        """
        Invoke LLM with structured output (Pydantic schema via with_structured_output).
        Returns (parsed_result, call_id).

        Every invocation is logged to logs/llm_calls.jsonl and SQLite.
        """
        llm_structured = self.llm.with_structured_output(output_schema, include_raw=False)

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt),
        ]

        parsed_output, record = llm_logger.invoke_and_log(
            llm=llm_structured,
            messages=messages,
            run_id=run_id,
            ticket_id=ticket_id,
            agent_name=self.agent_name,
            prompt_template_name=prompt_template_name,
            output_schema_name=output_schema.__name__,
        )

        self.logger.info(
            "llm_call_completed",
            ticket_id=ticket_id,
            run_id=run_id,
            call_id=record.call_id,
            latency_ms=round(record.latency_ms, 1),
            tokens=record.total_token_count,
            parsed_ok=record.parsed_successfully,
        )

        return parsed_output, record.call_id

    # ── Async bridge ──────────────────────────────────────────────────────────

    def run_async(self, coro) -> Any:
        """
        Run an async coroutine from a synchronous LangGraph node.
        Handles nested event loops (e.g. Jupyter / some test runners).
        """
        try:
            asyncio.get_running_loop()
            # Already inside a running event loop — delegate to a new thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        except RuntimeError:
            # No running event loop — safe to use asyncio.run()
            return asyncio.run(coro)

    # ── Abstract interface ────────────────────────────────────────────────────

    @abstractmethod
    def run(self, state: WorkflowState) -> dict:
        """
        Execute agent logic.
        Returns a partial WorkflowState dict to be merged by LangGraph.
        """
        ...
