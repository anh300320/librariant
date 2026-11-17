import json
import logging

from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError

from app.background_workers.producer.base import AsyncProducer
from app.db.repository.event_outbox import (
    get_unpublished_event,
    mark_events_failed,
    mark_events_published,
)
from app.db.session import get_db_sess
from app.models.events import DOCUMENT_UPLOAD_EVENT
from app.settings.kafka import KafkaSettings

logger = logging.getLogger(__name__)


class DocumentUploadedProducer(AsyncProducer):
    def __init__(self, kafka_settings: KafkaSettings):
        self._batch_size = kafka_settings.outbox_batch_size
        self._kafka_producer = AIOKafkaProducer(
            bootstrap_servers=f"{kafka_settings.address}:{kafka_settings.port}",
            acks="all",
            enable_idempotence=True,
        )

    async def start(self) -> None:
        await self._kafka_producer.start()

    async def close(self) -> None:
        await self._kafka_producer.stop()

    async def produce(self) -> None:
        # Rows stay locked until commit; an event is only marked published
        # after the broker acked it, so delivery is at-least-once.
        async with get_db_sess() as db_sess:
            events = await get_unpublished_event(
                db_sess,
                DOCUMENT_UPLOAD_EVENT,
                limit=self._batch_size,
            )
            published_ids: list[int] = []
            failed: dict[int, str] = {}
            for event in events:
                try:
                    value = json.dumps(event.payload).encode("utf-8")
                    await self._kafka_producer.send_and_wait(
                        topic=event.event_type,
                        key=str(event.id).encode("utf-8"),
                        value=value,
                    )
                except KafkaError as exc:
                    logger.exception("Failed to publish event %s", event.id)
                    if exc.retriable:
                        continue
                    failed[event.id] = repr(exc)
                except Exception as exc:
                    failed[event.id] = repr(exc)
                    logger.exception("Unknown error when publishing event %s", event.id)
                    continue
                published_ids.append(event.id)
            await mark_events_published(db_sess, published_ids)
            await mark_events_failed(db_sess, failed)
