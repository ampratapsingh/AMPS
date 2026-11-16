"""FastAPI application, dependencies and request handling."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.platforms.registry import build_platforms
from app.schemas import PostRequest, PostResponse, ValidationDetail, ValidationResponse
from app.services.posting_service import PostingService


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Share a single HTTP client and adapter registry across requests."""
    settings = get_settings()
    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
        app.state.posting_service = PostingService(
            build_platforms(settings, client), settings.platform_timeout_seconds
        )
        yield


def get_posting_service(request: Request) -> PostingService:
    """Resolve the posting service from the application lifespan."""
    return request.app.state.posting_service


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
    return JSONResponse(status_code=422, content=ValidationResponse(details=details).model_dump())


async def posting(post: PostRequest, service: PostingService = Depends(get_posting_service)) -> PostResponse:
    """Publish one validated message to the enabled platforms."""
    return await service.publish(post.message)


def create_app() -> FastAPI:
    """Build the application and register the posting endpoint."""
    app = FastAPI(
        title="Automated Multi-Platform Posting System", lifespan=lifespan, redoc_url=None
    )
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.post(
        "/posting",
        response_model=PostResponse,
        responses={422: {"model": ValidationResponse}},
        summary="Publish a message to multiple platforms",
        description="Send a message with one HTTP(S) link and receive a result for each enabled platform.",
    )(posting)
    return app


app = create_app()
