from __future__ import annotations

from tenacity import retry, stop_after_attempt, wait_exponential

# ── LLM retry config ──────────────────────────────────────────────────────────
# Retries up to 3 times with exponential back-off (2 s → 4 s → 8 s … max 30 s).
# All exceptions are retried (covers throttling, transient network errors, etc.).
# The last exception is re-raised after all attempts are exhausted.
_llm_retry = retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
)


def with_llm_retry(fn):
    """Decorator: wrap a callable with LLM retry policy."""
    return _llm_retry(fn)


# ── MCP / tool ainvoke retry helper ──────────────────────────────────────────

_mcp_retry = retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=15),
)


@_mcp_retry
async def ainvoke_with_retry(tool, params: dict):
    """
    Async wrapper that calls ``tool.ainvoke(params)`` with up to 3 retry
    attempts and exponential back-off.  Re-raises the last exception if all
    attempts fail.
    """
    return await tool.ainvoke(params)
