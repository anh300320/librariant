from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db.session import init_db
from app.router.auth import router as auth_router
from app.router.documents import router as documents_router
from app.service.search.elasticsearch import ElasticsearchService
from app.service.storage.minio import AsyncMinioStorageService
from app.settings.elasticsearch import elasticsearch_settings
from app.settings.minio import minio_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    search_service = ElasticsearchService(settings=elasticsearch_settings)
    storage_service = AsyncMinioStorageService(settings=minio_settings)
    app.state.storage_service = storage_service
    app.state.search_service = search_service

    yield


app = FastAPI(
    title="librariant",
    lifespan=lifespan,
)
app.include_router(auth_router)
app.include_router(documents_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
