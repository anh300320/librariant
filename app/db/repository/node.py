from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.entities.node import Node
from app.models.document import Document, BaseNode, Folder


def _convert_node(node: Node) -> BaseNode:
    if node.is_folder:
        return Folder(
            id=node.id,
            name=node.name,
            path=Path(node.path),
        )
    else:
        return Document(
            id=node.id,
            name=node.name,
            path=Path(node.path)
        )


async def get_node_by_path(db_sess: AsyncSession, path: str) -> BaseNode | None:
    stmt = select(Node).where(Node.path == path).limit(1)
    result = await db_sess.execute(stmt)
    node = result.scalar_one_or_none()
    if not node:
        return None

    return _convert_node(node)


async def get_child_nodes_by_parent_id(
    db_sess: AsyncSession,
    parent_id: int,
) -> list[BaseNode]:
    stmt = select(Node).where(Node.parent_id == parent_id)
    result = await db_sess.execute(stmt)
    return [
        _convert_node(node)
        for node in result.scalars().all()
    ]


async def add_document(
    db_sess: AsyncSession,
    parent: Folder,
    document: Document,
) -> Document:
    node = Node(
        name=document.name,
        path=(parent.path / document.name).as_posix(),
        storage_access_id=document.storage_access_id,
        parent_id=parent.id,
        is_folder=False,
        content_type=document.content_type,
        kb_size=document.kb_size,
    )
    db_sess.add(node)
    await db_sess.flush()
    await db_sess.refresh(node)
    document.id = node.id
    return document
