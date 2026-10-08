"""FastAPI application: routers + consistent JSON error handling."""
import logging
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes import certificates, jobs

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Bulk Certificate Generator API",
    description="Create many PDF certificates with one request, track progress, and download them.",
    version="1.0.0",
)
app.include_router(jobs.router, prefix="/api/v1")
app.include_router(certificates.router, prefix="/api/v1")


def _error(status_code: int, code: str, message: str, details: list | None = None) -> JSONResponse:
    body: dict = {"code": code, "message": message}
    if details is not None:
        body["details"] = details
    return JSONResponse(status_code=status_code, content={"error": body})


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    try:
        code = HTTPStatus(exc.status_code).phrase.upper().replace(" ", "_")
    except ValueError:
        code = "HTTP_ERROR"
    return _error(exc.status_code, code, str(exc.detail))


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = [
        {
            "field": ".".join(str(part) for part in err["loc"] if part != "body"),
            "message": str(err["msg"]).removeprefix("Value error, "),
        }
        for err in exc.errors()
    ]
    return _error(422, "VALIDATION_ERROR", "Invalid request", details)


@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return _error(500, "INTERNAL_SERVER_ERROR", "Something went wrong on our side.")  # no stack trace


@app.get("/health", tags=["Health"], summary="Liveness check")
def health() -> dict[str, str]:
    return {"status": "ok"}
