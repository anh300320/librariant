from __future__ import annotations

from datetime import date

from sqlalchemy import CheckConstraint, Column, Date, Float, ForeignKey, String, Table, Text
from sqlalchemy.ext.associationproxy import AssociationProxy, association_proxy
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.entities.base import Base


class Technology(Base):
    """A single technology (e.g. "Python", "PostgreSQL"), shared by every candidate that uses it."""

    __tablename__ = "technology"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)


def _technology_link_table(name: str, owner_table: str) -> Table:
    return Table(
        name,
        Base.metadata,
        Column(f"{owner_table}_id", ForeignKey(f"{owner_table}.id", ondelete="CASCADE"), primary_key=True),
        Column("technology_id", ForeignKey("technology.id", ondelete="CASCADE"), primary_key=True, index=True),
    )


candidate_technology = _technology_link_table("candidate_technology", "candidate")
candidate_experience_technology = _technology_link_table("candidate_experience_technology", "candidate_experience")
candidate_project_technology = _technology_link_table("candidate_project_technology", "candidate_project")


class Candidate(Base):
    __tablename__ = "candidate"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    headline: Mapped[str | None] = mapped_column(String(255), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    technologies: Mapped[list[Technology]] = relationship(secondary=candidate_technology, order_by=Technology.name)
    # Read-only list of names, so Pydantic models can read `tech_stack` as list[str].
    # To write, assign Technology rows (get-or-create by name) to `technologies`.
    tech_stack: AssociationProxy[list[str]] = association_proxy("technologies", "name")
    source_document_id: Mapped[int | None] = mapped_column(
        ForeignKey("node.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    educations: Mapped[list[CandidateEducation]] = relationship(
        back_populates="candidate",
        cascade="all, delete-orphan",
        order_by="CandidateEducation.start_date.desc()",
    )
    experiences: Mapped[list[CandidateExperience]] = relationship(
        back_populates="candidate",
        cascade="all, delete-orphan",
        order_by="CandidateExperience.start_date.desc()",
    )
    projects: Mapped[list[CandidateProject]] = relationship(
        back_populates="candidate",
        cascade="all, delete-orphan",
        order_by="CandidateProject.start_date.desc()",
    )


class CandidateEducation(Base):
    __tablename__ = "candidate_education"
    __table_args__ = (
        CheckConstraint("gpa IS NULL OR gpa_cap IS NULL OR gpa <= gpa_cap", name="ck_candidate_education_gpa_le_cap"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidate.id", ondelete="CASCADE"),
        index=True,
    )
    institution: Mapped[str] = mapped_column(String(255))
    degree: Mapped[str | None] = mapped_column(String(255), nullable=True)
    field_of_study: Mapped[str | None] = mapped_column(String(255), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    gpa: Mapped[float | None] = mapped_column(Float, nullable=True)
    gpa_cap: Mapped[float | None] = mapped_column(Float, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    candidate: Mapped[Candidate] = relationship(back_populates="educations")


class CandidateExperience(Base):
    __tablename__ = "candidate_experience"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidate.id", ondelete="CASCADE"),
        index=True,
    )
    company: Mapped[str] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(255))
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    technologies: Mapped[list[Technology]] = relationship(secondary=candidate_experience_technology, order_by=Technology.name)
    # Read-only list of names, so Pydantic models can read `tech_stack` as list[str].
    # To write, assign Technology rows (get-or-create by name) to `technologies`.
    tech_stack: AssociationProxy[list[str]] = association_proxy("technologies", "name")

    candidate: Mapped[Candidate] = relationship(back_populates="experiences")


class CandidateProject(Base):
    __tablename__ = "candidate_project"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidate.id", ondelete="CASCADE"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255))
    role: Mapped[str | None] = mapped_column(String(255), nullable=True)
    url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    technologies: Mapped[list[Technology]] = relationship(secondary=candidate_project_technology, order_by=Technology.name)
    # Read-only list of names, so Pydantic models can read `tech_stack` as list[str].
    # To write, assign Technology rows (get-or-create by name) to `technologies`.
    tech_stack: AssociationProxy[list[str]] = association_proxy("technologies", "name")

    candidate: Mapped[Candidate] = relationship(back_populates="projects")
