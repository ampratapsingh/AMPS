"""FastAPI application, dependencies and request handling."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from http.cookiejar import Cookie, CookieJar, DefaultCookiePolicy
from typing import Annotated
from urllib.request import Request as URLRequest

import httpx
from fastapi import Depends, FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException

from app.config import get_settings
from app.platforms.registry import build_platforms
from app.schemas import (
    POST_PARTIAL_EXAMPLE,
    POST_SUCCESS_EXAMPLE,
    PostRequest,
    PostResponse,
    ValidationDetail,
    ValidationResponse,
)
from app.services.posting_service import PostingService


class IgnoreCookies(DefaultCookiePolicy):
    """Keep anonymous probes independent of cookies set by earlier requests."""

    def set_ok(self, cookie: Cookie, request: URLRequest) -> bool:
        return False


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Share a single HTTP client and adapter registry across requests."""
    logging.basicConfig(level=logging.INFO)
    for logger_name in ("httpx", "httpcore"):
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    settings = get_settings()
    cookies = CookieJar(policy=IgnoreCookies())
    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0), cookies=cookies) as client:
        app.state.posting_service = PostingService(
            build_platforms(settings, client), settings.platform_timeout_seconds
        )
        yield


async def get_posting_service(request: Request) -> PostingService:
    """Resolve the posting service from the application lifespan."""
    return request.app.state.posting_service


def _validation_response(details: list[ValidationDetail]) -> JSONResponse:
    return JSONResponse(status_code=422, content=ValidationResponse(details=details).model_dump())


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Return the API's validation error envelope."""
    details = []
    for error in exc.errors():
        if error["type"] == "json_invalid":
            detail = ValidationDetail(field="body", message="body must be valid JSON")
        elif error["loc"] == ("body", "message"):
            message = "message is required" if error["type"] == "missing" else error["msg"]
            detail = ValidationDetail(field="message", message=message)
        else:
            detail = ValidationDetail(field="body", message="body must be a JSON object")
        details.append(detail)
    return _validation_response(details)


async def body_decoding_error_handler(request: Request, exc: HTTPException) -> Response:
    """Use the validation envelope when FastAPI wraps a JSON decoding failure."""
    if exc.status_code == 400 and isinstance(exc.__cause__, UnicodeDecodeError):
        return _validation_response([ValidationDetail(field="body", message="body must be valid JSON")])
    return await http_exception_handler(request, exc)


async def posting(
    post: PostRequest, service: Annotated[PostingService, Depends(get_posting_service)]
) -> PostResponse:
    """Publish one validated message to the enabled platforms."""
    return await service.publish(post.message)


def create_app() -> FastAPI:
    """Build the application and register the posting endpoint."""
    app = FastAPI(
        title="Automated Multi-Platform Posting System",
        lifespan=lifespan,
        redoc_url=None,
        swagger_ui_oauth2_redirect_url=None,
    )
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(HTTPException, body_decoding_error_handler)
    app.post(
        "/posting",
        response_model=PostResponse,
        responses={
            200: {
                "content": {
                    "application/json": {
                        "examples": {
                            "success": {
                                "summary": "All platforms succeeded",
                                "value": POST_SUCCESS_EXAMPLE,
                            },
                            "partial": {
                                "summary": "One platform failed",
                                "value": POST_PARTIAL_EXAMPLE,
                            },
                        }
                    }
                }
            },
            422: {"model": ValidationResponse},
        },
        summary="Publish a message to multiple platforms",
        description=(
            "Send up to 200 characters with exactly one HTTP(S) link. "
            "Every valid request returns HTTP 200 with a result for each enabled platform, "
            "and success is true when any platform publishes the message."
        ),
    )(posting)
    return app


app = create_app()
