from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from pydantic import BaseModel, Field

from config.settings import settings
from app_logging.activity_logger import ActivityLogger

_activity = ActivityLogger("llm_logger")


class LLMCallRecord(BaseModel):
    """Pydantic schema for a single LLM invocation log entry."""

    call_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str
    ticket_id: str
    agent_name: str

    # Request
    model_id: str
    prompt_template_name: str
    system_prompt: Optional[str] = None
    human_prompt: str
    prompt_token_count: Optional[int] = None

    # Response
    raw_response: str = ""
    parsed_successfully: bool = False
    parse_error: Optional[str] = None
    completion_token_count: Optional[int] = None
    total_token_count: Optional[int] = None

    # Performance
    latency_ms: float = 0.0
    invoked_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    # LLM metadata
    stop_reason: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None

    # Structured output
    output_schema_name: Optional[str] = None
    structured_output: Optional[dict] = None

    # Error
    error_occurred: bool = False
    error_type: Optional[str] = None
    error_message: Optional[str] = None


class LLMLogger:
    """
    Logs every LLM invocation to JSONL file and SQLite.
    Usage:
        result, record = llm_logger.invoke_and_log(llm, messages, ...)
    """

    def __init__(self) -> None:
        self._log_path = Path(settings.llm_log_path)
        self._log_path.parent.mkdir(parents=True, exist_ok=True)

    # ── Core log method ───────────────────────────────────────────────────────

    def log_call(self, record: LLMCallRecord) -> str:
        """Write record to JSONL file and SQLite. Returns call_id."""
        # File
        with open(self._log_path, "a", encoding="utf-8") as f:
            f.write(record.model_dump_json() + "\n")

        # SQLite (best-effort — don't crash the workflow on DB failure)
        try:
            from persistence.repository import TicketRepository
            TicketRepository().save_llm_call(record)
        except Exception as exc:
            _activity.warning(
                "llm_log_db_write_failed",
                call_id=record.call_id,
                error_message=str(exc),
            )

        return record.call_id

    # ── Convenience wrapper used by all agents ────────────────────────────────

    def invoke_and_log(
        self,
        llm: Any,
        messages: list,
        run_id: str,
        ticket_id: str,
        agent_name: str,
        prompt_template_name: str,
        output_schema_name: Optional[str] = None,
        parse_fn: Optional[Callable] = None,
    ) -> tuple[Any, LLMCallRecord]:
        """
        Invoke the LLM, capture all metadata, log the result.
        Returns (parsed_output_or_raw_response, record).
        """
        start = time.monotonic()
        error_occurred = False
        error_type: Optional[str] = None
        error_message: Optional[str] = None
        raw_response = ""
        parsed_output: Any = None
        parsed_successfully = False
        parse_error: Optional[str] = None
        stop_reason: Optional[str] = None
        prompt_tokens: Optional[int] = None
        completion_tokens: Optional[int] = None
        total_tokens: Optional[int] = None

        try:
            response = llm.invoke(messages)
            latency_ms = (time.monotonic() - start) * 1000

            raw_response = (
                str(response.content)
                if hasattr(response, "content")
                else str(response)
            )

            # Token counts
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                prompt_tokens = response.usage_metadata.get("input_tokens")
                completion_tokens = response.usage_metadata.get("output_tokens")
                total_tokens = response.usage_metadata.get("total_tokens")

            if hasattr(response, "response_metadata") and response.response_metadata:
                stop_reason = response.response_metadata.get("stop_reason")

            # Parse
            if parse_fn:
                try:
                    parsed_output = parse_fn(response)
                    parsed_successfully = True
                except Exception as pe:
                    parse_error = str(pe)
                    parsed_successfully = False
            else:
                parsed_output = response
                parsed_successfully = True

        except Exception as exc:
            latency_ms = (time.monotonic() - start) * 1000
            error_occurred = True
            error_type = type(exc).__name__
            error_message = str(exc)

        # Resolve human prompt text
        human_prompt_text = ""
        system_prompt_text = None
        if messages:
            from langchain_core.messages import HumanMessage, SystemMessage
            for m in messages:
                if isinstance(m, HumanMessage):
                    human_prompt_text = str(m.content)
                elif isinstance(m, SystemMessage):
                    system_prompt_text = str(m.content)

        record = LLMCallRecord(
            run_id=run_id,
            ticket_id=ticket_id,
            agent_name=agent_name,
            model_id=settings.bedrock_model_id,
            prompt_template_name=prompt_template_name,
            system_prompt=system_prompt_text,
            human_prompt=human_prompt_text,
            raw_response=raw_response,
            parsed_successfully=parsed_successfully,
            parse_error=parse_error,
            prompt_token_count=prompt_tokens,
            completion_token_count=completion_tokens,
            total_token_count=total_tokens,
            latency_ms=latency_ms,
            stop_reason=stop_reason,
            temperature=settings.bedrock_temperature,
            max_tokens=settings.bedrock_max_tokens,
            output_schema_name=output_schema_name,
            structured_output=(
                parsed_output.model_dump(mode="json")
                if parsed_output and hasattr(parsed_output, "model_dump")
                else None
            ),
            error_occurred=error_occurred,
            error_type=error_type,
            error_message=error_message,
        )

        self.log_call(record)
        return parsed_output, record


# Module-level singleton
llm_logger = LLMLogger()
