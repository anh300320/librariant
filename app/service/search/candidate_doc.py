"""Elasticsearch document format for candidates: index mapping + conversion.

A search document looks like:

    {
      "doc_id": "...", "filename": "cv.pdf", "text": "<full CV text>",
      "tags": [...], "organization": "default", "created_at": "...",
      "candidate": {
        "id": 12, "source_document_id": 3,
        "full_name": "Jane Doe", "email": "...", "phone": "...", "location": "...",
        "headline": "...", "summary": "...",
        "tech_stack": ["Python", "PostgreSQL"],          # candidate's listed skills
        "all_tech_stack": ["FastAPI", "Kafka", ...],     # skills + every job/project's stack
        "total_experience_months": 62,                   # overlapping jobs counted once
        "current_title": "...", "current_company": "...",
        "educations":  [{institution, degree, field_of_study, start_date, end_date,
                         gpa, gpa_cap, gpa_normalized, description}],
        "experiences": [{company, title, location, start_date, end_date, is_current,
                         duration_months, description, tech_stack}],
        "projects":    [{name, role, url, start_date, end_date, description, tech_stack}]
      }
    }

`educations`, `experiences` and `projects` are `nested`, so a query like
"Python *at the same job as* title Senior" matches within one entry instead of
across different entries. Tech names and other exact-match fields are keywords
with a lowercase normalizer, so filtering on "python" matches "Python".
"""

from datetime import date
from typing import Any

from app.models.candidate import Candidate, Education, Project, WorkExperience

_KEYWORD = {"type": "keyword", "normalizer": "lowercase_normalizer"}
# Full-text searchable, plus `.keyword` for exact match / aggregations / sorting.
_TEXT_AND_KEYWORD = {
    "type": "text",
    "fields": {"keyword": {"type": "keyword", "normalizer": "lowercase_normalizer", "ignore_above": 256}},
}
_TEXT = {"type": "text"}
_DATE = {"type": "date"}

INDEX_SETTINGS: dict[str, Any] = {
    "analysis": {
        "normalizer": {
            "lowercase_normalizer": {"type": "custom", "filter": ["lowercase", "asciifolding"]},
        },
    },
}

INDEX_MAPPINGS: dict[str, Any] = {
    # Unmapped fields are kept in _source but not indexed, rather than letting
    # Elasticsearch guess types.
    "dynamic": False,
    "properties": {
        "doc_id": {"type": "keyword"},
        "filename": _TEXT_AND_KEYWORD,
        "text": _TEXT,
        "tags": _KEYWORD,
        "organization": {"type": "keyword"},
        "created_at": _DATE,
        "candidate": {
            "properties": {
                "id": {"type": "long"},
                "source_document_id": {"type": "long"},
                "full_name": _TEXT_AND_KEYWORD,
                "email": _KEYWORD,
                "phone": {"type": "keyword"},
                "location": _TEXT_AND_KEYWORD,
                "headline": _TEXT_AND_KEYWORD,
                "summary": _TEXT,
                "tech_stack": _KEYWORD,
                "all_tech_stack": _KEYWORD,
                "total_experience_months": {"type": "integer"},
                "current_title": _TEXT_AND_KEYWORD,
                "current_company": _TEXT_AND_KEYWORD,
                "educations": {
                    "type": "nested",
                    "properties": {
                        "institution": _TEXT_AND_KEYWORD,
                        "degree": _TEXT_AND_KEYWORD,
                        "field_of_study": _TEXT_AND_KEYWORD,
                        "start_date": _DATE,
                        "end_date": _DATE,
                        "gpa": {"type": "float"},
                        "gpa_cap": {"type": "float"},
                        "gpa_normalized": {"type": "float"},
                        "description": _TEXT,
                    },
                },
                "experiences": {
                    "type": "nested",
                    "properties": {
                        "company": _TEXT_AND_KEYWORD,
                        "title": _TEXT_AND_KEYWORD,
                        "location": _TEXT_AND_KEYWORD,
                        "start_date": _DATE,
                        "end_date": _DATE,
                        "is_current": {"type": "boolean"},
                        "duration_months": {"type": "integer"},
                        "description": _TEXT,
                        "tech_stack": _KEYWORD,
                    },
                },
                "projects": {
                    "type": "nested",
                    "properties": {
                        "name": _TEXT_AND_KEYWORD,
                        "role": _TEXT_AND_KEYWORD,
                        "url": {"type": "keyword"},
                        "start_date": _DATE,
                        "end_date": _DATE,
                        "description": _TEXT,
                        "tech_stack": _KEYWORD,
                    },
                },
            },
        },
    },
}


