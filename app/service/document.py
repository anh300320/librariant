from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.background_workers.model.event_payload import DocumentUploadEventPayload
from app.db.repository.event_outbox import add_event_outbox
from app.db.repository.node import get_node_by_path, add_document
from app.db.session import get_db_sess
from app.exception.node import NodeNotFoundError, InvalidNodeTypeError
from app.models.document import Document, Folder
from app.models.events import DOCUMENT_UPLOAD_EVENT
from app.service.storage.base import StoredObject, AsyncStorageService


class DocumentService:
    def __init__(
        self,
        storage_service: AsyncStorageService,
    ) -> None:
        self._storage_service = storage_service

    async def add_document(
        self,
        document: Document,
        path: str,
    ) -> Document:
        compiled_path = Path(path)
        parent_path = compiled_path.parent

        storage_obj = StoredObject(
            name=document.name,
            content_type=document.content_type,
            content=document.raw_content,
            kb_size=document.kb_size,
        )
        document.storage_access_id = await self._storage_service.store(storage_obj)

        async with get_db_sess() as db_sess:
            parent_folder = await get_node_by_path(db_sess, parent_path.as_posix())

            if not parent_folder:
                raise NodeNotFoundError(parent_path)
            if not isinstance(parent_folder, Folder):
                raise InvalidNodeTypeError(parent_path)

            document = await add_document(
                db_sess,
                parent=parent_folder,
                document=document
            )
            payload = DocumentUploadEventPayload(
                document_id=document.id,
                storage_access_id=document.storage_access_id,
            )
            await add_event_outbox(
                db_sess=db_sess,
                event_type=DOCUMENT_UPLOAD_EVENT,
                payload=payload.model_dump(),
            )
        return document
