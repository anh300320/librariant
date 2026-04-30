from pathlib import Path

from pydantic import BaseModel

from app.background_workers.base import BaseBackgroundWorker
from app.service.doc_parser.manager import ParserManager
from app.service.search.base import SearchService
from app.service.storage.base import StorageService


class DocumentIndexerWorker[DocumentIndexTask](BaseBackgroundWorker):
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
        path = self._get_path(task_data)
        document = self._storage.load(path)
        parsed_document = self._parser.parse(document)
        self._search_service.add(document=document)

    def _get_path(self, task: DocumentIndexTask) -> Path:
        pass


class DocumentIndexTask(BaseModel):
    doc_url: str