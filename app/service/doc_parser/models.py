from pydantic import BaseModel

from app.models.document import Document


class ParsedDocument(BaseModel):
    original: Document | None = None
    content: str
