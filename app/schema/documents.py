from pydantic import BaseModel


class DocumentUploadRequest(BaseModel):
    path: str
