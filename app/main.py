"""FastAPI entry point."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.schemas import ValidationDetail, ValidationResponse

app = FastAPI(title="Automated Multi-Platform Posting System", redoc_url=None)


@app.exception_handler(RequestValidationError)
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
