"""Request and response models for the posting endpoint."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_core import PydanticCustomError

from app.validation import PostPayload, validate_message


_SUCCESS_RESULT = {
    "platform": "GitHub Gist",
    "status": "success",
    "posted_url": "https://gist.github.com/author/abc123",
    "public_access": True,
    "date": "2026-11-16",
    "time": "10:30:00",
    "error": None,
}
POST_SUCCESS_EXAMPLE = {"success": True, "results": [_SUCCESS_RESULT]}
POST_PARTIAL_EXAMPLE = {
    "success": True,
    "results": [
        _SUCCESS_RESULT,
        {
            "platform": "Telegram",
            "status": "failed",
            "posted_url": None,
            "public_access": False,
            "date": None,
            "time": None,
            "error": "Authentication failed",
        },
    ],
}


class PostRequest(BaseModel):
    """A message with one CTA link."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"message": "Check out our latest business platform. https://example.com"}]
        }
    )

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

    model_config = ConfigDict(
        json_schema_extra={"examples": [POST_SUCCESS_EXAMPLE, POST_PARTIAL_EXAMPLE]}
    )

    success: bool
    results: list[PostResult]


class ValidationDetail(BaseModel):
    """One invalid field or request body."""

    field: str
    message: str


class ValidationResponse(BaseModel):
    """The response sent for invalid requests."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "success": False,
                    "error": "validation_error",
                    "details": [
                        {
                            "field": "message",
                            "message": "message must contain exactly one link (found 2)",
                        }
                    ],
                }
            ]
        }
    )

    success: Literal[False] = False
    error: Literal["validation_error"] = "validation_error"
    details: list[ValidationDetail]
