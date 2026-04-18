from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CharacterCardSummary(BaseModel):
    asset_id: UUID
    source_id: UUID
    source_name: str
    filename: str
    relative_path: str
    preview_url: str | None = None
    content_url: str
    name: str
    creator: str | None = None
    description: str | None = None
    spec: str
    spec_version: str
    tags: list[str] = []
    extracted_at: datetime
    updated_at: datetime


class CharacterCardDetail(CharacterCardSummary):
    first_message: str | None = None
    message_examples: str | None = None
    personality: str | None = None
    scenario: str | None = None
    creator_notes: str | None = None
    system_prompt: str | None = None
    post_history_instructions: str | None = None
    character_version: str | None = None
    alternate_greetings: list[str] = []
    group_only_greetings: list[str] = []
    canonical_card: dict


class CharacterCardListResponse(BaseModel):
    items: list[CharacterCardSummary]
    total: int
    page: int
    page_size: int


class CharacterCardUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    description: str | None = None
    personality: str | None = None
    scenario: str | None = None
    first_message: str | None = None
    message_examples: str | None = None
    creator_notes: str | None = None
    system_prompt: str | None = None
    post_history_instructions: str | None = None
    creator: str | None = None
    character_version: str | None = None
    tags: list[str] | None = None
    alternate_greetings: list[str] | None = None
    group_only_greetings: list[str] | None = None
