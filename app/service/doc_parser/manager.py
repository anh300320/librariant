from app.models.document import Document
from app.service.doc_parser.base import Parser
from app.service.doc_parser.models import ParsedDocument


class ParserManager(Parser):
    def __init__(
        self,
        parsers: list[Parser]
    ) -> None:
        self._parsers = parsers

    def parse(self, document: Document) -> ParsedDocument:
        for parser in self._parsers:
            return parser.parse(document=document)
