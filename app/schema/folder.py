from datetime import datetime

from pydantic import BaseModel, Field

from app.schema.base import BaseResponse


class FolderAsset(BaseModel):
    id: int
    name: str
    created_at: datetime


class FolderResponse(BaseResponse):
    data: list[FolderAsset] = Field(default_factory=list)
