from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import Runnable

from app.models.candidate import Candidate
from app.service.extractor.base import BaseExtractor
from app.settings.llm import llm_settings

SYSTEM_PROMPT = """\
You extract structured candidate profiles from the text of a CV / resume.

The text was extracted from a PDF, so it may have broken lines, odd spacing,
page headers/footers or columns read out of order. Work out the intended content.

Rules:
- Only use information stated in the CV. Never invent or guess values; leave a
  field null (or a list empty) when the CV doesn't state it.
- Leave `id` as 0 and `source_document_id` and `created_at` as null; the system fills them.
- Dates: use ISO format (YYYY-MM-DD). If only month and year are given, use the
  1st of the month; if only a year is given, use January 1st. For a current or
  ongoing role or study ("Present", "Now", "Current"), set `end_date` to null.
- GPA: set `gpa` and `gpa_cap` only when the CV gives a numeric grade, e.g.
  "3.8/4.0" -> gpa 3.8, gpa_cap 4.0. If the scale isn't stated, leave `gpa_cap`
  null. Non-numeric grades ("First Class Honours", "Distinction") go in the
  education `description`, with `gpa` and `gpa_cap` null.
- Tech stack: use each technology's common name (e.g. "PostgreSQL", not
  "postgres"; "Kubernetes", not "k8s"), with no duplicates. The candidate-level
  `tech_stack` is the candidate's overall skills; each experience's and project's
  `tech_stack` is only what was used there.
- `experiences` covers jobs and internships. Personal, academic or open-source
  work goes in `projects`.
- Keep descriptions faithful to the CV; you may join bullet points into prose
  but don't embellish.
"""


class ExtractionError(Exception):
    """The LLM could not produce a valid Candidate from the given text."""


class LlmExtractor(BaseExtractor):
    def __init__(self, llm: BaseChatModel | None = None) -> None:
        llm = llm or ChatAnthropic(
            model=llm_settings.model,
            effort=llm_settings.effort,
            max_tokens=llm_settings.max_tokens,
            timeout=llm_settings.timeout_sec,
            max_retries=llm_settings.max_retries,
        )
        # json_schema uses Claude's native structured output, so the response is
        # guaranteed to match Candidate's schema. The default method
        # (function_calling) relies on forced tool use, which current Claude
        # models reject.
        self._chain: Runnable = llm.with_structured_output(Candidate, method="json_schema")

    def extract(self, text: str) -> Candidate:
        messages = self._messages(text)
        try:
            output = self._chain.invoke(messages)
        except Exception as e:  # parse/validation errors (e.g. gpa > gpa_cap), refusals
            raise ExtractionError(f"LLM extraction failed: {e}") from e
        return self._finalize(output)

    async def aextract(self, text: str) -> Candidate:
        """Async variant for use inside the async workers."""
        messages = self._messages(text)
        try:
            output = await self._chain.ainvoke(messages)
        except Exception as e:  # parse/validation errors (e.g. gpa > gpa_cap), refusals
            raise ExtractionError(f"LLM extraction failed: {e}") from e
        return self._finalize(output)

    @staticmethod
    def _messages(text: str) -> list[BaseMessage]:
        if not text.strip():
            raise ExtractionError("Cannot extract a candidate from empty text")
        return [SystemMessage(SYSTEM_PROMPT), HumanMessage(f"<cv>\n{text}\n</cv>")]

    @staticmethod
    def _finalize(output: object) -> Candidate:
        if not isinstance(output, Candidate):
            raise ExtractionError(f"Unexpected LLM output type: {type(output).__name__}")
        # Fields owned by the system, never by the LLM.
        return output.model_copy(update={"id": 0, "source_document_id": None, "created_at": None})
