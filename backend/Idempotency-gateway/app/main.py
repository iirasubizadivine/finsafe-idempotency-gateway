import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.payment_routes import router as payment_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting FinSafe Idempotency Gateway")
    yield
    logger.info("Shutting down FinSafe Idempotency Gateway")


app = FastAPI(
    title="FinSafe Idempotency Gateway",
    description=(
        "A concurrency-safe Idempotency Layer API built with FastAPI. "
        "Ensures payment requests with the same Idempotency-Key "
        "are processed only once."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


app.include_router(payment_router)