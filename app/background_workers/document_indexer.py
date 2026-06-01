from pathlib import Path

from pydantic import BaseModel

from app.background_workers.base import BaseBackgroundWorker
from app.models.document import Document
from app.service.doc_parser.manager import ParserManager
from app.service.search.base import SearchService
from app.service.storage.base import StorageService


class DocumentIndexTask(BaseModel):
    doc_url: str


class DocumentIndexerWorker(BaseBackgroundWorker[DocumentIndexTask]):
    def __init__(
        self,
        search_service: SearchService,
        storage: StorageService,
        parser: ParserManager,
    ) -> None:
        self._search_service = search_service
        self._storage = storage
        self._parser = parser

    def run(self, task_data: DocumentIndexTask) -> None:
        stored_object = self._storage.load(task_data.doc_url)
        document = Document(
            name=stored_object.name,
            content_type=stored_object.content_type,
            raw_content=stored_object.content,
            kb_size=stored_object.kb_size,
        )
        parsed_document = self._parser.parse(document)
        self._search_service.add(document=parsed_document)

    def _get_path(self, task: DocumentIndexTask) -> Path:
        pass
