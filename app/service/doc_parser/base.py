from abc import ABC, abstractmethod

from app.service.doc_parser.models import ParsedDocument
from app.models.document import Document


class Parser(ABC):

    target_content_type = []

    @abstractmethod
    def parse(self, document: Document) -> ParsedDocument:
        raise NotImplementedError