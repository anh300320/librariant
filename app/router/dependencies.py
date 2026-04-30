from app.service.search.model import SearchQuery
from app.service.storage.base import StorageService
from fastapi import Request


def get_storage_service(request: Request) -> StorageService:
    return request.state.storage_service


def get_search_service(request: Request) -> SearchQuery:
    return request.state.search_service
