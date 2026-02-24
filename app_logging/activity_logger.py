from __future__ import annotations

import json
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from config.settings import settings


class ActivityLogger:
    """
    Structured activity logger. Writes JSON lines to file and stderr.
    Thread-safe via a module-level write lock.

    Each log record schema:
    {
        "timestamp": "2025-01-01T00:00:00+00:00",
        "level":     "INFO",
        "event":     "workflow_started",
        "agent":     "supervisor",
        "ticket_id": "PROJ-123",  (optional)
        "run_id":    "uuid",      (optional)
        "message":   "...",
        ...extra_fields
    }
    """

    _lock = threading.Lock()

    def __init__(self, agent_name: str) -> None:
        self.agent_name = agent_name
        self._log_path = Path(settings.activity_log_path)
        self._log_path.parent.mkdir(parents=True, exist_ok=True)

    def _write(
        self,
        level: str,
        event: str,
        ticket_id: Optional[str] = None,
        run_id: Optional[str] = None,
        message: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        record: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "event": event,
            "agent": self.agent_name,
        }
        if ticket_id:
            record["ticket_id"] = ticket_id
        if run_id:
            record["run_id"] = run_id
        record["message"] = message or event
        record.update(kwargs)

        line = json.dumps(record, default=str)

        with self._lock:
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(line + "\n")

        # Also emit to stderr so Docker log drivers collect it
        print(line, file=sys.stderr, flush=True)

    # ── Public interface ──────────────────────────────────────────────────────

    def info(self, event: str, **kwargs: Any) -> None:
        self._write("INFO", event, **kwargs)

    def warning(self, event: str, **kwargs: Any) -> None:
        self._write("WARNING", event, **kwargs)

    def error(
        self,
        event: str,
        exc: Optional[Exception] = None,
        **kwargs: Any,
    ) -> None:
        if exc:
            kwargs.setdefault("error_type", type(exc).__name__)
            kwargs.setdefault("error_message", str(exc))
        self._write("ERROR", event, **kwargs)

    def debug(self, event: str, **kwargs: Any) -> None:
        if settings.log_level.upper() == "DEBUG":
            self._write("DEBUG", event, **kwargs)
