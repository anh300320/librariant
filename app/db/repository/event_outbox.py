from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.entities.event_outbox import EventOutbox, EventOutboxStatus
from app.lib.utils import get_current_time
from app.models.events import Event


async def add_event_outbox(
    db_sess: AsyncSession,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    db_sess.add(
        EventOutbox(
            event_type=event_type,
            payload=payload
        )
    )
    await db_sess.flush()


async def get_unpublished_event(
    db_sess: AsyncSession,
    event_type: str,
    limit: int = 100,
) -> list[Event]:
    """
    Fetch the oldest unpublished events, locking the rows so concurrent
    relays skip them (no-op on backends without row locks, e.g. SQLite).
    """
    stmt = (
        select(EventOutbox)
        .where(
            EventOutbox.status == EventOutboxStatus.PENDING.value,
            EventOutbox.event_type == event_type,
        )
        .order_by(EventOutbox.id.asc())
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    result = await db_sess.execute(stmt)
    return [
        Event(
            id=event.id,
            event_type=event.event_type,
            payload=event.payload,
        )
        for event in result.scalars().all()
    ]


async def mark_events_published(
    db_sess: AsyncSession,
    event_ids: list[int],
) -> None:
    if not event_ids:
        return
    await db_sess.execute(
        update(EventOutbox)
        .where(EventOutbox.id.in_(event_ids))
        .values(
            status=EventOutboxStatus.PUBLISHED.value,
            published_at=get_current_time(),
        )
    )


async def mark_events_failed(
    db_sess: AsyncSession,
    errors_by_event_id: dict[int, str],
) -> None:
    """Park events that can never be published so they stop being retried."""
    for event_id, error in errors_by_event_id.items():
        await db_sess.execute(
            update(EventOutbox)
            .where(EventOutbox.id == event_id)
            .values(status=EventOutboxStatus.FAILED.value, error=error)
        )
