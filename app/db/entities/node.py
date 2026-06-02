from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, String, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.entities.base import Base


class Node(Base):
    __tablename__ = "node"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))
    path: Mapped[str] = mapped_column(String(1024))
    storage_access_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_folder: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    kb_size: Mapped[int | None] = mapped_column(Integer())
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("node.id"),
        nullable=True,
    )

    parent: Mapped[Node | None] = relationship(
        remote_side="Node.id",
        back_populates="children",
    )
    children: Mapped[list[Node]] = relationship(back_populates="parent")
