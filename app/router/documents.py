from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.params import Depends, Form

from app.models.document import Document
from app.router.dependencies import get_document_service
from app.schema.base import BaseResponse
from app.schema.document import DocumentUploadRequest
from app.service.document import DocumentService

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_document(
    document_service: DocumentService = Depends(get_document_service),
    file: UploadFile = File(...),
    metadata: str = Form(...)
) -> BaseResponse:

    upload_request = DocumentUploadRequest.model_validate_json(metadata)
    try:
        raw_content = await file.read()
    finally:
        await file.close()
    if not raw_content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    document = Document(
        name=file.filename,
        path=Path(upload_request.path),
        content_type=file.content_type,
        raw_content=raw_content,
        kb_size=file.size // 1024,
    )
    document = await document_service.add_document(document, upload_request.path)
    return BaseResponse(
        status="200",
        message="Upload document successfully",
        data={
            "id": document.id,
            "name": document.name,
        }
    )
