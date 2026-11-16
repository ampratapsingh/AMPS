"""Request and response models for the posting endpoint."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator
from pydantic_core import PydanticCustomError

from app.validation import PostPayload, validate_message


class PostRequest(BaseModel):
    """A message with one CTA link."""

    message: PostPayload

    @field_validator("message", mode="plain", json_schema_input_type=str)
    @classmethod
    def check_message(cls, value: object) -> PostPayload:
        """Provide the service with the already validated message and link."""
        if not isinstance(value, str):
            raise PydanticCustomError("string_type", "message must be a string")
        try:
            return validate_message(value)
        except ValueError as exc:
            raise PydanticCustomError("invalid_message", str(exc)) from exc


class PostResult(BaseModel):
    """The result of publishing to one platform."""

    platform: str
    status: Literal["success", "failed"]
    posted_url: str | None
    public_access: bool
    date: str | None = Field(description="Publication date in UTC (YYYY-MM-DD).")
    time: str | None = Field(description="Publication time in UTC (HH:MM:SS).")
    error: str | None


class PostResponse(BaseModel):
    """Results in platform registry order."""

    success: bool
    results: list[PostResult]


class ValidationDetail(BaseModel):
    """One invalid field or request body."""

    field: str
    message: str


class ValidationResponse(BaseModel):
    """The response sent for invalid requests."""

    success: Literal[False] = False
    error: Literal["validation_error"] = "validation_error"
    details: list[ValidationDetail]
