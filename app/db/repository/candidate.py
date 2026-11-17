from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.entities.candidate import (
    Candidate as CandidateEntity,
    CandidateEducation,
    CandidateExperience,
    CandidateProject,
    Technology,
    candidate_experience_technology,
    candidate_project_technology,
    candidate_technology,
)
from app.models.candidate import Candidate


async def replace_candidate_for_document(
    db_sess: AsyncSession,
    document_id: int,
    candidate: Candidate,
) -> Candidate:
    """Save `candidate` as the profile extracted from document `document_id`.

    Any candidate previously extracted from the same document is deleted first,
    so re-processing a document (e.g. a retried task) never creates duplicates.
    """
    await delete_candidates_for_document(db_sess, document_id)

    all_names = [
        *candidate.tech_stack,
        *(name for exp in candidate.experiences for name in exp.tech_stack),
        *(name for proj in candidate.projects for name in proj.tech_stack),
    ]
    technologies = await get_or_create_technologies(db_sess, all_names)

    def techs(names: list[str]) -> list[Technology]:
        return _dedupe([technologies[name.strip().lower()] for name in names if name.strip()])

    entity = CandidateEntity(
        full_name=candidate.full_name,
        email=candidate.email,
        phone=candidate.phone,
        location=candidate.location,
        headline=candidate.headline,
        summary=candidate.summary,
        source_document_id=document_id,
        technologies=techs(candidate.tech_stack),
        educations=[
            CandidateEducation(**edu.model_dump(exclude={"id"}))
            for edu in candidate.educations
        ],
        experiences=[
            CandidateExperience(
                **exp.model_dump(exclude={"id", "tech_stack"}),
                technologies=techs(exp.tech_stack),
            )
            for exp in candidate.experiences
        ],
        projects=[
            CandidateProject(
                **proj.model_dump(exclude={"id", "tech_stack"}),
                technologies=techs(proj.tech_stack),
            )
            for proj in candidate.projects
        ],
    )
    db_sess.add(entity)
    await db_sess.flush()
    return await get_candidate(db_sess, entity.id)  # type: ignore[return-value]


async def delete_candidates_for_document(db_sess: AsyncSession, document_id: int) -> None:
    """Delete every candidate extracted from `document_id`, with all child rows.

    Children are deleted explicitly rather than relying on ON DELETE CASCADE, so
    this behaves the same on databases that don't enforce foreign keys (SQLite).
    """
    candidate_ids = select(CandidateEntity.id).where(
        CandidateEntity.source_document_id == document_id
    )
    experience_ids = select(CandidateExperience.id).where(
        CandidateExperience.candidate_id.in_(candidate_ids)
    )
    project_ids = select(CandidateProject.id).where(
        CandidateProject.candidate_id.in_(candidate_ids)
    )
    statements = [
        delete(candidate_experience_technology).where(
            candidate_experience_technology.c.candidate_experience_id.in_(experience_ids)
        ),
        delete(candidate_project_technology).where(
            candidate_project_technology.c.candidate_project_id.in_(project_ids)
        ),
        delete(candidate_technology).where(candidate_technology.c.candidate_id.in_(candidate_ids)),
        delete(CandidateEducation).where(CandidateEducation.candidate_id.in_(candidate_ids)),
        delete(CandidateExperience).where(CandidateExperience.candidate_id.in_(candidate_ids)),
        delete(CandidateProject).where(CandidateProject.candidate_id.in_(candidate_ids)),
        delete(CandidateEntity).where(CandidateEntity.source_document_id == document_id),
    ]
    for stmt in statements:
        # "fetch" also evicts the deleted objects from the session, so a later
        # insert that reuses a primary key doesn't clash with a stale object.
        await db_sess.execute(stmt.execution_options(synchronize_session="fetch"))


async def get_candidate(db_sess: AsyncSession, candidate_id: int) -> Candidate | None:
    stmt = (
        select(CandidateEntity)
        .where(CandidateEntity.id == candidate_id)
        .options(
            selectinload(CandidateEntity.technologies),
            selectinload(CandidateEntity.educations),
            selectinload(CandidateEntity.experiences).selectinload(CandidateExperience.technologies),
            selectinload(CandidateEntity.projects).selectinload(CandidateProject.technologies),
        )
        .execution_options(populate_existing=True)
    )
    entity = (await db_sess.execute(stmt)).scalar_one_or_none()
    if entity is None:
        return None
    return Candidate.model_validate(entity, from_attributes=True).model_copy(
        update={"created_at": entity.create_time}
    )


async def get_or_create_technologies(
    db_sess: AsyncSession,
    names: list[str],
) -> dict[str, Technology]:
    """Return Technology rows for `names`, keyed by lower-cased name.

    Matching is case-insensitive ("python" reuses an existing "Python"). Missing
    names are inserted with ON CONFLICT DO NOTHING, so concurrent workers adding
    the same technology don't fail on the unique constraint.
    """
    wanted: dict[str, str] = {}  # lower-cased -> first spelling seen
    for name in names:
        name = name.strip()
        if name:
            wanted.setdefault(name.lower(), name)
    if not wanted:
        return {}

    async def load() -> dict[str, Technology]:
        rows = await db_sess.execute(
            select(Technology).where(func.lower(Technology.name).in_(wanted))
        )
        return {tech.name.lower(): tech for tech in rows.scalars()}

    existing = await load()
    missing = [{"name": wanted[key]} for key in wanted if key not in existing]
    if missing:
        insert = pg_insert if db_sess.bind.dialect.name == "postgresql" else sqlite_insert
        await db_sess.execute(insert(Technology).values(missing).on_conflict_do_nothing())
        existing = await load()
    return existing


def _dedupe(items: list[Technology]) -> list[Technology]:
    seen: set[int] = set()
    result = []
    for item in items:
        if id(item) not in seen:
            seen.add(id(item))
            result.append(item)
    return result
