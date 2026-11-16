from datetime import date
from typing import Any

import pytest
from langchain_core.runnables import RunnableLambda

from app.models.candidate import Candidate, Education
from app.service.extractor.llm_extractor import SYSTEM_PROMPT, ExtractionError, LlmExtractor


class FakeLlm:
    """Stands in for a chat model: records what with_structured_output / invoke receive."""

    def __init__(self, output: Any = None, error: Exception | None = None) -> None:
        self.output = output
        self.error = error
        self.structured_kwargs: dict[str, Any] = {}
        self.schema: Any = None
        self.messages: list = []

    def with_structured_output(self, schema: Any, **kwargs: Any) -> RunnableLambda:
        self.schema, self.structured_kwargs = schema, kwargs

        def run(messages: list) -> Any:
            self.messages = messages
            if self.error:
                raise self.error
            return self.output

        return RunnableLambda(run)


def _candidate(**overrides: Any) -> Candidate:
    return Candidate(
        full_name="Jane Doe",
        tech_stack=["Python", "PostgreSQL"],
        educations=[Education(institution="MIT", gpa=3.8, gpa_cap=4.0, start_date=date(2015, 9, 1))],
        **overrides,
    )


def test_uses_native_json_schema_structured_output() -> None:
    llm = FakeLlm(output=_candidate())
    LlmExtractor(llm=llm)  # type: ignore[arg-type]
    assert llm.schema is Candidate
    assert llm.structured_kwargs == {"method": "json_schema"}


def test_extract_returns_candidate_and_sends_cv_text() -> None:
    llm = FakeLlm(output=_candidate())
    result = LlmExtractor(llm=llm).extract("Jane Doe\nPython developer")  # type: ignore[arg-type]

    assert result.full_name == "Jane Doe"
    assert result.educations[0].gpa_cap == 4.0
    system, human = llm.messages
    assert system.content == SYSTEM_PROMPT
    assert "<cv>\nJane Doe\nPython developer\n</cv>" == human.content


def test_extract_resets_system_owned_fields() -> None:
    llm = FakeLlm(output=_candidate(id=42, source_document_id=7))
    result = LlmExtractor(llm=llm).extract("cv text")  # type: ignore[arg-type]
    assert (result.id, result.source_document_id, result.created_at) == (0, None, None)


@pytest.mark.parametrize("text", ["", "   \n\t"])
def test_extract_rejects_empty_text_without_calling_llm(text: str) -> None:
    llm = FakeLlm(output=_candidate())
    with pytest.raises(ExtractionError, match="^Cannot extract a candidate from empty text$"):
        LlmExtractor(llm=llm).extract(text)  # type: ignore[arg-type]
    assert llm.messages == []


def test_extract_wraps_llm_errors() -> None:
    llm = FakeLlm(error=ValueError("gpa (4.2) must not exceed gpa_cap (4.0)"))
    with pytest.raises(ExtractionError, match="gpa_cap"):
        LlmExtractor(llm=llm).extract("cv text")  # type: ignore[arg-type]


def test_extract_rejects_unexpected_output() -> None:
    llm = FakeLlm(output={"full_name": "Jane"})
    with pytest.raises(ExtractionError, match="dict"):
        LlmExtractor(llm=llm).extract("cv text")  # type: ignore[arg-type]


async def test_aextract() -> None:
    llm = FakeLlm(output=_candidate(id=5))
    result = await LlmExtractor(llm=llm).aextract("cv text")  # type: ignore[arg-type]
    assert result.full_name == "Jane Doe" and result.id == 0


async def test_aextract_wraps_llm_errors() -> None:
    llm = FakeLlm(error=RuntimeError("refused"))
    with pytest.raises(ExtractionError, match="refused"):
        await LlmExtractor(llm=llm).aextract("cv text")  # type: ignore[arg-type]
