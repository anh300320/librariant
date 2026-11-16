import logging
import uuid
from typing import Any

from app.background_workers.consumer.base import AsyncProcessor
from app.background_workers.model.event_payload import DocumentUploadEventPayload
from app.idempotent.manager import IdempotencyManager
from app.lib.utils import get_current_time
from app.models.document import Document
from app.service.doc_parser.manager import ParserManager
from app.service.search.base import AsyncSearchService
from app.service.search.model import SearchDocument
from app.service.storage.base import AsyncStorageService


_logger = logging.getLogger(__name__)


class DocumentIndexerWorker(AsyncProcessor[DocumentUploadEventPayload]):

    def __init__(
        self,
        search_service: AsyncSearchService,
        storage: AsyncStorageService,
        parser: ParserManager,
        idempotency_manager: IdempotencyManager[uuid.UUID],
    ) -> None:
        self._search_service = search_service
        self._storage = storage
        self._parser = parser
        self._idempotency_manager = idempotency_manager

    async def parse_message(self, message: dict[str, Any]) -> DocumentUploadEventPayload:
        return DocumentUploadEventPayload.model_validate(message)

    async def process(self, task_data: DocumentUploadEventPayload) -> None:
        async with self._idempotency_manager.idempotent(task_data.storage_access_id) as claim:
            if not claim.success:
                _logger.info(
                    "skipping processing, the idempotency key has been claimed, key=%s",
                    task_data.storage_access_id,
                )
                return
            stored_object = await self._storage.load(task_data.storage_access_id)
            parsed_document = self._parser.parse(
                Document(
                    storage_access_id=stored_object.id,
                    content_type=stored_object.content_type,
                    raw_content=stored_object.content,
                    kb_size=stored_object.kb_size,
                )
            )
            index_document = SearchDocument(
                doc_id=stored_object.id,
                filename=stored_object.name,
                text=parsed_document.content,
                tags=[],
                organization="default",
                created_at=get_current_time(),
            )
            await self._search_service.add(document=index_document)
