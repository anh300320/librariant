from typing import Any

from pydantic import BaseModel

DOCUMENT_UPLOAD_EVENT = "document.upload"


class Event(BaseModel):
    id: int
    event_type: str
    payload: dict[str, Any]
