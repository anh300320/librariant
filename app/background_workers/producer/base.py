import asyncio
import logging
from abc import ABC, abstractmethod
from asyncio import Task

logger = logging.getLogger(__name__)


class AsyncProducer(ABC):

    @abstractmethod
    async def start(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def produce(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        raise NotImplementedError


class AsyncBackgroundWorker:
    def __init__(
        self,
        scan_interval_sec: float,
        producer: AsyncProducer,
    ):
        self._scan_interval_sec = scan_interval_sec
        self._producer = producer
        self._instance: Task | None = None

    async def start(self):
        await self._producer.start()
        self._instance = asyncio.create_task(self._run())

    async def _run(self):
        while True:
            try:
                await self._producer.produce()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Outbox relay iteration failed")
            await asyncio.sleep(self._scan_interval_sec)

    async def stop(self):
        if self._instance is not None:
            self._instance.cancel()
            try:
                await self._instance
            except asyncio.CancelledError:
                pass
            self._instance = None
        await self._producer.close()
