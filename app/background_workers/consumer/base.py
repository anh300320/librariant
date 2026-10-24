import json
import logging
from abc import ABC, abstractmethod
from typing import Any

from aiokafka import AIOKafkaConsumer

from app.settings.kafka import KafkaSettings


logger = logging.getLogger(__name__)


class AsyncConsumer(ABC):
    @abstractmethod
    async def run(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def stop(self) -> None:
        raise NotImplementedError


class AsyncProcessor[T](ABC):

    @abstractmethod
    async def parse_message(self, message: dict[str, Any]) -> T:
        raise NotImplementedError

    @abstractmethod
    async def process(self, task_data: T) -> None:
        raise NotImplementedError


class KafkaConsumer(AsyncConsumer):
    def __init__(
        self,
        topic: str,
        processor: AsyncProcessor,
        kafka_settings: KafkaSettings,
    ):
        self._processor = processor
        self._consumer = AIOKafkaConsumer(
            topic,
            group_id=kafka_settings.consumer_group,
            auto_offset_reset="earliest",
            bootstrap_servers=f"{kafka_settings.address}:{kafka_settings.port}",
            enable_auto_commit=False,
        )

    async def run(self) -> None:
        await self._consumer.start()
        async for message in self._consumer:
            try:
                payload = await self._processor.parse_message(
                    json.loads(message.value)
                )
                await self._processor.process(payload)
                await self._consumer.commit()
            except Exception:
                logger.exception(
                    "Failed to process task from message: %s",
                    message.value,
                )

    async def stop(self) -> None:
        await self._consumer.stop()
