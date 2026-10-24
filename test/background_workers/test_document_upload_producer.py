from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

from aiokafka.errors import KafkaConnectionError, MessageSizeTooLargeError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.background_workers.producer.document_upload import DocumentUploadedProducer
from app.db.entities.event_outbox import EventOutbox
from app.db.repository.event_outbox import add_event_outbox
from app.models.events import DOCUMENT_UPLOAD_EVENT
from app.settings.kafka import KafkaSettings


async def test_produce_publishes_and_marks_events(db_sess: AsyncSession):
    await add_event_outbox(db_sess, DOCUMENT_UPLOAD_EVENT, {"document_id": 1})
    await add_event_outbox(db_sess, "other.event", {"x": 1})
    await db_sess.commit()

    @asynccontextmanager
    async def _sess():
        yield db_sess

    producer = DocumentUploadedProducer(KafkaSettings())
    producer._kafka_producer = AsyncMock()

    with patch("app.background_workers.producer.document_upload.get_db_sess", _sess):
        await producer.produce()
        await producer.produce()

    producer._kafka_producer.send_and_wait.assert_awaited_once()
    rows = (await db_sess.execute(select(EventOutbox).order_by(EventOutbox.id))).scalars().all()
    assert rows[0].published_at is not None
    assert rows[0].status == "PUBLISHED"
    assert rows[1].published_at is None


async def test_produce_commits_events_sent_before_a_failure(db_sess: AsyncSession):

    for i in range(3):
        await add_event_outbox(db_sess, DOCUMENT_UPLOAD_EVENT, {"document_id": i})
    await db_sess.commit()

    @asynccontextmanager
    async def _sess():
        yield db_sess

    producer = DocumentUploadedProducer(KafkaSettings())
    producer._kafka_producer = AsyncMock()
    producer._kafka_producer.send_and_wait.side_effect = [None, KafkaConnectionError(), None]

    with patch("app.background_workers.producer.document_upload.get_db_sess", _sess):
        await producer.produce()

    rows = (await db_sess.execute(select(EventOutbox).order_by(EventOutbox.id))).scalars().all()
    assert [r.published_at is not None for r in rows] == [True, False, False]
    assert producer._kafka_producer.send_and_wait.await_count == 2


async def test_produce_parks_non_retriable_failures(db_sess: AsyncSession):
    for i in range(3):
        await add_event_outbox(db_sess, DOCUMENT_UPLOAD_EVENT, {"document_id": i})
    await db_sess.commit()

    @asynccontextmanager
    async def _sess():
        yield db_sess

    producer = DocumentUploadedProducer(KafkaSettings())
    producer._kafka_producer = AsyncMock()
    producer._kafka_producer.send_and_wait.side_effect = [
        None,
        MessageSizeTooLargeError(),
        None,
    ]

    with patch("app.background_workers.producer.document_upload.get_db_sess", _sess):
        await producer.produce()
        await producer.produce()

    rows = (await db_sess.execute(select(EventOutbox).order_by(EventOutbox.id))).scalars().all()
    assert [r.status for r in rows] == ["PUBLISHED", "FAILED", "PUBLISHED"]
    assert rows[1].error
    assert producer._kafka_producer.send_and_wait.await_count == 3
