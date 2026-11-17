import logging
from datetime import datetime
from typing import Any

from elasticsearch import AsyncElasticsearch

from app.lib.utils import get_current_time
from app.service.search.base import SearchQuery, AsyncSearchService
from app.service.search.candidate_doc import (
    INDEX_MAPPINGS,
    INDEX_SETTINGS,
    candidate_to_es,
    es_to_candidate,
)
from app.service.search.model import SearchDocument
from app.settings.elasticsearch import ElasticsearchSettings


_logger = logging.getLogger(__name__)


class ElasticsearchService(AsyncSearchService):

    def __init__(self, settings: ElasticsearchSettings):
        self._settings = settings
        self._index = settings.index
        self._client: AsyncElasticsearch = AsyncElasticsearch(hosts=[settings.url])

    async def ensure_index(self) -> None:
        """Create the index with the candidate mapping if it doesn't exist yet.

        An existing index is left untouched: mappings can't be changed in place,
        so an index created with an older mapping must be deleted (or reindexed).
        """
        if await self._client.indices.exists(index=self._index):
            return
        await self._client.indices.create(
            index=self._index,
            settings=INDEX_SETTINGS,
            mappings=INDEX_MAPPINGS,
        )
        _logger.info("created search index, index=%s", self._index)

    async def add(
        self,
        document: SearchDocument,
    ) -> None:
        es_doc = self._convert_to_es_doc(document=document)
        # Use doc_id as the Elasticsearch _id so re-indexing a document (e.g. a
        # retried task) overwrites it instead of creating a duplicate.
        await self._client.index(index=self._index, id=document.doc_id, document=es_doc)

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
            "tags": document.tags,
            "candidate": (
                candidate_to_es(document.candidate, today=get_current_time().date())
                if document.candidate
                else None
            ),
        }

    async def search(
        self,
        search: SearchQuery,
    ) -> list[SearchDocument]:
        result = await self._client.search(index=self._index, query=self._build_query(search))
        return self._parse_es_result(result.body)

    def _build_query(
        self,
        search: SearchQuery,
    ) -> dict[str, Any]:
        """Free-text search across the CV text and the main candidate fields.

        Matches in structured fields (name, title, skills) rank above matches
        that only appear somewhere in the CV text.
        """
        query = search.raw_query
        return {
            "bool": {
                "should": [
                    {
                        "multi_match": {
                            "query": query,
                            "fields": [
                                "candidate.full_name^4",
                                "candidate.headline^3",
                                "candidate.current_title^3",
                                "candidate.summary^2",
                                "candidate.location",
                                "filename",
                                "text",
                            ],
                        }
                    },
                    # Exact (case-insensitive) skill match, e.g. "python".
                    {"term": {"candidate.all_tech_stack": {"value": query, "boost": 3}}},
                    {
                        "nested": {
                            "path": "candidate.experiences",
                            "query": {
                                "multi_match": {
                                    "query": query,
                                    "fields": [
                                        "candidate.experiences.title^2",
                                        "candidate.experiences.company^2",
                                        "candidate.experiences.description",
                                    ],
                                }
                            },
                            "score_mode": "max",
                        }
                    },
                    {
                        "nested": {
                            "path": "candidate.projects",
                            "query": {
                                "multi_match": {
                                    "query": query,
                                    "fields": [
                                        "candidate.projects.name^2",
                                        "candidate.projects.description",
                                    ],
                                }
                            },
                            "score_mode": "max",
                        }
                    },
                    {
                        "nested": {
                            "path": "candidate.educations",
                            "query": {
                                "multi_match": {
                                    "query": query,
                                    "fields": [
                                        "candidate.educations.institution^2",
                                        "candidate.educations.degree",
                                        "candidate.educations.field_of_study",
                                    ],
                                }
                            },
                            "score_mode": "max",
                        }
                    },
                ],
                "minimum_should_match": 1,
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
                    candidate=es_to_candidate(source.get("candidate") or {}),
                )
            )

        return documents
