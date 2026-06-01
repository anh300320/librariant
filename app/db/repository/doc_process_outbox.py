from sqlalchemy.ext.asyncio import AsyncSession

from app.db.entities.doc_process_outbox import DocProcessOutbox, DocProcessOutboxStatus


async def add_doc_process_outbox(
    db_sess: AsyncSession,
    document_id: int,
    status: DocProcessOutboxStatus = DocProcessOutboxStatus.CREATED,
) -> None:
    db_sess.add(
        DocProcessOutbox(
            document_id=document_id,
            status=status
        )
    )
    await db_sess.flush()
