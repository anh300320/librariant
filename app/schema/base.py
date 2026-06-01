from typing import Any

from pydantic import BaseModel


class BaseResponse(BaseModel):
    status: str
    message: str = ""
    data: Any | None = None
