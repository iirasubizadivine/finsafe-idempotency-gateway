from fastapi import APIRouter, Header, HTTPException, status, Response

from app.schemas.payment import (
    PaymentRequest,
    PaymentResponse,
    ErrorResponse,
)
from app.services import payment_service, idempotency_service
from app.core.exceptions import IdempotencyConflictException


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
    # 1. Validate the idempotency key
    if idempotency_key is None or not idempotency_key.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Header 'Idempotency-Key' is required and cannot be empty.",
        )

    key = idempotency_key.strip()
    payload = payment_data.model_dump()

    # 2. Define the payment operation
    async def execute_payment():
        payment_result = await payment_service.process_payment(
            amount=payment_data.amount,
            currency=payment_data.currency,
        )

        result = payment_result.model_dump()
        # Ensure amount is float for JSON serialization
        result["amount"] = float(result["amount"])

        return result, status.HTTP_200_OK

    # 3. Execute with idempotency protection
    try:
        result_body, result_status, is_cache_hit = (
            await idempotency_service.execute_idempotent(
                key=key,
                payload=payload,
                action=execute_payment,
            )
        )

        # 4. Indicate whether the response was cached
        response.headers["X-Cache-Hit"] = (
            "true" if is_cache_hit else "false"
        )

        response.status_code = result_status

        return result_body

    except IdempotencyConflictException as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=exc.message,
        ) from exc