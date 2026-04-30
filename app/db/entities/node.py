from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.entities.base import Base


class Node(Base):
    __tablename__ = "node"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("node.id"),
        nullable=True,
    )

    parent: Mapped[Node | None] = relationship(
        remote_side="Node.id",
        back_populates="children",
    )
    children: Mapped[list[Node]] = relationship(back_populates="parent")
