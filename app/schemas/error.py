from typing import Any

from pydantic import BaseModel


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[dict[str, Any]] | None = None


class ErrorResponse(BaseModel):
    """Every error from this API looks like {"error": {"code": ..., "message": ...}}."""

    error: ErrorBody
