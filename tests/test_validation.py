import httpx
import pytest
from fastapi import FastAPI

from app.main import validation_error_handler
from app.schemas import PostRequest
from app.validation import PostPayload, validate_message


def test_valid_message() -> None:
    assert validate_message("  Read this https://example.com/path  ") == PostPayload(
        "Read this https://example.com/path", "https://example.com/path"
    )


def test_character_limit() -> None:
    message = "a" * 180 + " https://example.com"
    assert len(message) == 200
    assert validate_message(message).text == message
    with pytest.raises(ValueError, match=r"must not exceed 200 characters \(got 201\)"):
        validate_message("a" + message)


@pytest.mark.parametrize(
    ("message", "reason"),
    [
        ("", "message must not be empty"),
        ("  \t", "message must not be empty"),
        ("missing link", "message must contain exactly one link (found 0)"),
        ("https://a.com https://b.com", "message must contain exactly one link (found 2)"),
        ("https://a.com https://a.com", "message must contain exactly one link (found 2)"),
        ("ftp://x.com", "link must start with http:// or https://"),
        ("www.example.com", "link must start with http:// or https://"),
        ("http://nodot", "link is not a valid URL"),
        ("https://-invalid.example", "link is not a valid URL"),
        ("https://example.com:99999", "link is not a valid URL"),
    ],
)
def test_invalid_message(message: str, reason: str) -> None:
    with pytest.raises(ValueError) as error:
        validate_message(message)
    assert str(error.value) == reason


@pytest.mark.parametrize("suffix", [".", ")", "!?"])
def test_trailing_punctuation(suffix: str) -> None:
    text = f"Read (HTTPS://example.com{suffix}"
    assert validate_message(text) == PostPayload(text, "HTTPS://example.com")


@pytest.mark.parametrize(
    ("body", "field", "message"),
    [
        ("{}", "message", "message is required"),
        ('{"message": 12}', "message", "message must be a string"),
        ("not JSON", "body", "body must be valid JSON"),
    ],
)
async def test_validation_error_shape(body: str, field: str, message: str) -> None:
    from fastapi.exceptions import RequestValidationError

    app = FastAPI()
    app.add_exception_handler(RequestValidationError, validation_error_handler)

    @app.post("/posting")
    async def posting(post: PostRequest) -> str:
        return post.message.text

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/posting", content=body, headers={"Content-Type": "application/json"}
        )

    assert response.status_code == 422
    assert response.json() == {
        "success": False,
        "error": "validation_error",
        "details": [{"field": field, "message": message}],
    }
