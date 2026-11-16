import uuid
from datetime import datetime

from sqlalchemy import String, Integer, DateTime, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.entities.base import Base


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_record"

    # Composite primary key: a key is unique within a task, so different tasks
    # may reuse the same key (e.g. a document_id) without colliding.
    task_name: Mapped[str] = mapped_column(String(255), primary_key=True)
    key: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    status: Mapped[str] = mapped_column(String(16))                   # processing | succeeded | failed
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
