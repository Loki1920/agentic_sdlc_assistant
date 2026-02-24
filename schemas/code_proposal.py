from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ChangeType(str, Enum):
    CREATE = "create"
    MODIFY = "modify"
    DELETE = "delete"
    RENAME = "rename"


class FileDiff(BaseModel):
    file_path: str
    change_type: ChangeType
    original_content_snippet: Optional[str] = Field(
        default=None,
        description="Relevant excerpt from original file",
    )
    proposed_content: str = Field(
        ...,
        description="Full proposed content or unified diff patch",
    )
    is_diff_format: bool = Field(
        default=True,
        description="True if proposed_content is a unified diff, False if full file",
    )
    rationale: str


class CodeProposal(BaseModel):
    ticket_id: str
    summary: str
    file_changes: list[FileDiff] = Field(default_factory=list)
    new_dependencies: list[str] = Field(default_factory=list)
    configuration_changes: list[str] = Field(default_factory=list)
    migration_scripts: list[str] = Field(default_factory=list)
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    caveats: list[str] = Field(default_factory=list)
    raw_llm_response: Optional[str] = None
