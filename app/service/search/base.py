from abc import ABC, abstractmethod

from app.service.search.model import SearchDocument, SearchQuery


class SearchService[T](ABC):
    @abstractmethod
    def add(
        self,
        document: SearchDocument,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def search(
        self,
        search: SearchQuery,
    ) -> list[SearchDocument]:
        raise NotImplementedError


class AsyncSearchService[T](ABC):

    @abstractmethod
    async def add(
        self,
        document: SearchDocument,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def search(
            self,
            search: SearchQuery,
    ) -> list[SearchDocument]:
        raise NotImplementedError
