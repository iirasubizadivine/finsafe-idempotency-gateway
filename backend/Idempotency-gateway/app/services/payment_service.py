import asyncio
import uuid
import logging
from typing import Any, Dict, Tuple

from app.schemas.payment import PaymentRequest, PaymentResponse
from app.services.idempotency_service import idempotency_service
from app.core.exceptions import InvalidIdempotencyKeyException

logger = logging.getLogger(__name__)


class PaymentService:

    async def process_payment(self, amount: float, currency: str) -> PaymentResponse:
        await asyncio.sleep(2)

        transaction_id = f"tx_{uuid.uuid4().hex[:10]}"
        formatted_amount = f"{amount:.2f}".rstrip("0").rstrip(".")
        message = f"Charged {formatted_amount} {currency}"

        logger.info("Payment processed successfully. Transaction ID: %s", transaction_id)

        return PaymentResponse(
            message=message,
            amount=amount,
            currency=currency,
            transaction_id=transaction_id,
            status="SUCCESS",
        )

    async def process_payment_idempotent(
        self,
        payment_data: PaymentRequest,
        idempotency_key: str | None,
    ) -> Tuple[Dict[str, Any], int, bool]:
        if idempotency_key is None or not idempotency_key.strip():
            raise InvalidIdempotencyKeyException()

        key = idempotency_key.strip()
        payload = payment_data.model_dump()

        async def execute_payment() -> Tuple[Dict[str, Any], int]:
            payment_result = await self.process_payment(
                amount=payment_data.amount,
                currency=payment_data.currency,
            )
            result = payment_result.model_dump()
            result["amount"] = float(result["amount"])
            return result, 200

        return await idempotency_service.execute_idempotent(
            key=key,
            payload=payload,
            action=execute_payment,
        )

    @staticmethod
    def get_cache_hit_header(is_cache_hit: bool) -> str:
        return str(is_cache_hit).lower()


payment_service = PaymentService()