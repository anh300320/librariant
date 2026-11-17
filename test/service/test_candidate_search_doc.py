import os

os.environ.setdefault("INDEX", "test")  # required by app.settings.elasticsearch at import

from datetime import date, datetime, timezone

from app.models.candidate import Candidate, Education, Project, WorkExperience
from app.service.search.candidate_doc import INDEX_MAPPINGS, candidate_to_es, es_to_candidate
from app.service.search.elasticsearch import ElasticsearchService
from app.service.search.model import SearchDocument
from app.settings.elasticsearch import ElasticsearchSettings

TODAY = date(2026, 11, 1)


def _candidate() -> Candidate:
    return Candidate(
        id=12,
        source_document_id=3,
        full_name="Jane Doe",
        headline="Senior Backend Engineer",
        tech_stack=["Python", "python ", "PostgreSQL"],
        educations=[
            Education(institution="MIT", degree="BSc", gpa=3.6, gpa_cap=4.0),
            Education(institution="Uni", gpa=8.0),  # no cap -> no normalized gpa
        ],
        experiences=[
            WorkExperience(company="Acme", title="Engineer", start_date=date(2018, 1, 1),
                           end_date=date(2021, 1, 1), tech_stack=["Java"]),
            # Overlaps the Acme job by 6 months.
            WorkExperience(company="Beta", title="Senior Engineer", start_date=date(2020, 7, 1),
                           tech_stack=["Python", "Kafka"]),
            WorkExperience(company="Gamma", title="Consultant"),  # no dates
        ],
        projects=[Project(name="librariant", tech_stack=["FastAPI", "PostgreSQL"])],
    )


def test_candidate_fields_and_derived_values() -> None:
    doc = candidate_to_es(_candidate(), today=TODAY)

    assert doc["id"] == 12 and doc["source_document_id"] == 3
    assert doc["tech_stack"] == ["Python", "PostgreSQL"]
    assert doc["all_tech_stack"] == ["Python", "PostgreSQL", "Java", "Kafka", "FastAPI"]
    # 2018-01 .. 2026-11 with the overlap counted once = 106 months.
    assert doc["total_experience_months"] == 106
    assert (doc["current_title"], doc["current_company"]) == ("Senior Engineer", "Beta")


def test_nested_entries() -> None:
    doc = candidate_to_es(_candidate(), today=TODAY)

    acme, beta, gamma = doc["experiences"]
    assert acme["start_date"] == "2018-01-01" and acme["end_date"] == "2021-01-01"
    assert (acme["is_current"], acme["duration_months"]) == (False, 36)
    assert (beta["is_current"], beta["duration_months"], beta["end_date"]) == (True, 76, None)
    assert (gamma["is_current"], gamma["duration_months"]) == (False, None)
    assert "id" not in acme

    mit, uni = doc["educations"]
    assert mit["gpa_normalized"] == 0.9
    assert uni["gpa_normalized"] is None
    assert doc["projects"][0]["tech_stack"] == ["FastAPI", "PostgreSQL"]


def test_round_trip_through_es_source() -> None:
    candidate = _candidate()
    rebuilt = es_to_candidate(candidate_to_es(candidate, today=TODAY))
    assert rebuilt is not None
    assert rebuilt.full_name == candidate.full_name
    assert rebuilt.experiences[1].company == "Beta"
    assert rebuilt.educations[0].gpa_cap == 4.0
    assert es_to_candidate({}) is None


def test_every_converted_field_is_mapped() -> None:
    """Catch fields added to the model but forgotten in the index mapping."""
    doc = candidate_to_es(_candidate(), today=TODAY)
    mapping = INDEX_MAPPINGS["properties"]["candidate"]["properties"]
    assert set(doc) <= set(mapping)
    for nested in ("educations", "experiences", "projects"):
        assert set(doc[nested][0]) <= set(mapping[nested]["properties"])


def test_es_document_includes_candidate() -> None:
    service = ElasticsearchService(ElasticsearchSettings(index="test"))
    es_doc = service._convert_to_es_doc(
        SearchDocument(
            doc_id="obj-1", filename="cv.pdf", text="cv", tags=[], organization="default",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc), candidate=_candidate(),
        )
    )
    assert es_doc["candidate"]["full_name"] == "Jane Doe"

    es_doc = service._convert_to_es_doc(
        SearchDocument(doc_id="obj-2", filename="a.pdf", text="x", tags=[], organization="default",
                       created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    )
    assert es_doc["candidate"] is None
