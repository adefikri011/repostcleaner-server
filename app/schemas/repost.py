from datetime import datetime
from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class RepostStatus(StrEnum):
    SAVED = "saved"
    ARCHIVED = "archived"


class RepostCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_platform: str = Field(min_length=1, max_length=40)
    source_id: str | None = Field(default=None, max_length=200)
    title: str | None = Field(default=None, max_length=300)
    description: str | None = Field(default=None, max_length=10_000)
    thumbnail_url: str | None = Field(default=None, max_length=2048)
    original_url: str | None = Field(default=None, max_length=2048)
    creator_username: str | None = Field(default=None, max_length=100)
    creator_display_name: str | None = Field(default=None, max_length=160)
    status: RepostStatus = RepostStatus.SAVED

    @field_validator("source_platform")
    @classmethod
    def normalize_source_platform(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("Source platform must not be empty")
        return normalized

    @field_validator(
        "source_id", "title", "description", "creator_username", "creator_display_name"
    )
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("thumbnail_url", "original_url")
    @classmethod
    def validate_http_url(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        parsed = AnyHttpUrl(value)
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("URLs must not contain credentials")
        return str(parsed)


class RepostUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_platform: str | None = Field(default=None, min_length=1, max_length=40)
    source_id: str | None = Field(default=None, max_length=200)
    title: str | None = Field(default=None, max_length=300)
    description: str | None = Field(default=None, max_length=10_000)
    thumbnail_url: str | None = Field(default=None, max_length=2048)
    original_url: str | None = Field(default=None, max_length=2048)
    creator_username: str | None = Field(default=None, max_length=100)
    creator_display_name: str | None = Field(default=None, max_length=160)
    status: RepostStatus | None = None

    @model_validator(mode="after")
    def require_a_change(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        return self

    @field_validator("source_platform")
    @classmethod
    def normalize_source_platform(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("Source platform must not be empty")
        return normalized

    @field_validator(
        "source_id", "title", "description", "creator_username", "creator_display_name"
    )
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("thumbnail_url", "original_url")
    @classmethod
    def validate_http_url(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        parsed = AnyHttpUrl(value)
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("URLs must not contain credentials")
        return str(parsed)

    @field_validator("source_platform", mode="before")
    @classmethod
    def reject_null_platform(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("Source platform cannot be null")
        return value

    @field_validator("status", mode="before")
    @classmethod
    def reject_null_status(cls, value: RepostStatus | str | None) -> RepostStatus | str:
        if value is None:
            raise ValueError("Status cannot be null")
        return value


class RepostResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_platform: str
    source_id: str | None
    title: str | None
    description: str | None
    thumbnail_url: str | None
    original_url: str | None
    creator_username: str | None
    creator_display_name: str | None
    status: RepostStatus
    created_at: datetime
    updated_at: datetime


class RepostList(BaseModel):
    items: list[RepostResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
