"""Validate a posting message and extract its CTA."""

import re
from dataclasses import dataclass
from urllib.parse import urlsplit

LINK_PATTERN = re.compile(r"\b(?:[a-z][a-z0-9+.\-]*://|www\.)\S+", re.IGNORECASE)
DNS_LABEL = re.compile(r"[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?")


@dataclass(frozen=True)
class PostPayload:
    """The stripped message and its validated CTA URL."""

    text: str
    link: str


def find_links(text: str) -> list[str]:
    """Return every candidate, including duplicates and unsupported schemes."""
    return LINK_PATTERN.findall(text)


def validate_link(candidate: str) -> str:
    """Remove trailing punctuation and require an HTTP(S) URL with DNS labels."""
    link = candidate.rstrip(".,;:!?)]}'\"")
    if not link.lower().startswith(("http://", "https://")):
        raise ValueError("link must start with http:// or https://")

    try:
        if any(ord(char) < 32 or ord(char) == 127 for char in link):
            raise ValueError
        parts = urlsplit(link)
        hostname = parts.hostname or ""
        # Reading the port makes urlsplit check its syntax and range.
        _ = parts.port
    except ValueError:
        raise ValueError("link is not a valid URL") from None

    if (
        len(hostname) > 253
        or "." not in hostname
        or not all(DNS_LABEL.fullmatch(label) for label in hostname.split("."))
    ):
        raise ValueError("link is not a valid URL")
    return link


def validate_message(message: str) -> PostPayload:
    """Validate the stripped message in contract order."""
    text = message.strip()
    if not text:
        raise ValueError("message must not be empty")
    if len(text) > 200:
        raise ValueError(f"message must not exceed 200 characters (got {len(text)})")

    candidates = find_links(text)
    if len(candidates) != 1:
        raise ValueError(f"message must contain exactly one link (found {len(candidates)})")
    return PostPayload(text=text, link=validate_link(candidates[0]))


def split_link(payload: PostPayload) -> tuple[str, str]:
    """Return the text on either side of the already validated CTA."""
    match = re.search(r"\b" + re.escape(payload.link), payload.text)
    assert match is not None  # validate_message extracted the CTA at a word boundary.
    return payload.text[:match.start()], payload.text[match.end():]
