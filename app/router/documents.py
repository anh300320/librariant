from elasticsearch import Elasticsearch
from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.params import Depends, Form

from app.router.dependencies import get_storage_service
from app.schema.base import BaseResponse
from app.schema.documents import DocumentUploadRequest
from app.service.storage.base import StoredObject, StorageService, AsyncStorageService

router = APIRouter(prefix="/documents", tags=["documents"])


def _ensure_index_exists(es_client: Elasticsearch, index_name: str) -> None:
    if es_client.indices.exists(index=index_name):
        return

    es_client.indices.create(
        index=index_name,
        mappings={
            "properties": {
                "file_name": {"type": "keyword"},
                "content_type": {"type": "keyword"},
                "size_kb": {"type": "float"},
                "s3_key": {"type": "keyword"},
                "uploaded_at": {"type": "date"},
                "content": {"type": "text"},
            }
        },
    )


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_and_index(
    storage_service: AsyncStorageService = Depends(get_storage_service),
    file: UploadFile = File(...),
    metadata: str = Form(...)
) -> BaseResponse:

    metadata = DocumentUploadRequest.model_validate_strings(metadata)
    try:
        raw_content = await file.read()
    finally:
        await file.close()
    if not raw_content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    document = StoredObject(
        content_type=file.content_type,
        content=raw_content,
        kb_size=file.size // 1024,
    )
    id = await storage_service.store(document)

    return BaseResponse(
        status="200",
        data=f"Upload document successfully, {id=}",
    )
