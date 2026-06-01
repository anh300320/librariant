from pathlib import Path

from pydantic import BaseModel


class BaseNode(BaseModel):
    id: int = 0
    name: str = ""
    path: Path | None = None


class Document(BaseNode):
    storage_access_id: str = ""
    content_type: str | None = None
    raw_content: bytes | None = None
    kb_size: int | None = None


class Folder(BaseNode):
    pass