def candidate_to_es(candidate: Candidate, today: date) -> dict[str, Any]:
    """Convert a Candidate into the `candidate` object of a search document.

    `today` is the end date used for current roles (end_date = null).
    """
    current = [exp for exp in candidate.experiences if exp.end_date is None]
    latest_current = max(current, key=lambda e: e.start_date or date.min, default=None)
    return {
        "id": candidate.id or None,
        "source_document_id": candidate.source_document_id,
        "full_name": candidate.full_name,
        "email": candidate.email,
        "phone": candidate.phone,
        "location": candidate.location,
        "headline": candidate.headline,
        "summary": candidate.summary,
        "tech_stack": _unique(candidate.tech_stack),
        "all_tech_stack": _unique(
            [
                *candidate.tech_stack,
                *(t for exp in candidate.experiences for t in exp.tech_stack),
                *(t for proj in candidate.projects for t in proj.tech_stack),
            ]
        ),
        "total_experience_months": _total_months(candidate.experiences, today),
        "current_title": latest_current.title if latest_current else None,
        "current_company": latest_current.company if latest_current else None,
        "educations": [_education(edu) for edu in candidate.educations],
        "experiences": [_experience(exp, today) for exp in candidate.experiences],
        "projects": [_project(proj) for proj in candidate.projects],
    }


def es_to_candidate(source: dict[str, Any]) -> Candidate | None:
    """Rebuild a Candidate from the `candidate` object of a search hit (derived fields dropped)."""
    if not source:
        return None
    return Candidate.model_validate({**source, "id": source.get("id") or 0})


def _education(edu: Education) -> dict[str, Any]:
    gpa_normalized = (
        round(edu.gpa / edu.gpa_cap, 4)
        if edu.gpa is not None and edu.gpa_cap  # gpa_cap of 0/None can't be normalized
        else None
    )
    return {
        **edu.model_dump(mode="json", exclude={"id"}),
        "gpa_normalized": gpa_normalized,
    }


def _experience(exp: WorkExperience, today: date) -> dict[str, Any]:
    return {
        **exp.model_dump(mode="json", exclude={"id"}),
        "tech_stack": _unique(exp.tech_stack),
        "is_current": exp.end_date is None and exp.start_date is not None,
        "duration_months": _months(exp.start_date, exp.end_date or today) if exp.start_date else None,
    }


def _project(proj: Project) -> dict[str, Any]:
    return {
        **proj.model_dump(mode="json", exclude={"id"}),
        "tech_stack": _unique(proj.tech_stack),
    }


def _months(start: date, end: date) -> int:
    return max(0, (end.year - start.year) * 12 + (end.month - start.month))


def _total_months(experiences: list[WorkExperience], today: date) -> int:
    """Total months worked, counting overlapping jobs only once."""
    intervals = sorted(
        (exp.start_date, min(exp.end_date or today, today))
        for exp in experiences
        if exp.start_date is not None
    )
    total = 0
    current_start: date | None = None
    current_end: date | None = None
    for start, end in intervals:
        if current_end is None or start > current_end:
            if current_start is not None and current_end is not None:
                total += _months(current_start, current_end)
            current_start, current_end = start, end
        else:
            current_end = max(current_end, end)
    if current_start is not None and current_end is not None:
        total += _months(current_start, current_end)
    return total


def _unique(names: list[str]) -> list[str]:
    """Drop blanks and case-insensitive duplicates, keeping the first spelling."""
    seen: set[str] = set()
    result = []
    for name in names:
        name = name.strip()
        if name and name.lower() not in seen:
            seen.add(name.lower())
            result.append(name)
    return result
