import io

from pypdf import PdfReader

from app.service.doc_parser.base import Parser
from app.service.doc_parser.models import ParsedDocument
from app.models.document import Document


class PdfParser(Parser):

    target_content_type = ["application/pdf"]

    def parse(self, document: Document) -> ParsedDocument:
        text = self._extract_text(document)
        return ParsedDocument(
            original=document,
            content=text.strip(),
        )

    def _extract_text(self, document: Document) -> str:
        content = document.raw_content
        with io.BytesIO(content) as file:
            with PdfReader(file) as reader:
                text = ""
                for page in reader.pages:
                    text += page.extract_text() + " "
                return text

