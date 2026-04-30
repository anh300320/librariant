from pathlib import Path

from pydantic import BaseModel


class Document(BaseModel):
    name: str
    content_type: str | None = None
    raw_content: bytes | None = None
    kb_size: int | None = None


class InternalPath(BaseModel):
    bucket: str
    path: Path
