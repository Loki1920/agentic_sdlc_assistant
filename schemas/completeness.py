from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class CompletenessDecision(str, Enum):
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"


class MissingField(BaseModel):
    field_name: str
    severity: str = Field(..., description="critical | major | minor")
    description: str


class CompletenessResult(BaseModel):
    ticket_id: str
    decision: CompletenessDecision
    completeness_score: float = Field(..., ge=0.0, le=1.0)
    missing_fields: list[MissingField] = Field(default_factory=list)
    clarification_questions: list[str] = Field(default_factory=list)
    assumptions_summary: Optional[str] = None
    jira_comment_posted: bool = False
    jira_comment_id: Optional[str] = None
    raw_llm_response: Optional[str] = Field(
        default=None,
        description="Raw LLM output before parsing, stored for audit",
    )
