import httpx
import pytest

from app.validation import PostPayload, find_links, split_link, validate_message


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
        ("https://[v1.example]/path", "link is not a valid URL"),
        ("https://[::1]example.com/path", "link is not a valid URL"),
        ("https:///missing-host", "link is not a valid URL"),
        ("https://256.0.0.1/path", "link is not a valid URL"),
        (r"https://example.com\path", "link is not a valid URL"),
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
    "link",
    [
        "https://example.com:8443/path%20with%20spaces?q=a%2Bb&limit=2#section",
        "https://例え.テスト/path",
        "https://example.com./path",
        "http://localhost:8000/path",
        "http://192.0.2.1:8000/path",
        "https://[2001:db8::1]:8443/path?q=value#section",
        "http://[::]",
    ],
)
def test_valid_url_formats(link: str) -> None:
    text = f"Read this ({link})."
    assert validate_message(text).link == link


@pytest.mark.parametrize(
    "message",
    [
        "https://example.com/a https://example.org/b",
        "https://example.com/a,https://example.org/b",
        "https://example.com/a;https://example.org/b",
        "https://example.com/a!https://example.org/b",
        "[First](https://example.com/a),[Second](https://example.org/b)",
        "[First](https://example.com/a)[Second](https://example.org/b)",
        "https://example.com/a,[Second](https://example.org/b)",
        "[First](https://example.com/a),https://example.org/b",
        "[First](<https://example.com/a>),[Second](<https://example.org/b>)",
    ],
)
def test_multiple_ctas(message: str) -> None:
    assert [link.rstrip(",;") for link in find_links(message)] == [
        "https://example.com/a", "https://example.org/b"
    ]
    with pytest.raises(ValueError, match=r"message must contain exactly one link \(found 2\)"):
        validate_message(message)


@pytest.mark.parametrize(
    ("message", "link"),
    [
        ("Read <https://example.com/a>", "https://example.com/a"),
        ("[Read this](https://example.com/a)", "https://example.com/a"),
        ("[Read this](<https://example.com/a>)", "https://example.com/a"),
        ('[Read this](https://example.com/a "Title")', "https://example.com/a"),
        ("[Read this](https://example.com/a_(b(c)))", "https://example.com/a_(b(c))"),
        ("[Read this](http://[2001:db8::1])", "http://[2001:db8::1]"),
        (
            "Read https://example.com/a,b?redirect=https://example.org/path#section",
            "https://example.com/a,b?redirect=https://example.org/path#section",
        ),
    ],
)
def test_extract_single_cta(message: str, link: str) -> None:
    assert validate_message(message) == PostPayload(message, link)


def test_markdown_destination_position_matches_the_clickable_url() -> None:
    link = "https://example.com/a"
    message = f'[{link}]({link} "see https://example.org")'
    payload = validate_message(message)

    assert payload.link == link
    assert split_link(payload) == (f"[{link}](", ' "see https://example.org")')


@pytest.mark.parametrize(
    ("body", "field", "message"),
    [
        ("{}", "message", "message is required"),
        ('{"message": 12}', "message", "message must be a string"),
        ("not JSON", "body", "body must be valid JSON"),
    ],
)
async def test_validation_error_shape(
    api_client: httpx.AsyncClient, body: str, field: str, message: str
) -> None:
    response = await api_client.post(
        "/posting", content=body, headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 422
    assert response.json() == {
        "success": False,
        "error": "validation_error",
        "details": [{"field": field, "message": message}],
    }
