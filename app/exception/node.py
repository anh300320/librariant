from pathlib import Path

from app.exception.base import BaseAppException


class NodeExistError(BaseAppException):
    def __init__(self, path: Path):
        self.path = path
        super().__init__(f"Node already existed {path.as_posix()}")


class NodeNotFoundError(BaseAppException):
    def __init__(self, path: Path):
        self.path = path
        super().__init__(f"Path not found {path.as_posix()}")


class InvalidNodeTypeError(BaseAppException):
    def __init__(self, path: Path):
        self.path = path
        super().__init__(f"Invalid node type {path.as_posix()}")
