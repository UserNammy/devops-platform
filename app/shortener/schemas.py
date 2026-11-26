from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, HttpUrl

CODE_PATTERN = r"^[A-Za-z0-9_-]{3,16}$"

Code = Annotated[str, Field(pattern=CODE_PATTERN)]


class LinkCreate(BaseModel):
    url: HttpUrl
    code: Code | None = Field(
        default=None, description="Optional custom alias. Generated when omitted."
    )


class LinkOut(BaseModel):
    code: str
    target_url: str
    short_url: str
    clicks: int
    created_at: datetime
