"""
Integration tests for POST /documents (upload_document).

Database:  SQLite in-memory (via aiosqlite) – created fresh for every test.
Storage:   StubStorageService – records objects in-memory, no real I/O.
"""
import io
import json

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.entities.node import Node
from app.router.dependencies import get_document_service
from app.router.documents import router
from app.service.document import DocumentService
from test.conftest import StubStorageService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app():
    test_app = FastAPI()
    test_app.include_router(router)
    return test_app


@pytest_asyncio.fixture
async def app_with_deps(
    app: FastAPI,
    db_sess: AsyncSession,
    storage_service: StubStorageService,
    patch_get_db_sess,
):
    """Override get_document_service to use the test DB session and stub storage."""

    async def _override() -> DocumentService:
        return DocumentService(storage_service=storage_service)

    app.dependency_overrides[get_document_service] = _override
    yield app
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(app_with_deps: FastAPI):
    async with AsyncClient(
        transport=ASGITransport(app=app_with_deps), base_url="http://test"
    ) as c:
        yield c


@pytest_asyncio.fixture
async def parent_folder(db_sess: AsyncSession) -> Node:
    """Insert a folder node at /docs so the upload endpoint can resolve the parent."""
    node = Node(
        name="docs",
        path="/docs",
        storage_access_id="",
        is_folder=True,
    )
    db_sess.add(node)
    await db_sess.commit()
    await db_sess.refresh(node)
    return node


@pytest_asyncio.fixture
async def file_node_in_docs(db_sess: AsyncSession, parent_folder: Node) -> Node:
    """Insert a *file* (non-folder) node inside /docs to test type-mismatch errors."""
    node = Node(
        name="existing.pdf",
        path="/docs/existing.pdf",
        storage_access_id="some-id",
        is_folder=False,
        parent_id=parent_folder.id,
    )
    db_sess.add(node)
    await db_sess.commit()
    await db_sess.refresh(node)
    return node


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _file(content: bytes = b"hello pdf", filename: str = "report.pdf"):
    return ("file", (filename, io.BytesIO(content), "application/pdf"))


def _metadata(path: str = "/docs/report.pdf") -> str:
    return json.dumps({"path": path})


# ---------------------------------------------------------------------------
# Success
# ---------------------------------------------------------------------------


class TestUploadDocumentSuccess:
    async def test_returns_201_with_document_info(
        self, client: AsyncClient, parent_folder: Node
    ):
        response = await client.post(
            "/documents",
            files=[_file()],
            data={"metadata": _metadata()},
        )

        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "200"
        assert body["message"] == "Upload document successfully"
        assert isinstance(body["data"]["id"], int)
        assert body["data"]["name"] == "report.pdf"

    async def test_document_is_persisted_in_database(
        self,
        client: AsyncClient,
        parent_folder: Node,
        db_sess: AsyncSession,
    ):
        await client.post(
            "/documents",
            files=[_file(filename="notes.pdf")],
            data={"metadata": _metadata("/docs/notes.pdf")},
        )

        from sqlalchemy import select
        from app.db.entities.node import Node as NodeEntity

        result = await db_sess.execute(
            select(NodeEntity).where(NodeEntity.name == "notes.pdf")
        )
        saved = result.scalar_one_or_none()
        assert saved is not None
        assert saved.is_folder is False
        assert saved.parent_id == parent_folder.id
        assert saved.content_type == "application/pdf"

    async def test_outbox_entry_is_created(
        self,
        client: AsyncClient,
        parent_folder: Node,
        db_sess: AsyncSession,
    ):
        response = await client.post(
            "/documents",
            files=[_file()],
            data={"metadata": _metadata()},
        )
        document_id = response.json()["data"]["id"]

        from sqlalchemy import select
        from app.db.entities.event_outbox import EventOutbox
        from app.models.events import DOCUMENT_UPLOAD_EVENT

        result = await db_sess.execute(
            select(EventOutbox).where(EventOutbox.event_type == DOCUMENT_UPLOAD_EVENT)
        )
        outbox = result.scalar_one_or_none()
        assert outbox is not None
        assert outbox.payload["document_id"] == document_id
        assert outbox.published_at is None

    async def test_file_content_is_sent_to_storage(
        self,
        client: AsyncClient,
        parent_folder: Node,
        storage_service: StubStorageService,
    ):
        await client.post(
            "/documents",
            files=[_file(content=b"pdf bytes here")],
            data={"metadata": _metadata()},
        )

        assert len(storage_service.stored) == 1
        stored_obj = next(iter(storage_service.stored.values()))
        assert stored_obj.content == b"pdf bytes here"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestUploadDocumentValidation:
    async def test_empty_file_returns_400(self, client: AsyncClient):
        response = await client.post(
            "/documents",
            files=[_file(content=b"")],
            data={"metadata": _metadata()},
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Uploaded file is empty."

    async def test_missing_file_returns_422(self, client: AsyncClient):
        response = await client.post(
            "/documents",
            data={"metadata": _metadata()},
        )

        assert response.status_code == 422

    async def test_missing_metadata_returns_422(self, client: AsyncClient):
        response = await client.post(
            "/documents",
            files=[_file()],
        )

        assert response.status_code == 422

    async def test_invalid_metadata_json_returns_422(self, client: AsyncClient):
        response = await client.post(
            "/documents",
            files=[_file()],
            data={"metadata": "not-valid-json"},
        )

        assert response.status_code == 422

    async def test_metadata_missing_path_field_returns_422(self, client: AsyncClient):
        response = await client.post(
            "/documents",
            files=[_file()],
            data={"metadata": json.dumps({"other_field": "value"})},
        )

        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Service-level errors surfaced through the endpoint
# ---------------------------------------------------------------------------


class TestUploadDocumentServiceErrors:
    async def test_parent_folder_not_found_returns_500(self, client: AsyncClient):
        """No folder seeded → NodeNotFoundError bubbles up as 500."""
        response = await client.post(
            "/documents",
            files=[_file()],
            data={"metadata": _metadata("/missing/report.pdf")},
        )

        assert response.status_code == 500

    async def test_parent_is_a_file_not_folder_returns_500(
        self, client: AsyncClient, file_node_in_docs: Node
    ):
        """Parent path resolves to a file node → InvalidNodeTypeError → 500."""
        response = await client.post(
            "/documents",
            files=[_file(filename="nested.pdf")],
            data={"metadata": _metadata("/docs/existing.pdf/nested.pdf")},
        )

        assert response.status_code == 500
