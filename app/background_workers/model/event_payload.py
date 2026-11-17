from pydantic import BaseModel


class DocumentUploadEventPayload(BaseModel):
    document_id: int
    storage_access_id: str