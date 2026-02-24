from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ConfluencePage(BaseModel):
    """Represents a single Confluence page retrieved during context gathering."""

    page_id: str = Field(description="Confluence page ID")
    title: str = Field(description="Page title")
    url: str = Field(description="Full URL to the Confluence page")
    space_key: str = Field(description="Confluence space key the page belongs to")
    content_excerpt: str = Field(
        description="Relevant excerpt from the page content (up to 2000 characters)"
    )
    relevance_reason: str = Field(
        description="Brief explanation of why this page is relevant to the ticket"
    )


class ConfluenceContext(BaseModel):
    """Aggregated Confluence context retrieved for a ticket."""

    pages_found: list[ConfluencePage] = Field(
        default_factory=list,
        description="Confluence pages retrieved and deemed relevant",
    )
    total_pages_searched: int = Field(
        default=0,
        description="Total number of pages examined during search",
    )
    search_queries_used: list[str] = Field(
        default_factory=list,
        description="Search queries sent to Confluence",
    )
    summary: str = Field(
        default="",
        description=(
            "LLM-synthesised summary of relevant business rules, architecture decisions, "
            "and API contracts found in the documentation"
        ),
    )
    doc_update_suggestions: list[str] = Field(
        default_factory=list,
        description=(
            "Page titles or descriptions of Confluence pages that likely need updating "
            "after the ticket work is completed"
        ),
    )
