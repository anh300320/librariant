from fastapi import Request
from fastapi.params import Depends

from app.service.document import DocumentService
from app.service.search.base import AsyncSearchService
from app.service.storage.base import AsyncStorageService


def get_storage_service(request: Request) -> AsyncStorageService:
    return request.state.storage_service


def get_search_service(request: Request) -> AsyncSearchService:
    return request.state.search_service


async def get_document_service(
    storage_service: AsyncStorageService = Depends(get_storage_service),
) -> DocumentService:
        return DocumentService(storage_service=storage_service)
