import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.background_workers.consumer.base import KafkaConsumer
from app.background_workers.consumer.document_indexer import DocumentIndexerWorker
from app.background_workers.producer.base import AsyncBackgroundWorker
from app.background_workers.producer.document_upload import DocumentUploadedProducer
from app.db.repository.idempotent import DbOpManager
from app.db.session import get_db_sess, init_db
from app.models.events import DOCUMENT_UPLOAD_EVENT
from app.service.doc_parser.manager import ParserManager
from app.service.doc_parser.pdf import PdfParser
from app.service.extractor.llm_extractor import LlmExtractor
from app.settings.kafka import kafka_settings
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
    await search_service.ensure_index()
    storage_service = AsyncMinioStorageService(settings=minio_settings)
    app.state.storage_service = storage_service
    app.state.search_service = search_service

    outbox_relay = AsyncBackgroundWorker(
        scan_interval_sec=kafka_settings.outbox_scan_interval_sec,
        producer=DocumentUploadedProducer(kafka_settings),
    )
    indexer_consumer = KafkaConsumer(
        topic=DOCUMENT_UPLOAD_EVENT,
        processor=DocumentIndexerWorker(
            search_service=search_service,
            storage=storage_service,
            parser=ParserManager([PdfParser()]),
            idempotency_manager=DbOpManager(task_name="document_indexer", get_db_sess_func=get_db_sess),
            extractor=LlmExtractor(),
            get_db_sess_func=get_db_sess,
        ),
        kafka_settings=kafka_settings,
    )
    await outbox_relay.start()
    consumer_task = asyncio.create_task(indexer_consumer.run())

    yield

    consumer_task.cancel()
    await indexer_consumer.stop()
    await outbox_relay.stop()


app = FastAPI(
    title="librariant",
    lifespan=lifespan,
)
app.include_router(auth_router)
app.include_router(documents_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
