import asyncio
from abc import ABC, abstractmethod

from app.models.candidate import Candidate


class BaseExtractor(ABC):
    @abstractmethod
    def extract(self, text: str) -> Candidate:
        raise NotImplementedError

    async def aextract(self, text: str) -> Candidate:
        """Async variant. Defaults to running `extract` in a thread; override for native async."""
        return await asyncio.to_thread(self.extract, text)
