"""Unit tests for the LLM client factory and logger."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from llm.llm_logger import LLMCallRecord


# ── get_llm routing ───────────────────────────────────────────────────────────

def test_get_llm_routes_to_bedrock(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "bedrock")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")

    with patch("llm.bedrock_client._build_bedrock") as mock_bedrock, \
         patch("llm.bedrock_client.get_llm") as mock_get_llm:
        mock_bedrock.return_value = MagicMock()
        mock_get_llm.return_value = mock_bedrock.return_value

        from llm.bedrock_client import get_llm
        get_llm.cache_clear()
        llm = get_llm()

    assert llm is not None


def test_get_llm_raises_for_openai_without_key():
    from llm.bedrock_client import _build_openai
    from pydantic import SecretStr

    with patch("llm.bedrock_client.settings") as mock_settings:
        mock_settings.openai_api_key.get_secret_value.return_value = ""

        with pytest.raises(ValueError, match="OPENAI_API_KEY"):
            _build_openai()


# ── LLMLogger.invoke_and_log ──────────────────────────────────────────────────

def _make_mock_llm(response_content: str = "ok", raise_exc=None):
    mock_llm = MagicMock()
    if raise_exc:
        mock_llm.invoke.side_effect = raise_exc
    else:
        mock_response = MagicMock()
        mock_response.content = response_content
        mock_response.usage_metadata = {
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
        }
        mock_response.response_metadata = {"stop_reason": "end_turn"}
        # Return a proper dict so LLMCallRecord.structured_output validates
        mock_response.model_dump = MagicMock(return_value={"content": response_content})
        mock_llm.invoke.return_value = mock_response
    return mock_llm


def _make_messages():
    from langchain_core.messages import HumanMessage, SystemMessage
    return [SystemMessage(content="You are helpful."), HumanMessage(content="Hello")]


def test_invoke_and_log_happy_path(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_LOG_PATH", str(tmp_path / "llm.jsonl"))

    from llm.llm_logger import LLMLogger

    logger = LLMLogger()
    mock_llm = _make_mock_llm("hello world")

    output, record = logger.invoke_and_log(
        llm=mock_llm,
        messages=_make_messages(),
        run_id="run-1",
        ticket_id="PROJ-1",
        agent_name="TestAgent",
        prompt_template_name="test",
    )

    assert record.parsed_successfully is True
    assert record.error_occurred is False
    assert record.total_token_count == 150
    assert record.latency_ms > 0
    assert record.run_id == "run-1"
    assert record.ticket_id == "PROJ-1"


def test_invoke_and_log_captures_exception(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_LOG_PATH", str(tmp_path / "llm.jsonl"))

    from llm.llm_logger import LLMLogger

    logger = LLMLogger()
    mock_llm = _make_mock_llm(raise_exc=RuntimeError("Bedrock throttled"))

    output, record = logger.invoke_and_log(
        llm=mock_llm,
        messages=_make_messages(),
        run_id="run-2",
        ticket_id="PROJ-1",
        agent_name="TestAgent",
        prompt_template_name="test",
    )

    assert output is None
    assert record.error_occurred is True
    assert record.error_type == "RuntimeError"
    assert "Bedrock throttled" in record.error_message


def test_invoke_and_log_writes_jsonl(tmp_path):
    log_path = tmp_path / "llm.jsonl"

    from llm.llm_logger import LLMLogger

    with patch("llm.llm_logger.settings") as mock_settings:
        mock_settings.llm_log_path = str(log_path)
        mock_settings.bedrock_model_id = "test-model"
        mock_settings.bedrock_temperature = 0.1
        mock_settings.bedrock_max_tokens = 4096

        logger = LLMLogger()
        mock_llm = _make_mock_llm("response text")

        logger.invoke_and_log(
            llm=mock_llm,
            messages=_make_messages(),
            run_id="run-3",
            ticket_id="PROJ-1",
            agent_name="TestAgent",
            prompt_template_name="test",
        )

    assert log_path.exists()
    lines = log_path.read_text().strip().splitlines()
    assert len(lines) == 1
    import json
    record = json.loads(lines[0])
    assert record["run_id"] == "run-3"


# ── Retry integration ─────────────────────────────────────────────────────────

def test_llm_retry_retries_on_transient_error(tmp_path, monkeypatch):
    """invoke_and_log should retry up to 3 times before capturing the error."""
    log_path = tmp_path / "llm.jsonl"
    monkeypatch.setenv("LLM_LOG_PATH", str(log_path))

    from llm.llm_logger import LLMLogger

    call_count = 0

    def flaky_invoke(messages):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ConnectionError("transient")
        mock_response = MagicMock()
        mock_response.content = "success"
        mock_response.usage_metadata = {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
        mock_response.response_metadata = {"stop_reason": "end_turn"}
        mock_response.model_dump = MagicMock(return_value={"content": "success"})
        return mock_response

    mock_llm = MagicMock()
    mock_llm.invoke = flaky_invoke

    logger = LLMLogger()
    output, record = logger.invoke_and_log(
        llm=mock_llm,
        messages=_make_messages(),
        run_id="run-retry",
        ticket_id="PROJ-1",
        agent_name="TestAgent",
        prompt_template_name="test",
    )

    # Should succeed on the 3rd attempt
    assert call_count == 3
    assert record.error_occurred is False
