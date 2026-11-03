from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

ActivityType = Literal[
    "repost_created",
    "repost_updated",
    "repost_deleted",
    "queue_item_added",
    "queue_item_removed",
]


class ActivityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    activity_type: ActivityType
    entity_type: str
    entity_id: UUID | None
    description: str
    created_at: datetime


class ActivityList(BaseModel):
    items: list[ActivityResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
