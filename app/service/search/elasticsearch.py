from datetime import datetime
from typing import Any

from elasticsearch import AsyncElasticsearch, Elasticsearch

from app.service.search.base import SearchQuery, AsyncSearchService
from app.service.search.model import SearchDocument
from app.settings.elasticsearch import elasticsearch_settings, ElasticsearchSettings


class ElasticsearchService(AsyncSearchService):

    def __init__(self, settings: ElasticsearchSettings):
        self._settings = settings
        self._index = settings.index
        self._client: AsyncElasticsearch = AsyncElasticsearch(hosts=[settings.url])

    async def add(
        self,
        document: SearchDocument,
    ) -> None:
        es_doc = self._convert_to_es_doc(document=document)
        await self._client.index(index=self._index, document=es_doc)

    def _convert_to_es_doc(
        self,
        document: SearchDocument,
    ) -> dict[str, Any]:
        return {
            "doc_id": document.doc_id,
            "filename": document.filename,
            "text": document.text,
            "organization": document.organization,
            "created_at": document.created_at.isoformat(),
            "tags": document.tags
        }

    async def search(
        self,
        search: SearchQuery,
    ) -> list[SearchDocument]:
        body = self._build_query(search)
        result = await self._client.search(index=self._index, body=body)
        return self._parse_es_result(result)

    def _build_query(
        self,
        search: SearchQuery,
    ) -> dict[str, Any]:
        return {
            "query": {
                "wildcard": {
                    "content": {
                        "value": f"*{search.raw_query}*",
                        "case_insensitive": True,
                    }
                }
            }
        }

    def _parse_es_result(
        self,
        search_result: dict[str, Any],
    ) -> list[SearchDocument]:
        hits = search_result.get("hits", {}).get("hits", [])
        documents: list[SearchDocument] = []

        for hit in hits:
            source = hit.get("_source", {})
            documents.append(
                SearchDocument(
                    doc_id=source.get("doc_id", hit.get("_id", "")),
                    filename=source.get("filename", ""),
                    # Keep compatibility with both indexed field names.
                    text=source.get("text", source.get("content", "")),
                    tags=source.get("tags", []),
                    organization=source.get("organization", ""),
                    created_at=source.get("created_at", datetime.now().isoformat()),
                )
            )

        return documents


def init_index(index_name: str):
    es_client = Elasticsearch(hosts=[elasticsearch_settings.url])
    if not es_client.indices.exists(index=index_name):
        es_client.indices.create(
            index=index_name,
            body={
                "mappings": {
                    "properties": {
                        "user_id": {"type": "keyword"},
                        "file_id": {"type": "keyword"},
                        "filename": {"type": "text"},
                        "content": {"type": "text"},
                        "created_at": {"type": "date"}
                    }
                }
            }
        )
