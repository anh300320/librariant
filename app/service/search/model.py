from datetime import datetime

from pydantic import BaseModel

from app.models.candidate import Candidate


class SearchQuery(BaseModel):
    raw_query: str


class SearchDocument(BaseModel):
    doc_id: str
    filename: str
    text: str
    tags: list[str]
    organization: str
    created_at: datetime
    candidate: Candidate | None = None
