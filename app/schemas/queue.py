from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.repost import RepostResponse


class QueueAddRequest(BaseModel):
    repost_ids: list[UUID] = Field(min_length=1, max_length=100)


class QueueResponse(BaseModel):
    items: list[RepostResponse]
    total: int
