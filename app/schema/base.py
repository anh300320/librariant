from typing import Any

from pydantic import BaseModel


class BaseResponse(BaseModel):
    status: str = "200"
    message: str = ""
    data: Any | None = None
