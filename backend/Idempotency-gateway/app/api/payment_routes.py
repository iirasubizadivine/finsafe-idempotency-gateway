
from fastapi import APIRouter, Header, status, Response

from app.schemas.payment import (
    PaymentRequest,
    PaymentResponse,
    ErrorResponse,
)

from app.services import payment_service


router = APIRouter(tags=["Payments"])


@router.post(
    "/process-payment",
    response_model=PaymentResponse,
    status_code=status.HTTP_200_OK,
    summary="Process a Payment",
    description="Processes a payment transaction with idempotency protection.",
    responses={
        400: {
            "description": "Missing or invalid Idempotency-Key header",
            "model": ErrorResponse,
        },
        409: {
            "description": "Idempotency key reused for a different payload",
            "model": ErrorResponse,
        },
    },
)
async def process_payment(
    payment_data: PaymentRequest,
    response: Response,
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
        description="Unique string identifying this payment attempt.",
        examples=["req_unique_key_001"],
    ),
):

    result_body, result_status, is_cache_hit = (
        await payment_service.process_payment_idempotent(
            payment_data=payment_data,
            idempotency_key=idempotency_key,
        )
    )

    response.headers["X-Cache-Hit"] = (
        payment_service.get_cache_hit_header(is_cache_hit)
    )

    response.status_code = result_status

    return result_body
