from datetime import date

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.entities.candidate import (
    Candidate as CandidateEntity,
    CandidateEducation,
    CandidateExperience,
    Technology,
    candidate_technology,
)
from app.db.entities.node import Node
from app.db.repository.candidate import (
    get_candidate,
    get_or_create_technologies,
    replace_candidate_for_document,
)
from app.models.candidate import Candidate, Education, Project, WorkExperience


@pytest.fixture
async def db(db_sess: AsyncSession) -> AsyncSession:
    db_sess.add(Node(id=1, name="cv.pdf", path="/cv.pdf", is_folder=False))
    await db_sess.flush()
    return db_sess


def _candidate(name: str = "Jane Doe") -> Candidate:
    return Candidate(
        full_name=name,
        email="jane@example.com",
        tech_stack=["Python", "PostgreSQL", "python"],
        educations=[Education(institution="MIT", degree="BSc", gpa=3.8, gpa_cap=4.0)],
        experiences=[
            WorkExperience(
                company="Acme",
                title="Backend Engineer",
                start_date=date(2021, 3, 1),
                tech_stack=["Python", "Kafka"],
            )
        ],
        projects=[Project(name="librariant", tech_stack=["FastAPI", "PostgreSQL"])],
    )


async def _count(db: AsyncSession, model) -> int:
    return (await db.execute(select(func.count()).select_from(model))).scalar_one()


async def test_saves_full_candidate(db: AsyncSession) -> None:
    saved = await replace_candidate_for_document(db, document_id=1, candidate=_candidate())

    assert saved.id > 0
    assert saved.source_document_id == 1
    assert saved.created_at is not None
    assert saved.tech_stack == ["PostgreSQL", "Python"]  # case-insensitive dedupe, sorted
    assert saved.educations[0].gpa == 3.8 and saved.educations[0].gpa_cap == 4.0
    assert saved.experiences[0].tech_stack == ["Kafka", "Python"]
    assert saved.projects[0].tech_stack == ["FastAPI", "PostgreSQL"]
    assert await get_candidate(db, saved.id) == saved


async def test_technologies_are_shared(db: AsyncSession) -> None:
    await replace_candidate_for_document(db, document_id=1, candidate=_candidate())
    names = (await db.execute(select(Technology.name).order_by(Technology.name))).scalars().all()
    assert names == ["FastAPI", "Kafka", "PostgreSQL", "Python"]


async def test_replaces_previous_candidate_for_same_document(db: AsyncSession) -> None:
    first = await replace_candidate_for_document(db, document_id=1, candidate=_candidate())
    second = await replace_candidate_for_document(db, document_id=1, candidate=_candidate("Jane D."))

    assert second.full_name == "Jane D."
    assert [c.full_name for c in (await db.execute(select(CandidateEntity))).scalars()] == ["Jane D."]
    assert await _count(db, CandidateEntity) == 1
    assert await _count(db, CandidateEducation) == 1
    assert await _count(db, CandidateExperience) == 1
    assert await _count(db, candidate_technology) == 2
    assert await _count(db, Technology) == 4  # reused, not duplicated


async def test_get_or_create_reuses_existing_case_insensitively(db: AsyncSession) -> None:
    db.add(Technology(name="Python"))
    await db.flush()

    techs = await get_or_create_technologies(db, [" python ", "Go", "", "GO"])

    assert set(techs) == {"python", "go"}
    assert techs["python"].name == "Python"
    assert techs["go"].name == "Go"
    assert await _count(db, Technology) == 2


async def test_get_or_create_empty(db: AsyncSession) -> None:
    assert await get_or_create_technologies(db, []) == {}
