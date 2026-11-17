import uuid
from contextlib import asynccontextmanager

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.background_workers.consumer.document_indexer import DocumentIndexerWorker
from app.background_workers.model.event_payload import DocumentUploadEventPayload
from app.db.entities.candidate import Candidate as CandidateEntity
from app.db.entities.node import Node
from app.idempotent.manager import ClaimResult, IdempotencyManager, IdempotencyStatus
from app.models.candidate import Candidate
from app.models.document import Document
from app.service.doc_parser.base import Parser
from app.service.doc_parser.models import ParsedDocument
from app.service.extractor.base import BaseExtractor
from app.service.search.base import AsyncSearchService
from app.service.search.model import SearchDocument, SearchQuery
from app.service.storage.base import StoredObject


class FakeSearch(AsyncSearchService):
    def __init__(self) -> None:
        self.added: list[SearchDocument] = []

    async def add(self, document: SearchDocument) -> None:
        self.added.append(document)

    async def search(self, search: SearchQuery) -> list[SearchDocument]:
        return []


class FakeParser(Parser):
    def parse(self, document: Document) -> ParsedDocument:
        return ParsedDocument(original=document, content=document.raw_content.decode())


class FakeExtractor(BaseExtractor):
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.texts: list[str] = []

    def extract(self, text: str) -> Candidate:
        self.texts.append(text)
        if self.error:
            raise self.error
        return Candidate(full_name="Jane Doe", tech_stack=["Python"])


class FakeIdempotency(IdempotencyManager[uuid.UUID]):
    def __init__(self, claimable: bool = True) -> None:
        self.claimable = claimable
        self.outcome: str | None = None

    async def _claim(self, idempotency_key) -> ClaimResult:
        status = IdempotencyStatus.PROCESSING if self.claimable else IdempotencyStatus.SUCCEEDED
        return ClaimResult(success=self.claimable, status=status, token=1)

    async def _on_success(self, idempotency_key, claim) -> None:
        self.outcome = "succeeded"

    async def _on_fail(self, idempotency_key, claim) -> None:
        self.outcome = "failed"


@pytest.fixture
async def setup(db_sess: AsyncSession, storage_service):
    db_sess.add(Node(id=1, name="cv.pdf", path="/cv.pdf", is_folder=False))
    await db_sess.flush()
    storage_service.stored["obj-1"] = StoredObject(
        id="obj-1", name="cv.pdf", content=b"Jane Doe - Python developer", content_type="application/pdf"
    )

    @asynccontextmanager
    async def get_sess():
        yield db_sess

    def make(extractor: BaseExtractor, idempotency: FakeIdempotency | None = None):
        search = FakeSearch()
        idem = idempotency or FakeIdempotency()
        worker = DocumentIndexerWorker(
            search_service=search,
            storage=storage_service,
            parser=FakeParser(),  # type: ignore[arg-type]
            idempotency_manager=idem,
            extractor=extractor,
            get_db_sess_func=get_sess,
        )
        return worker, search, idem

    return make


PAYLOAD = DocumentUploadEventPayload(document_id=1, storage_access_id="obj-1")


async def _candidates(db_sess: AsyncSession) -> list[CandidateEntity]:
    return list((await db_sess.execute(select(CandidateEntity))).scalars())


async def test_extracts_saves_and_indexes(setup, db_sess: AsyncSession) -> None:
    extractor = FakeExtractor()
    worker, search, idem = setup(extractor)

    await worker.process(PAYLOAD)

    assert extractor.texts == ["Jane Doe - Python developer"]
    [candidate] = await _candidates(db_sess)
    assert candidate.full_name == "Jane Doe"
    assert candidate.source_document_id == 1
    assert [d.doc_id for d in search.added] == ["obj-1"]
    assert search.added[0].candidate is not None
    assert search.added[0].candidate.id == candidate.id
    assert search.added[0].candidate.tech_stack == ["Python"]
    assert idem.outcome == "succeeded"


async def test_extraction_failure_fails_task_without_indexing(setup, db_sess: AsyncSession) -> None:
    worker, search, idem = setup(FakeExtractor(error=RuntimeError("LLM down")))

    with pytest.raises(RuntimeError, match="LLM down"):
        await worker.process(PAYLOAD)

    assert search.added == []
    assert await _candidates(db_sess) == []
    assert idem.outcome == "failed"


async def test_reprocessing_does_not_duplicate_candidate(setup, db_sess: AsyncSession) -> None:
    worker, _, _ = setup(FakeExtractor())
    await worker.process(PAYLOAD)
    await worker.process(PAYLOAD)
    assert (await db_sess.execute(select(func.count()).select_from(CandidateEntity))).scalar_one() == 1


async def test_skips_when_already_claimed(setup, db_sess: AsyncSession) -> None:
    extractor = FakeExtractor()
    worker, search, _ = setup(extractor, FakeIdempotency(claimable=False))

    await worker.process(PAYLOAD)

    assert extractor.texts == []
    assert search.added == []
