from abc import ABC, abstractmethod

from pydantic import BaseModel


class StoredObject(BaseModel):
    id: str | None = None
    content: bytes
    content_type: str | None = None
    kb_size: int | None = None


class StorageService(ABC):
    @abstractmethod
    def store(
        self,
        document: StoredObject,
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    def remove(
        self,
        id: str
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def load(
        self,
        id: str
    ) -> StoredObject:
        raise NotImplementedError


class AsyncStorageService(ABC):
    @abstractmethod
    async def store(
        self,
        document: StoredObject,
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    async def remove(
        self,
        id: str,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def load(
        self,
        id: str
    ) -> StoredObject:
        raise NotImplementedError
