from datetime import date, datetime

from typing import Self

from pydantic import BaseModel, Field, model_validator


class Education(BaseModel):
    id: int = 0
    institution: str
    degree: str | None = None
    field_of_study: str | None = None
    start_date: date | None = None
    end_date: date | None = None  # None = ongoing / unknown
    gpa: float | None = None  # e.g. 3.8
    gpa_cap: float | None = None  # max of the grading scale, e.g. 4.0 in "3.8/4.0"
    description: str | None = None

    @model_validator(mode="after")
    def _gpa_within_cap(self) -> Self:
        if self.gpa is not None and self.gpa_cap is not None and self.gpa > self.gpa_cap:
            raise ValueError(f"gpa ({self.gpa}) must not exceed gpa_cap ({self.gpa_cap})")
        return self


class WorkExperience(BaseModel):
    id: int = 0
    company: str
    title: str
    location: str | None = None
    start_date: date | None = None
    end_date: date | None = None  # None = current role / unknown
    description: str | None = None
    tech_stack: list[str] = Field(default_factory=list)


class Project(BaseModel):
    id: int = 0
    name: str
    role: str | None = None
    url: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    description: str | None = None
    tech_stack: list[str] = Field(default_factory=list)


class Candidate(BaseModel):
    id: int = 0
    full_name: str
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    headline: str | None = None  # e.g. "Senior Backend Engineer"
    summary: str | None = None
    tech_stack: list[str] = Field(default_factory=list)
    educations: list[Education] = Field(default_factory=list)
    experiences: list[WorkExperience] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    source_document_id: int | None = None  # node.id of the CV this was extracted from
    created_at: datetime | None = None
