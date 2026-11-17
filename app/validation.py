"""Validate a posting message and extract its CTA."""

import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from ipaddress import IPv4Address, IPv6Address
from urllib.parse import urlsplit

URL_PREFIX = r"(?:[a-z][a-z0-9+.\-]*://|www\.)"
URL_START = re.compile(URL_PREFIX, re.IGNORECASE)
# Treat punctuation as a separator only when it is followed by another URL.
LINK_SEPARATOR = r"""[\[\](){}.,;:!?|"'“”‘’]+"""
PLAIN_LINK = re.compile(
    rf"\b{URL_PREFIX}[^\s<>]+?(?=$|[\s<>]|{LINK_SEPARATOR}\b{URL_PREFIX})",
    re.IGNORECASE,
)
MARKDOWN_OPEN = re.compile(r"(?<!\\)\[(?:\\.|[^\[\]\\\n]|\[[^\[\]\n]*\])*\]\(\s*")
MARKDOWN_CLOSE = re.compile(r"""(?:\s+(?:"[^"\n]*"|'[^'\n]*'|\([^)\n]*\)))?\s*\)""")
DNS_LABEL = re.compile(r"[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?")
BRACKETED_HOST = r"\[[^\[\]/?#]+\]"
BRACKETED_URL_HOST = re.compile(rf"https?://(?:[^/?#@]*@)?{BRACKETED_HOST}", re.IGNORECASE)
TRAILING_PUNCTUATION = ".,;:!?)]}'\""


@dataclass(frozen=True)
class PostPayload:
    """The stripped message and its validated CTA URL."""

    text: str
    link: str
    _link_start: int | None = field(default=None, kw_only=True, repr=False, compare=False)


def _markdown_destination(text: str, start: int) -> tuple[int, int, int] | None:
    """Return the destination span and the end of the enclosing inline link."""
    if text.startswith("<", start):
        start += 1
        end = text.find(">", start)
        if end < 0 or any(char.isspace() or char == "<" for char in text[start:end]):
            return None
        close = MARKDOWN_CLOSE.match(text, end + 1)
    else:
        end = start
        depth = 0
        while end < len(text):
            char = text[end]
            if char.isspace() or char in "<>" or (char == ")" and depth == 0):
                break
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            end += 1
        if depth:
            return None
        close = MARKDOWN_CLOSE.match(text, end)

    if close:
        return start, end, close.end()
    return None


def _link_candidates(text: str) -> Iterator[tuple[int, str, bool]]:
    """Yield the position, text, and whether each URL is an inline destination."""
    cursor = 0
    for markdown in MARKDOWN_OPEN.finditer(text):
        if markdown.start() < cursor:
            continue
        destination = _markdown_destination(text, markdown.end())
        if destination is None:
            continue
        start, end, link_end = destination
        for plain in PLAIN_LINK.finditer(text, cursor, markdown.start()):
            yield plain.start(), plain.group(), False
        prefix = URL_START.match(text, start, end)
        if prefix and prefix.end() < end:
            yield start, text[start:end], True
        cursor = link_end

    for plain in PLAIN_LINK.finditer(text, cursor):
        yield plain.start(), plain.group(), False


def find_links(text: str) -> list[str]:
    """Return every candidate, including duplicates and unsupported schemes."""
    return [link for _, link, _ in _link_candidates(text)]


def _strip_punctuation(candidate: str) -> str:
    link = candidate.rstrip(TRAILING_PUNCTUATION)
    bracketed = BRACKETED_URL_HOST.match(candidate)
    # Keep the closing bracket of an IPv6 authority, even without a path.
    if bracketed and bracketed.end() > len(link):
        return candidate[:bracketed.end()]
    return link


def _valid_hostname(hostname: str, authority: str) -> bool:
    if authority.startswith("["):
        if not re.fullmatch(rf"{BRACKETED_HOST}(?::[0-9]*)?", authority):
            return False
        IPv6Address(hostname)
        return True

    hostname = hostname.encode("idna").decode("ascii").lower().removesuffix(".")
    if hostname == "localhost":
        return True
    labels = hostname.split(".")
    if len(labels) < 2 or len(hostname) > 253:
        return False
    if labels[-1].isdigit():
        IPv4Address(hostname)
        return True
    return all(DNS_LABEL.fullmatch(label) for label in labels)


def validate_link(candidate: str, *, strip_punctuation: bool = True) -> str:
    """Validate an HTTP(S) URL's host and port, cleaning plain-text candidates."""
    link = _strip_punctuation(candidate) if strip_punctuation else candidate
    if not link.lower().startswith(("http://", "https://")):
        raise ValueError("link must start with http:// or https://")

    try:
        if "\\" in link or any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in link):
            raise ValueError
        parts = urlsplit(link)
        hostname = parts.hostname or ""
        # Reading the port makes urlsplit check its syntax and range.
        _ = parts.port
        authority = parts.netloc.rsplit("@", 1)[-1]
        if not _valid_hostname(hostname, authority):
            raise ValueError
    except ValueError:
        raise ValueError("link is not a valid URL") from None
    return link


def validate_message(message: str) -> PostPayload:
    """Validate the stripped message in contract order."""
    text = message.strip()
    if not text:
        raise ValueError("message must not be empty")
    if len(text) > 200:
        raise ValueError(f"message must not exceed 200 characters (got {len(text)})")

    candidates = list(_link_candidates(text))
    if len(candidates) != 1:
        raise ValueError(f"message must contain exactly one link (found {len(candidates)})")
    start, candidate, inline = candidates[0]
    return PostPayload(
        text=text, link=validate_link(candidate, strip_punctuation=not inline), _link_start=start
    )


def split_link(payload: PostPayload) -> tuple[str, str]:
    """Return the text on either side of the already validated CTA."""
    start = payload._link_start
    if start is None:
        match = re.search(r"\b" + re.escape(payload.link), payload.text)
        assert match is not None  # A directly constructed payload must contain its link.
        start = match.start()
    return payload.text[:start], payload.text[start + len(payload.link):]
