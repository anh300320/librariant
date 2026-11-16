import logging
import uuid
from typing import Any, AsyncContextManager, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.background_workers.consumer.base import AsyncProcessor
from app.background_workers.model.event_payload import DocumentUploadEventPayload
from app.db.repository.candidate import replace_candidate_for_document
from app.idempotent.manager import IdempotencyManager
from app.lib.utils import get_current_time
from app.models.document import Document
from app.service.doc_parser.manager import ParserManager
from app.service.extractor.base import BaseExtractor
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
        extractor: BaseExtractor,
        get_db_sess_func: Callable[[], AsyncContextManager[AsyncSession]],
    ) -> None:
        self._search_service = search_service
        self._storage = storage
        self._parser = parser
        self._idempotency_manager = idempotency_manager
        self._extractor = extractor
        self._get_db_sess_func = get_db_sess_func

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

            # Extract and save the candidate before indexing: the search index has
            # no idempotent upsert, so a failure after indexing would create a
            # duplicate search document when the task is retried. Saving the
            # candidate is safe to repeat (it replaces the document's previous one).
            candidate = await self._extractor.aextract(parsed_document.content)
            async with self._get_db_sess_func() as db_sess:
                saved = await replace_candidate_for_document(
                    db_sess, document_id=task_data.document_id, candidate=candidate
                )
                _logger.info(
                    "extracted candidate, document_id=%s, candidate_id=%s",
                    task_data.document_id,
                    saved.id,
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
