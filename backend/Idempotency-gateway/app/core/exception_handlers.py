from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    InvalidIdempotencyKeyException,
    IdempotencyConflictException,
)


async def invalid_idempotency_key_handler(
    request: Request,
    exc: InvalidIdempotencyKeyException,
):
    return JSONResponse(
        status_code=400,
        content={"detail": exc.message},
    )


async def idempotency_conflict_handler(
    request: Request,
    exc: IdempotencyConflictException,
):
    return JSONResponse(
        status_code=409,
        content={"detail": exc.message},
    )