import enum

from sqlalchemy import Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db.entities.base import Base


class DocProcessOutboxStatus(str, enum.Enum):
    CREATED = "CREATED"
    QUEUED = "QUEUED"


class DocProcessOutbox(Base):
    __tablename__ = "doc_process_outbox"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("node.id"),
        nullable=False,
    )
    status: Mapped[DocProcessOutboxStatus] = mapped_column(
        Enum(DocProcessOutboxStatus),
        nullable=False,
        default=DocProcessOutboxStatus.CREATED,
    )
